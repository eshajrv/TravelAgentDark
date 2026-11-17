"""Durable local operations and simulated bookings; never store card details."""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from agent import eligibility_errors
from execution_models import Checkout, Offer, cents, parse_time


class State:
    def __init__(self, path, run_id):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.run_id = run_id
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS records(run TEXT, kind TEXT, id TEXT, payload TEXT,
                                             PRIMARY KEY(run,kind,id));
        ''')

    def close(self):
        self.db.close()

    def get(self, kind, key, default=None):
        row = self.db.execute('SELECT payload FROM records WHERE run=? AND kind=? AND id=?',
                              (self.run_id, kind, str(key))).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, kind, key, value):
        self.db.execute('INSERT OR REPLACE INTO records VALUES (?,?,?,?)',
                        (self.run_id, kind, str(key), json.dumps(value, allow_nan=False)))

    def all(self, kind):
        return [json.loads(r[0]) for r in self.db.execute(
            'SELECT payload FROM records WHERE run=? AND kind=? ORDER BY id', (self.run_id, kind))]

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def configure(self, config):
        with self.transaction():
            old = self.get('config', 'run')
            if old is not None and old != config:
                raise ValueError('Run configuration changed; choose a new run ID')
            self.put('config', 'run', config)

    def booking(self, trip_id):
        return self.get('booking', trip_id)

    def pending(self, trip_id):
        return next((o for o in self.all('operation') if o['offer']['trip_id'] == trip_id
                     and o['status'] in {'creating','pending','unknown','paid_unbooked','approved',
                                        'requires_action','submitted','succeeded'}), None)

    def prepare(self, offer, backend, trip):
        operation_id = sha256(f'{self.run_id}:{offer.id}:{backend}'.encode()).hexdigest()
        with self.transaction():
            existing = self.get('operation', operation_id)
            if existing:
                return existing
            if self.pending(trip.id):
                raise ValueError('Another checkout is unresolved for this trip')
            old = self.booking(trip.id)
            op = dict(id=operation_id, offer=asdict(offer), trip=asdict(trip), backend=backend,
                      status='creating', checkout=None, booking_id=None,
                      created_at=datetime.now(timezone.utc).isoformat(),
                      previous_booking_id=old['id'] if old else None)
            self.put('operation', operation_id, op)
            return op

    def record_checkout(self, operation_id, checkout):
        with self.transaction():
            op = self.get('operation', operation_id)
            if op['status'] == 'booked':
                return op
            op['checkout'] = asdict(checkout)
            op['status'] = 'paid_unbooked' if checkout.status == 'paid' else checkout.status
            self.put('operation', operation_id, op)
            return op

    def record_error(self, operation_id, error):
        with self.transaction():
            op = self.get('operation', operation_id)
            op.update(status='unknown', error=error)
            self.put('operation', operation_id, op)

    def finalize(self, operation_id, trip, now):
        """Atomic *simulated* booking/refund; never remote airline fulfillment."""
        with self.transaction():
            op = self.get('operation', operation_id)
            if op['status'] == 'booked':
                return op
            offer = Offer.from_dict(op['offer'])
            checkout = Checkout(**op['checkout'])
            if checkout.status != 'paid' or checkout.operation_id != operation_id or checkout.amount_cents != cents(offer.price) or checkout.currency != 'usd':
                raise ValueError('Payment not verified for this offer')
            errors = eligibility_errors(trip, offer, now)
            if errors or offer.price > trip.cap:
                raise ValueError('Booking policy recheck failed: ' + ', '.join(errors or ['cap_escalation']))
            old = self.booking(trip.id)
            if (old['id'] if old else None) != op['previous_booking_id']:
                raise ValueError('Booking changed while payment was pending')
            if old:
                if op['backend'] != 'mock':
                    raise ValueError('Remote replacement/refund requires separate orchestration')
                if now >= parse_time(old['free_cancel_until']) or offer.price >= old['price']:
                    raise ValueError('Replacement is not freely cancellable and cheaper')
            booking = dict(id='booking_'+operation_id[:24], trip_id=trip.id, offer_id=offer.id,
                           night=offer.night, price=offer.price, travel_date=offer.travel_date,
                           free_cancel_until=offer.free_cancel_until, status='simulated_confirmed',
                           payment_backend=op['backend'], payment_id=checkout.id,
                           replaced_booking_id=old['id'] if old else None,
                           simulated_refund=old['price'] if old else 0,
                           replacement_savings=round(old['price']-offer.price, 2) if old else 0)
            if old:
                self.put('history', old['id'], {**old, 'status':'simulated_replaced'})
            self.put('booking', trip.id, booking)
            op.update(status='booked', booking_id=booking['id'], booking=booking)
            self.put('operation', operation_id, op)
            return op
