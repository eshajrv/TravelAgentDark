"""Red-Eye memory layer (Esha): Cognee holds the policy, the workspace and the lessons.

Public functions (the contract in models.py):
    get_trips() -> list[Trip]
    recall_context(trip_id) -> str
    log_trace(trace) -> None
    end_night(night) -> list[str]

Plus helpers for setup and the demo:
    setup(reset=False)   load policy + workspace into Cognee (run once before Night 1)
    ask(question) -> str ask Cognee anything (used for the before/after proof)

Everything here is plain synchronous Python, so Rohan's run_night.py can call it directly.
Cognee is async; we run it on one background event loop (see _run).

CLI:
    python memory.py setup [--reset]
    python memory.py trips
    python memory.py context esha_sfo_jfk
    python memory.py ask "When should we buy SFO-JFK?"
    python memory.py end-night 1
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import threading
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Keep Cognee's databases in this project (gitignored as .cognee*), not inside .venv
_HERE = Path(__file__).parent
os.environ.setdefault("SYSTEM_ROOT_DIRECTORY", str(_HERE / ".cognee_system"))
os.environ.setdefault("DATA_ROOT_DIRECTORY", str(_HERE / ".cognee_data"))

import cognee  # noqa: E402  (needs the env loaded first)

from models import Decision, Trace, Trip  # noqa: E402

DATASET = "redeye"
ROOT = Path(__file__).parent
DATA = ROOT / "data"
OUTPUT = ROOT / "output"
TRIPS_FILE = OUTPUT / "trips.json"      # cache, so extraction runs once
LESSONS_FILE = OUTPUT / "lessons.json"  # every lesson learned, by night
TICKS_START_HOUR = 22                   # tick 0 = 10:00 PM, 4 ticks per hour
LINK_MAX = 500.0                        # Stripe Link's per-request cap (see BUILD_PLAN.md)
HOME_AIRPORT = os.getenv("HOME_AIRPORT", "SFO")  # used when a message doesn't say where they fly from

OUTPUT.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# One background event loop for all Cognee calls
# ---------------------------------------------------------------------------
_loop = asyncio.new_event_loop()
threading.Thread(target=_loop.run_forever, daemon=True, name="cognee-loop").start()


def _run(coro):
    """Run a Cognee coroutine from normal (sync) code and wait for the result."""
    return asyncio.run_coroutine_threadsafe(coro, _loop).result()


def _text(results) -> str:
    """Turn cognee.recall() results into plain text."""
    if isinstance(results, str):
        return results
    parts = []
    for r in results or []:
        for attr in ("answer", "text", "content"):
            value = getattr(r, attr, None) if not isinstance(r, dict) else r.get(attr)
            if value:
                parts.append(value if isinstance(value, str) else json.dumps(value))
                break
        else:
            parts.append(str(r))
    return "\n".join(p.strip() for p in parts if p and p.strip())


def tick_time(tick: int) -> str:
    """Tick 0 = 10:00 PM, every tick is 15 minutes."""
    minutes = TICKS_START_HOUR * 60 + tick * 15
    h, m = (minutes // 60) % 24, minutes % 60
    return f"{(h % 12) or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


def _route(trip: Trip) -> str:
    return f"{trip.origin}-{trip.dest}"


# ---------------------------------------------------------------------------
# Inputs: Aman's files if they exist, else the stand-ins
# ---------------------------------------------------------------------------
def _policy_text() -> str:
    path = DATA / "policy.md"
    return (path if path.exists() else DATA / "sample_policy.md").read_text()


def _workspace() -> dict:
    path = DATA / "workspace.json"
    return json.loads((path if path.exists() else DATA / "sample_workspace.json").read_text())


def _workspace_text(ws: dict) -> str:
    """Slack + email as readable lines with timestamps and source evidence IDs."""
    lines = []
    for m in ws.get("slack_messages", ws.get("slack", [])):
        lines.append(f"[Slack {m.get('id', '')} {m.get('channel', '')} "
                     f"{m.get('timestamp', m.get('ts', ''))}] "
                     f"{m.get('sender', m.get('user', ''))}: {m['text']}")
    for e in ws.get("emails", ws.get("email", [])):
        lines.append(
            f"[Email {e.get('id', '')} {e.get('timestamp', e.get('date', ''))}] From {e.get('from', '')} to {e.get('to', '')}, "
            f"subject \"{e.get('subject', '')}\": {e.get('body', '')}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
def setup(reset: bool = False) -> None:
    """Load the policy and the workspace into Cognee's permanent graph."""

    async def go():
        if reset:
            await cognee.forget(everything=True)
            for f in (TRIPS_FILE, LESSONS_FILE):
                f.unlink(missing_ok=True)
        await cognee.remember(_policy_text(), dataset_name=DATASET, self_improvement=False)
        await cognee.remember(
            "Team workspace messages (Slack and email):\n" + _workspace_text(_workspace()),
            dataset_name=DATASET,
            self_improvement=False,
        )

    _run(go())


