# Red-Eye Team Split: Esha, Rohan, Aman

Nov 16, 2026 · @Verma

Each person owns one layer, one sponsor and one demo moment.

## Step 0: agree on models.py (10 minutes, all three)

Before anyone codes, agree on the data shapes and function names so the three pieces fit together at the end. Think of it as agreeing on measurements before one person builds the walls and another the roof. Read the draft below together, tweak names if you want, and save it as `models.py` in the repo.

**The four questions to settle:**

1. What info does a trip have?
2. What does the agent's decision look like?
3. What gets logged at each step?
4. What are the function names, and who writes each one?

**Draft answers:**

```python
from dataclasses import dataclass

@dataclass
class Trip:
    id: str                  # "esha_sfo_jfk"
    traveler: str            # "Esha"
    origin: str              # "SFO"
    dest: str                # "JFK"
    dates: list[str]         # ["2026-12-06", "2026-12-07"]
    banned_dates: list[str]  # ["2026-12-03"]
    cap: float               # 600.0
    trip_type: str           # "tier_a_conference" | "tier_b_conference" | "customer" | "other"

@dataclass
class Decision:
    action: str              # "BUY" | "WAIT" | "ESCALATE"
    reason: str
    rules_used: list[str]

@dataclass
class Trace:
    night: int
    tick: int                # 0-31
    trip_id: str
    price: float
    decision: Decision
    hindsight_min: float | None = None   # Esha fills in at end of night
    regret: float | None = None          # price paid minus the night's lowest

# Esha (memory.py)
def get_trips() -> list[Trip]: ...
def recall_context(trip_id: str) -> str: ...   # plain text: rules + constraints + lessons
def log_trace(trace: Trace) -> None: ...
def end_night(night: int) -> list[str]: ...    # returns the new lessons

# Rohan (sim / agent / payments / run_night)
def get_fare(trip: Trip, night: int, tick: int) -> float: ...
def decide(trip: Trip, price: float, context: str) -> Decision: ...
def issue_card(amount: float, merchant: str, trip_id: str) -> dict: ...
def run_night(night: int) -> list[Trace]: ...
```

**Small rules:**

- Dates are `"YYYY-MM-DD"` strings and prices are plain dollars.
- Trip IDs are `traveler_origin_dest`.
- `recall_context` returns plain text, so the agent can paste it straight into its prompt.
- Traces are also saved to `output/night_N.json`, so Aman's app can read them without calling Cognee.

**Dummy versions:** each person writes a fake version of anyone else's function they need, so their own part runs right away. For example, Rohan's temporary stand-in for Esha's function:

```python
def recall_context(trip_id):
    return "Cap $600. Tier A conference. Banned dates: none. No lessons yet."
```

Aman builds the app against a hand-written `output/night_1.json`. When the real function is ready, delete the fake and import the real one; nothing else changes.

**The one rule:** if anyone needs to change a field or a function name, tell the other two first.

## Esha: memory and learning (Cognee)

**Owns:** `memory.py`, the policy setup, and the Cognee mentor conversation.

**Builds:**

- Loads the company policy and the Slack and email messages into Cognee.
- Pulls trips out of the messages: who, where, which dates, banned dates and the cap. Rohan's "not Dec 3" has to come out of the chat, not be typed in by hand.
- `recall_context(trip)`: gives the agent the rules, constraints and past lessons for a trip.
- `log_trace(trace)`: saves every decision into that night's session.
- `end_night(night)`: works out how much each buy overpaid compared with the night's low, then calls `improve()` so Cognee turns that into lessons.
- The before/after proof: the same question asked to Cognee before and after `improve()`, with visibly different answers.

**Done when:** after Night 1, Cognee answers "when should we buy SFO→JFK?" with a real lesson it learned.

**Demo moment:** "here's what it learned."

## Rohan: the agent and payments (Allowance)

**Owns:** `sim/fares.py`, `agent.py`, `payments.py`, `run_night.py`, and the Allowance founder conversation.

**Builds:**

- **Fare simulator:** prices that move through the night, a fixed seed so every run is identical, and Night 1 set up so a naive buy overpays (about $412 early, about $287 later).
- **Decision agent:** takes the trip, the price and the Cognee context, and returns buy, wait or escalate with a reason and the rules it used.
- **Payments:** a one-time card capped at the fare plus $5, issued only after the policy check passes. Allowance if the API works; otherwise Stripe test mode or a fake card behind the same function.
- **Night loop:** 32 ticks; calls `recall_context` and `log_trace` from Esha's code and `end_night` at the end.

**Done when:** running Night 1 and then Night 2 shows the agent buying cheaper on Night 2, refusing Rohan's Dec 3 fare, and escalating Priya's.

**Demo moment:** "watch it decide."

## Aman: data, product and pitch

**Owns:** `data/workspace.json`, `data/policy.md`, `app.py`, the slides and the demo.

**Builds:**

- **Fake workspace:** about 20 Slack messages and 5 emails that read like a real startup, with the constraints hidden in casual chat. This is what makes Esha's extraction look impressive.
- **Policy doc:** about 10 rules in plain English, with the Tier A and Tier B conference lists.
- **Streamlit app:**
  - extracted trip cards
  - a fare chart with buy, wait and escalate markers
  - the decision log with reasons
  - a lessons panel
  - Night 1 vs. Night 2 savings
  - a morning summary
- **Pitch:** 3–4 slides, the 3-minute script, judge Q&A, and a backup video.

**Done when:** someone who has never seen the project understands it from the app alone.

**Demo moment:** runs the whole demo.

## Handoffs between teammates

| From | To | What gets passed |
| --- | --- | --- |
| Aman | Esha | `workspace.json` and `policy.md` (Esha loads them into Cognee) |
| Esha | Rohan | `get_trips()`, `recall_context()`, `log_trace()`, `end_night()` |
| Rohan | Aman | Traces and results (Aman's app displays them) |

All of these use the shapes and names agreed in Step 0.
