"""Explicit offline fixture, NOT Cognee. Production uses Esha's memory module."""
import json

from models import Trip


class DemoMemory:
    def __init__(self, state):
        self.state = state
        self.snapshot = None

    def get_trips(self):
        return [Trip('esha_sfo_jfk','Esha','SFO','JFK',['2026-12-06','2026-12-07'],cap=600,trip_type='tier_a_conference'),
                Trip('rohan_sfo_ord','Rohan','SFO','ORD',['2026-12-02','2026-12-04'],['2026-12-03'],300,'customer'),
                Trip('priya_bos_sfo','Priya','BOS','SFO',['2026-12-09','2026-12-10'],cap=300)]

    def recall_context(self, trip_id):
        return json.dumps({'source':'offline_demo_fixture', 'rules':['trip_cap','allowed_dates','economy_only'],
                           'timing_rule': self.state.get('lesson', trip_id)})

    def log_trace(self, trace):
        # Runner persists traces. No external service is called in fixture mode.
        pass

    def prepare_hindsight(self, snapshot):
        self.snapshot = snapshot

    def end_night(self, night):
        lessons = []
        for trip in self.get_trips():
            buys = [e for e in self.snapshot['execution_events'] if e['status']=='booked'
                    and e['offer']['trip_id']==trip.id]
            low = self.snapshot['metrics']['eligible_hindsight_min'].get(trip.id)
            if buys and low is not None and any(e['offer']['price'] > low for e in buys):
                # A cautious single-sample heuristic, not a claimed route trend.
                target = round(low*1.05,2)
                lesson = f'Night {night} observed an eligible {trip.origin}-{trip.dest} low of ${low:.2f} after an earlier buy. Trial target ${target:.2f}; one simulated night is not a reliable trend.'
                with self.state.transaction():
                    self.state.put('lesson',trip.id,{'target_price':target,'lesson':lesson,'source_night':night})
                lessons.append(lesson)
        return lessons

