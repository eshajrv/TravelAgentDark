"""Shared data shapes and function contracts for Red-Eye.

Agreed by Esha, Rohan and Aman before coding. If you need to change a field
or a function name, tell the other two first.

Conventions:
- Dates are "YYYY-MM-DD" strings; prices are plain US dollars (float).
- Trip IDs are "traveler_origin_dest", e.g. "esha_sfo_jfk".
- recall_context() returns plain text for the agent's prompt.
- Traces are also written to output/night_N.json for the UI.

Payments:
- payments.py must have a MockPayments backend with the same two functions as
  LinkPayments (request_payment, get_payment), selected by PAYMENTS_BACKEND=mock|link
  in .env (default mock).
- LinkPayments calls the Stripe Link CLI (@stripe/link-cli) with --output-file, so card
  numbers never enter the agent's prompt or logs. Link caps each request at $500.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Trip:
    id: str                      # "esha_sfo_jfk"
    traveler: str                # "Esha"
    origin: str                  # "SFO"
    dest: str                    # "JFK"
    dates: list[str]             # ["2026-12-06", "2026-12-07"]
    banned_dates: list[str] = field(default_factory=list)  # ["2026-12-03"]
    cap: float = 0.0             # 600.0
    trip_type: str = "other"     # "tier_a_conference" | "tier_b_conference" | "customer" | "other"


@dataclass
class Decision:
    action: str                  # "BUY" | "WAIT" | "ESCALATE"
    reason: str
    rules_used: list[str] = field(default_factory=list)


@dataclass
class Trace:
    night: int
    tick: int                    # 0-31 (8 hours x 4 ticks per hour)
    trip_id: str
    price: float
    decision: Decision
    hindsight_min: float | None = None   # filled in by end_night()
    regret: float | None = None          # price paid minus the night's lowest


# ---------------------------------------------------------------------------
# Function contracts (signatures only; implementations live in each owner's file)
#
# Esha — memory.py
#   get_trips() -> list[Trip]
#   recall_context(trip_id: str) -> str          # rules + constraints + lessons, plain text
#   log_trace(trace: Trace) -> None
#   end_night(night: int) -> list[str]           # adds hindsight, calls cognee.improve(), returns new lessons
#
# Rohan — sim/fares.py, agent.py, payments.py, run_night.py
#   get_fare(trip: Trip, night: int, tick: int) -> float
#   decide(trip: Trip, price: float, context: str) -> Decision
#   run_night(night: int) -> list[Trace]
#
# Rohan — payments.py (MockPayments and LinkPayments, same two functions)
#   request_payment(amount: float, merchant: str, reason: str) -> dict
#       Creates a Link spend request.
#       Returns {"id": "lsrq_...", "approval_url": str, "status": "pending"}
#   get_payment(request_id: str) -> dict
#       Returns {"id", "status": "pending" | "approved" | "denied" | "expired",
#                "card_file": str | None}
#
# Rohan — sim/jinko.py (optional)
#   search_fares(trip: Trip) -> float | None
#       One real Jinko search; returns the lowest fare or None.
#       Used only as the simulator's base price.
#
# Aman — app.py
#   reads output/night_N.json and renders the demo
# ---------------------------------------------------------------------------