def ask(question: str) -> str:
    """Ask Cognee a question over everything it knows (rules, workspace, lessons)."""
    return _text(_run(cognee.recall(question, datasets=[DATASET])))


# ---------------------------------------------------------------------------
# get_trips: who, where, when, banned dates, cap, trip type
# ---------------------------------------------------------------------------
_TRIP_PROMPT = """You are extracting upcoming work trips for a travel desk.

Using the team's Slack and email messages and the travel policy, list every upcoming work
trip. For each trip give:
- traveler: first name
- origin, dest: 3-letter airport codes (San Francisco = SFO, New York = JFK,
  Chicago = ORD, London = LHR)
- dates: every date they said they can fly, as YYYY-MM-DD (year 2026)
- banned_dates: dates they said they can NOT do, as YYYY-MM-DD
- trip_type: one of tier_a_conference, tier_b_conference, customer, other
- cap: the policy's fare cap in US dollars for that trip type

Return ONLY a JSON array, no prose, like:
[{"traveler": "Esha", "origin": "SFO", "dest": "JFK", "dates": ["2026-12-06"],
  "banned_dates": [], "trip_type": "tier_a_conference", "cap": 600}]"""


def _parse_trips(text: str) -> list[Trip]:
    match = re.search(r"\[.*\]", text, re.S)
    if not match:
        return []
    trips = []
    for t in json.loads(match.group(0)):
        if not t.get("traveler") or not t.get("dest"):
            continue  # not a usable trip
        origin = (t.get("origin") or HOME_AIRPORT).upper()
        dest = t["dest"].upper()
        trip = Trip(
            id=f"{t['traveler'].lower()}_{origin.lower()}_{dest.lower()}",
            traveler=t["traveler"],
            origin=origin,
            dest=dest,
            dates=list(t.get("dates") or []),
            banned_dates=list(t.get("banned_dates") or []),
            cap=float(t.get("cap") or 0),
            trip_type=t.get("trip_type") or "other",
        )
        # A banned date is never a travel date
        trip.dates = [d for d in trip.dates if d not in trip.banned_dates]
        trips.append(trip)
    return trips


def get_trips(refresh: bool = False) -> list[Trip]:
    """Trips pulled out of the workspace by Cognee. Cached in output/trips.json."""
    if TRIPS_FILE.exists() and not refresh:
        return [Trip(**t) for t in json.loads(TRIPS_FILE.read_text())]

    # Cognee answers from the graph built from the messages + policy
    trips = _parse_trips(ask(_TRIP_PROMPT))
    if not trips:
        # Fallback: hand Cognee's LLM the raw messages directly
        trips = _parse_trips(_llm(_TRIP_PROMPT + "\n\nPOLICY:\n" + _policy_text()
                                  + "\n\nMESSAGES:\n" + _workspace_text(_workspace())))
    TRIPS_FILE.write_text(json.dumps([asdict(t) for t in trips], indent=2))
    return trips


def _trip(trip_id: str) -> Trip:
    for t in get_trips():
        if t.id == trip_id:
            return t
    raise KeyError(f"Unknown trip {trip_id!r}. Known: {[t.id for t in get_trips()]}")


