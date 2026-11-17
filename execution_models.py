"""Execution records; the team's Trip/Decision/Trace contract stays unchanged."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import math


def cents(amount: float) -> int:
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError("Amount must be finite and positive")
    return int((Decimal(str(amount)) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def tick_time(night: int, tick: int) -> datetime:
    if night < 1 or not 0 <= tick < 32:
        raise ValueError("Expected night >= 1 and tick 0..31")
    # 20:00 PST on Nov 16; explicit UTC avoids host-timezone dependence.
    return datetime(2026, 11, 17, 4, tzinfo=timezone.utc) + timedelta(days=night-1, minutes=15*tick)


def parse_time(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Timestamp must include timezone")
    return result


@dataclass(frozen=True)
class Offer:
    id: str
    trip_id: str
    night: int
    tick: int
    price: float
    travel_date: str
    origin: str
    dest: str
    itinerary: tuple[str, ...]
    merchant: str
    quoted_at: str
    expires_at: str
    free_cancel_until: str
    cabin: str = 'economy'
    currency: str = 'usd'
    skip_segment: bool = False

    @classmethod
    def from_dict(cls, data):
        return cls(**{**data, 'itinerary': tuple(data['itinerary'])})


@dataclass(frozen=True)
class Checkout:
    id: str
    url: str | None
    status: str
    amount_cents: int
    currency: str
    backend: str
    operation_id: str

