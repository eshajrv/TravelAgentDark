"""Read-only dashboard adapter. No memory, payment, or runner imports."""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from models import Decision, Trace, Trip


@dataclass
class Night:
    number: int
    traces: list[Trace] = field(default_factory=list)
    trips: list[Trip] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source: str = ""
    demo: bool = False
    metadata: dict = field(default_factory=dict)
    observations: list[dict] = field(default_factory=list)
    executions: list[dict] = field(default_factory=list)
    bookings: list[dict] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def money(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError("amount cannot be boolean")
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError("amount must be finite and nonnegative")
    return value


def integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def parse_trip(raw: dict) -> Trip:
    fields = {k: raw[k] for k in Trip.__dataclass_fields__ if k in raw}
    trip = Trip(**fields)
    for key in ("id", "traveler", "origin", "dest", "trip_type"):
        if not isinstance(getattr(trip, key), str) or not getattr(trip, key):
            raise ValueError(f"invalid trip {key}")
    for key in ("dates", "banned_dates"):
        dates = getattr(trip, key)
        if not isinstance(dates, list) or any(not isinstance(v, str) for v in dates):
            raise ValueError(f"invalid {key}")
    trip.cap = money(trip.cap)
    return trip


def read_trips(path: Path) -> tuple[list[Trip], list[str]]:
    if not path.exists():
        return [], []
    try:
        raw = json.loads(path.read_text())
        rows = raw.get("trips", []) if isinstance(raw, dict) else raw
        if not isinstance(rows, list):
            raise ValueError("trips must be an array")
        return [parse_trip(row) for row in rows], []
    except (OSError, ValueError, TypeError, KeyError) as error:
        return [], [f"Could not read {path.name}: {error}"]


def read_night(path: Path, number: int, *, demo: bool = False) -> Night:
    result = Night(number, source=str(path), demo=demo)
    try:
        raw = json.loads(path.read_text())
        if isinstance(raw, dict):
            result.metadata = {key: raw[key] for key in ("run_id", "status", "mode", "payment_backend", "memory_mode") if isinstance(raw.get(key), str)}
            # Copy only display fields. Never retain card_file, raw CLI output,
            # credentials, or unknown payment fields from execution records.
            for item in raw.get("observations", []) if isinstance(raw.get("observations"), list) else []:
                try:
                    offer = item["offer"]
                    observation = {"trip_id":str(offer["trip_id"]), "tick":integer(offer["tick"], "tick"), "price":money(offer["price"]), "date":str(offer.get("travel_date", "")), "eligible":item.get("eligible") is True, "rules":", ".join(str(r) for r in item.get("rejection_rules", []))}
                    if not 0 <= observation["tick"] <= 31:
                        raise ValueError("observation tick outside 0–31")
                    result.observations.append(observation)
                except (ValueError, TypeError, KeyError, AttributeError):
                    result.warnings.append("Omitted an invalid market observation.")
            for event in raw.get("execution_events", []) if isinstance(raw.get("execution_events"), list) else []:
                try:
                    offer = event["offer"]
                    payment = event.get("checkout") or event.get("payment") or {}
                    result.executions.append({"Trip":str(offer["trip_id"]), "Tick":integer(offer["tick"], "tick"), "Fare":money(offer["price"]), "Execution":str(event.get("status", "unknown")), "Payment":str(payment.get("status", "unknown")), "Backend":str(event.get("backend", "unknown"))})
                except (ValueError, TypeError, KeyError, AttributeError):
                    result.warnings.append("Omitted an invalid payment execution record.")
            for booking in raw.get("bookings", []) if isinstance(raw.get("bookings"), list) else []:
                try:
                    result.bookings.append({"Trip":str(booking["trip_id"]), "Date":str(booking.get("travel_date", "")), "Fare":money(booking["price"]), "Status":str(booking.get("status", "unknown")), "Backend":str(booking.get("payment_backend", "unknown"))})
                except (ValueError, TypeError, KeyError, AttributeError):
                    result.warnings.append("Omitted an invalid booking record.")
            for key in ("simulated_replacement_savings", "confirmed_real_flight_savings"):
                try:
                    if isinstance(raw.get("metrics"), dict) and key in raw["metrics"]:
                        result.metrics[key] = money(raw["metrics"][key])
                except (ValueError, TypeError):
                    result.warnings.append(f"Omitted invalid {key}.")
            for error in raw.get("errors", []) if isinstance(raw.get("errors"), list) else []:
                if isinstance(error, dict):
                    result.warnings.append(f"Runner reported an error in {error.get('component', 'unknown component')}; inspect runner diagnostics.")
            rows = raw.get("traces", [])
            raw_trips = raw.get("trips", [])
            if not isinstance(raw_trips, list):
                raise ValueError("trips must be an array")
            for trip in raw_trips:
                result.trips.append(parse_trip(trip))
            lessons = raw.get("lessons", [])
            if not isinstance(lessons, list) or any(not isinstance(x, str) for x in lessons):
                result.warnings.append("Lessons were not a list of strings; omitted.")
            else:
                result.lessons = lessons
        else:
            rows = raw
        if not isinstance(rows, list):
            raise ValueError("night output must be a Trace array or an object with traces")
        seen = set()
        for index, row in enumerate(rows):
            try:
                if not isinstance(row, dict):
                    raise ValueError("trace must be an object")
                tick = integer(row["tick"], "tick")
                night = integer(row.get("night", number), "night")
                if night != number or not 0 <= tick <= 31:
                    raise ValueError("night mismatch or tick outside 0–31")
                trip_id = row["trip_id"]
                if not isinstance(trip_id, str) or not trip_id:
                    raise ValueError("missing trip_id")
                d = row["decision"]
                if not isinstance(d, dict):
                    raise ValueError("decision must be the nested models.Decision object")
                action = d["action"]
                if action not in {"BUY", "WAIT", "ESCALATE"}:
                    raise ValueError("unknown action")
                reason = d["reason"]
                rules = d.get("rules_used", [])
                if not isinstance(reason, str) or not isinstance(rules, list) or any(not isinstance(x, str) for x in rules):
                    raise ValueError("invalid decision reason or rules")
                key = (trip_id, tick)
                if key in seen:
                    raise ValueError("duplicate trip/tick")
                trace = Trace(night, tick, trip_id, money(row["price"]), Decision(action, reason, rules),
                              money(row["hindsight_min"]) if row.get("hindsight_min") is not None else None,
                              money(row["regret"]) if row.get("regret") is not None else None)
                seen.add(key)
                result.traces.append(trace)
            except (ValueError, TypeError, KeyError) as error:
                result.warnings.append(f"Skipped trace {index + 1}: {error}")
    except (OSError, ValueError, TypeError, KeyError) as error:
        result.warnings.append(f"Could not read {path.name}: {error}")
    result.traces.sort(key=lambda t: (t.tick, t.trip_id))
    return result


def load_nights(folder: Path, *, demo: bool = False) -> dict[int, Night]:
    result = {}
    trips, warnings = read_trips(folder / "trips.json")
    for path in sorted(folder.glob("night_*.json")):
        match = re.fullmatch(r"night_([1-9]\d*)\.json", path.name)
        if not match:
            continue
        n = int(match[1])
        night = read_night(path, n, demo=demo)
        if not night.trips:
            night.trips = trips
        night.warnings.extend(warnings)
        lesson_path = folder / f"lessons_{n}.json"
        if not night.lessons and lesson_path.exists():
            try:
                lessons = json.loads(lesson_path.read_text())
                if isinstance(lessons, dict):
                    lessons = lessons.get("lessons", [])
                if not isinstance(lessons, list) or any(not isinstance(x, str) for x in lessons):
                    raise ValueError("lessons must be an array of strings")
                night.lessons = lessons
            except (OSError, ValueError, TypeError) as error:
                night.warnings.append(f"Could not read {lesson_path.name}: {error}")
        result[n] = night
    return result


def purchases(night: Night, tick: int = 31) -> dict[str, Trace]:
    """First BUY per trip, never one purchase per logged tick."""
    result = {}
    for trace in sorted(night.traces, key=lambda t: t.tick):
        if trace.tick <= tick and trace.decision.action == "BUY":
            result.setdefault(trace.trip_id, trace)
    return result


def statuses(night: Night, tick: int = 31) -> dict[str, Trace]:
    latest = {t.trip_id: t for t in night.traces if t.tick <= tick}
    latest.update(purchases(night, tick))
    return latest


def comparison(first: Night, second: Night) -> list[dict]:
    a, b = purchases(first), purchases(second)
    return [{"Trip": key, "Night 1": a[key].price, "Night 2": b[key].price,
             "Savings": round(a[key].price - b[key].price, 2)} for key in sorted(a.keys() & b.keys())]


def clock_label(tick: int) -> str:
    minutes = (22 * 60 + tick * 15) % (24 * 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def digest(night: Night, tick: int = 31) -> str:
    lines = [f"Red-Eye — Night {night.number}", "Demo fixtures; simulated purchases." if night.demo else "Runner output; BUY records are decisions, not booking confirmations.", ""]
    for trip_id, trace in statuses(night, tick).items():
        lines.append(f"{trip_id}: {trace.decision.action} at ${trace.price:,.2f}. {trace.decision.reason}")
    if not night.traces:
        lines.append("No decisions available.")
    return "\n".join(lines)
