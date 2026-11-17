"""Pure offer generation: call order never affects a seeded result."""
from __future__ import annotations
from datetime import timedelta
from hashlib import sha256
import random

from execution_models import Offer, tick_time
from models import Trip


def _price(trip: Trip, night: int, tick: int, seed: int) -> float:
    rng = random.Random(int.from_bytes(sha256(f'{seed}:{trip.id}:{night}:{tick}'.encode()).digest()[:8], 'big'))
    if (trip.origin, trip.dest) == ('SFO', 'JFK'):
        # The fixed demo anchors are data, never inputs to the decision policy.
        if tick == 0 and night == 1:
            return 412.0
        if tick == 24:
            return 287.0 if night == 1 else 291.0
        if tick < 24:
            return float(412 - tick * 3 + rng.randint(0, 8) + (night-1)*2)
        return float(340 + (tick-24)*5 + rng.randint(0, 10))
    if (trip.origin, trip.dest) == ('BOS', 'SFO'):
        return float(360 + rng.randint(0, 45))
    return float(260 + rng.randint(0, 30))


def get_offers(trip: Trip, night: int, tick: int, seed: int = 17) -> list[Offer]:
    now = tick_time(night, tick)
    offers = []
    for index, date in enumerate(sorted(set(trip.dates + trip.banned_dates))):
        price = 189.0 if date in trip.banned_dates else _price(trip, night, tick, seed) + index
        offers.append(Offer(
            id=f'{trip.id}:n{night}:t{tick}:{date}', trip_id=trip.id,
            night=night, tick=tick, price=price, travel_date=date,
            origin=trip.origin, dest=trip.dest, itinerary=(trip.origin, trip.dest),
            merchant='Demo Air', quoted_at=now.isoformat(),
            expires_at=(now+timedelta(minutes=15)).isoformat(),
            # Explicit synthetic fare term: fully refundable through end of next night.
            free_cancel_until=(tick_time(night+2, 0)).isoformat(),
        ))
    return sorted(offers, key=lambda o: (o.price, o.id))


def get_fare(trip: Trip, night: int, tick: int) -> float:
    """Legacy price wrapper. Execution must use rich offers for validation."""
    offers = [o for o in get_offers(trip, night, tick) if o.travel_date not in trip.banned_dates]
    if not offers:
        raise ValueError('No available travel date')
    return min(o.price for o in offers)


def hindsight_min(trip: Trip, night: int, seed: int = 17) -> float | None:
    """Only call after the night; never expose this to the timing provider."""
    from agent import eligibility_errors
    values = [o.price for tick in range(32) for o in get_offers(trip, night, tick, seed)
              if not eligibility_errors(trip, o, tick_time(night, tick)) and o.price <= min(trip.cap, 500)]
    return min(values) if values else None
