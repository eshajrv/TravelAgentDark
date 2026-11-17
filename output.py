"""Atomic versioned exports; compatible with Aman's trips/traces/lessons reader."""
import json
import os
from pathlib import Path
import tempfile


def write_snapshot(path, snapshot):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.'+path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(snapshot, stream, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def grade_snapshot(snapshot):
    """Mechanical UI grading from eligible observed offers and executed buys.

    Esha still owns memory improvement. This supplies its evidence and prevents
    an unpaid BUY or forbidden fare being presented as a missed saving.
    """
    minima = {}
    first = {}
    for observation in snapshot['observations']:
        offer = observation['offer']
        if not observation['eligible']:
            continue
        tid = offer['trip_id']
        first.setdefault(tid, offer['price'])
        minima[tid] = min(minima.get(tid, float('inf')), offer['price'])
    executed = {e['trace_index']:e for e in snapshot['execution_events'] if e['status']=='booked'}
    for i, trace in enumerate(snapshot['traces']):
        if i in executed:
            trace['hindsight_min'] = minima.get(trace['trip_id'])
            trace['regret'] = round(max(0, trace['price']-minima[trace['trip_id']]), 2) if trace['trip_id'] in minima else None
    metrics = {'eligible_hindsight_min': minima, 'first_eligible_price': first,
               'simulated_replacement_savings': round(sum(e.get('booking', {}).get('replacement_savings',0) for e in executed.values()),2),
               'confirmed_real_flight_savings': 0}
    snapshot['metrics'] = metrics