def _llm(prompt: str) -> str:
    """Direct LLM call, same model and key Cognee uses (LLM_MODEL / LLM_API_KEY)."""
    import litellm

    response = litellm.completion(
        model=os.getenv("LLM_MODEL", "openai/gpt-4o-mini"),
        api_key=os.getenv("LLM_API_KEY"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# recall_context: what the agent pastes into its prompt
# ---------------------------------------------------------------------------
def _lessons(route: str | None = None) -> list[dict]:
    if not LESSONS_FILE.exists():
        return []
    lessons = json.loads(LESSONS_FILE.read_text())
    return [x for x in lessons if route is None or x["route"] == route]


def recall_context(trip_id: str) -> str:
    """Rules, constraints and lessons for one trip, as plain text."""
    trip = _trip(trip_id)
    route = _route(trip)
    policy = ask(
        f"What travel policy rules apply to {trip.traveler}'s {trip.trip_type.replace('_', ' ')} "
        f"trip from {trip.origin} to {trip.dest}? Include the fare cap, when it needs approval, "
        f"and any dates {trip.traveler} cannot travel. Answer in 3 short bullet points."
    )
    learned = ask(f"What lessons have we learned about when to buy {route} fares overnight?")
    lessons = _lessons(route)

    lines = [
        f"Trip {trip.id}: {trip.traveler}, {trip.origin} to {trip.dest}, {trip.trip_type}.",
        f"Fly on: {', '.join(trip.dates) or 'not specified'}.",
        f"Never book: {', '.join(trip.banned_dates) or 'no banned dates'}.",
        f"Fare cap: ${trip.cap:.0f}. Over the cap means ESCALATE, never BUY.",
        f"Payment: Stripe Link, max ${LINK_MAX:.0f} per request. Over ${LINK_MAX:.0f} means ESCALATE "
        "even if under the cap.",
        "",
        "Policy (from Cognee):",
        policy or "(nothing found)",
        "",
        "Lessons from past nights:",
    ]
    if lessons:
        lines += [f"- Night {x['night']}: {x['lesson']}" for x in lessons]
        if learned:
            lines += ["Cognee's summary:", learned]
    else:
        lines.append("- No lessons yet.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# log_trace: every decision goes into that night's session
# ---------------------------------------------------------------------------
def _night_file(night: int) -> Path:
    return OUTPUT / f"night_{night}.json"


def _load_night(night: int) -> list[dict]:
    path = _night_file(night)
    return json.loads(path.read_text()) if path.exists() else []


def _save_night(night: int, rows: list[dict]) -> None:
    _night_file(night).write_text(json.dumps(rows, indent=2))


def log_trace(trace: Trace) -> None:
    """Save one decision: to output/night_N.json (for the UI) and to Cognee's night session."""
    row = asdict(trace)
    rows = _load_night(trace.night)
    rows.append(row)
    _save_night(trace.night, rows)

    d = trace.decision
    note = (
        f"Night {trace.night}, {tick_time(trace.tick)} (tick {trace.tick}): trip {trace.trip_id} "
        f"was ${trace.price:.0f}. Decision {d.action}: {d.reason}. "
        f"Rules used: {', '.join(d.rules_used) or 'none'}."
    )
    _run(cognee.remember(note, dataset_name=DATASET, session_id=f"night_{trace.night}", self_improvement=False))


# ---------------------------------------------------------------------------
# end_night: hindsight grading, then cognee.improve() turns it into lessons
# ---------------------------------------------------------------------------
def end_night(night: int) -> list[str]:
    """Grade the night in hindsight, let Cognee learn from it, and return the new lessons."""
    rows = _load_night(night)
    if not rows:
        return []
    trips = {t.id: t for t in get_trips()}

    new_lessons: list[dict] = []
    for trip_id in sorted({r["trip_id"] for r in rows}):
        trip_rows = [r for r in rows if r["trip_id"] == trip_id]
        low = min(trip_rows, key=lambda r: r["price"])
        first = trip_rows[0]
        bought = next((r for r in trip_rows if r["decision"]["action"] == "BUY"), None)

        for r in trip_rows:
            r["hindsight_min"] = low["price"]
            if r["decision"]["action"] == "BUY":
                r["regret"] = round(r["price"] - low["price"], 2)

        trip = trips.get(trip_id)
        route = _route(trip) if trip else trip_id
        drop = (first["price"] - low["price"]) / first["price"] * 100 if first["price"] else 0
        if bought:
            regret = bought["price"] - low["price"]
            lesson = (
                f"{route}: we bought at ${bought['price']:.0f} at {tick_time(bought['tick'])}, but the night's "
                f"low was ${low['price']:.0f} at {tick_time(low['tick'])} (${regret:.0f} of regret). "
                f"Fares fell {drop:.0f}% from the start of the night, so waiting until about "
                f"{tick_time(low['tick'])} is better than buying early."
                if regret > 0
                else f"{route}: we bought at the night's low of ${low['price']:.0f} at {tick_time(low['tick'])}. "
                f"Buying around {tick_time(low['tick'])} worked."
            )
        else:
            lesson = (
                f"{route}: we didn't buy. The night's low was ${low['price']:.0f} at {tick_time(low['tick'])}, "
                f"{drop:.0f}% below the first fare of the night."
            )
        new_lessons.append({"night": night, "route": route, "trip_id": trip_id, "lesson": lesson})

    _save_night(night, rows)

    async def learn():
        session = f"night_{night}"
        # The graded results go into the night's session with explicit numbers...
        for x in new_lessons:
            await cognee.remember(f"Hindsight grade for night {night}: {x['lesson']}",
                                  dataset_name=DATASET, session_id=session, self_improvement=False)
        # ...and improve() distills the whole session into the permanent graph
        await cognee.improve(dataset=DATASET, session_ids=[session])
        # Keep the lesson itself in permanent memory too, so recall always finds it
        await cognee.remember("\n".join(f"Lesson learned on night {night}: {x['lesson']}" for x in new_lessons),
                              dataset_name=DATASET, self_improvement=False)

    _run(learn())

    all_lessons = [x for x in _lessons() if x["night"] != night] + new_lessons
    LESSONS_FILE.write_text(json.dumps(all_lessons, indent=2))
    return [x["lesson"] for x in new_lessons]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["help"]
    if cmd == "setup":
        setup(reset="--reset" in args)
        print("Loaded policy and workspace into Cognee.")
    elif cmd == "trips":
        for t in get_trips(refresh="--refresh" in args):
            print(t)
    elif cmd == "context":
        print(recall_context(args[0]))
    elif cmd == "ask":
        print(ask(" ".join(args)))
    elif cmd == "end-night":
        for lesson in end_night(int(args[0])):
            print("-", lesson)
    else:
        print(__doc__)
