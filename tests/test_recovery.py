"""Failure-boundary checks for decisions, trace delivery and spend requests."""
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent import evaluate_offer
from demo_memory import DemoMemory
from execution_models import Checkout, cents, tick_time
from models import Decision
from payments import MockPayments, LinkPayments
from run_night import execute_purchase, run_night_async, refresh_escalations
from sim.fares import get_offers
from state import State


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        self.state = State(self.path / 'state.db', 'recovery')
        self.memory = DemoMemory(self.state)
        self.trip = self.memory.get_trips()[0]

    def tearDown(self):
        self.state.close()
        self.tmp.cleanup()

    def run_night(self, n=1, memory=None, backend=None):
        return asyncio.run(run_night_async(n, state=self.state, memory=memory or self.memory,
            backend=backend or MockPayments(), output_dir=self.path))

    def test_missing_memory_blocks_even_permissive_provider(self):
        offer = get_offers(self.trip, 1, 0)[0]
        decision = evaluate_offer(self.trip, offer, '', tick_time(1, 0),
                                  provider=lambda *a: Decision('BUY', 'Go', []))
        self.assertEqual(decision.action, 'ESCALATE')
        self.assertIn('memory_required', decision.rules_used)

    def test_link_limit_escalates_before_timing_provider(self):
        offer = replace(get_offers(self.trip, 1, 0)[0], price=550)
        decision = evaluate_offer(self.trip, offer, 'rules', tick_time(1, 0),
                                  provider=lambda *a: Decision('WAIT', 'Wait', []))
        self.assertEqual(decision.action, 'ESCALATE')
        self.assertIn('link_request_cap', decision.rules_used)

    def test_expired_replacement_never_requests_payment(self):
        execute_purchase(self.state, MockPayments(), self.trip, get_offers(self.trip, 1, 0)[0], tick_time(1, 0))
        original = self.state.booking(self.trip.id)
        with self.state.transaction():
            self.state.put('booking', self.trip.id, {**original, 'free_cancel_until': tick_time(2, 0).isoformat()})
        class MustNotCall:
            backend = 'mock'
            def create_checkout(self, *a):
                raise AssertionError('Cancellation must be checked before issuing payment')
        with self.assertRaises(ValueError):
            execute_purchase(self.state, MustNotCall(), self.trip, get_offers(self.trip, 2, 24)[0], tick_time(2, 24))
        self.assertEqual(len(self.state.all('operation')), 1)
        self.assertEqual(self.state.booking(self.trip.id)['id'], original['id'])

    def test_trace_failure_resumes_without_repeating_purchase(self):
        wrapped = self.memory
        class FlakyMemory:
            failed = False
            def get_trips(self): return wrapped.get_trips()
            def recall_context(self, key): return wrapped.recall_context(key)
            def log_trace(self, trace):
                if not self.failed:
                    self.failed = True
                    raise RuntimeError('Temporary memory failure')
                wrapped.log_trace(trace)
            def prepare_hindsight(self, snapshot): wrapped.prepare_hindsight(snapshot)
            def end_night(self, n): return wrapped.end_night(n)
        memory = FlakyMemory()
        partial = self.run_night(memory=memory)
        self.assertEqual(partial['status'], 'memory_failed')
        self.assertEqual(partial['next_tick'], 1)
        self.assertEqual(len(partial['traces']), 3)
        self.assertEqual(len(self.state.all('operation')), 2)
        result = self.run_night(memory=memory)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(result['traces']), 96)
        self.assertEqual(len(self.state.all('operation')), 2)
        self.assertTrue(all(x['sent'] for x in self.state.all('trace_outbox')))

    def test_crash_after_booking_preserves_original_buy_and_regret(self):
        import run_night as runner
        original = runner.execute_purchase
        class Crash(BaseException): pass
        def crash_after_payment(*args):
            original(*args)
            raise Crash()
        with patch('run_night.execute_purchase', crash_after_payment):
            with self.assertRaises(Crash): self.run_night()
        booking_id = self.state.booking(self.trip.id)['id']
        result = self.run_night()
        trace = next(t for t in result['traces'] if t['trip_id'] == self.trip.id and t['tick'] == 0)
        self.assertEqual(trace['decision']['action'], 'BUY')
        self.assertEqual(trace['regret'], 125)
        self.assertEqual(self.state.booking(self.trip.id)['id'], booking_id)
        self.assertEqual(len(result['traces']), 96)
        self.assertEqual(len({(t['tick'], t['trip_id']) for t in result['traces']}), 96)
        self.assertEqual(len(self.state.all('operation')), 2)

    def test_ambiguous_link_create_is_not_automatically_retried(self):
        class Ambiguous:
            backend = 'link'
            calls = 0
            def create_checkout(self, offer, key):
                self.calls += 1
                raise TimeoutError('Unknown create outcome')
        backend = Ambiguous()
        offer = get_offers(self.trip, 1, 0)[0]
        with self.assertRaises(TimeoutError): execute_purchase(self.state, backend, self.trip, offer, tick_time(1, 0))
        result = execute_purchase(self.state, backend, self.trip, offer, tick_time(1, 0))
        self.assertEqual(backend.calls, 1)
        self.assertEqual(result['status'], 'unknown')
        self.assertFalse(self.state.all('booking'))

    def test_link_lifecycle_and_required_action_are_not_booking(self):
        next_action = {'type': 'partner_auth_challenge', 'resolution': 'auto_resume',
                       'display_message': 'Verify in Link', 'action_url': 'https://app.link.com/test',
                       'card': 'SECRET'}
        class Result:
            returncode = 0
            stdout = ''
        def executor(args, **kwargs): return Result()
        backend = LinkPayments(merchant_url='https://air.example', card_dir=self.path, executor=executor)
        offer = get_offers(self.trip, 1, 0)[0]
        for status in ('created', 'pending_approval', 'requires_action', 'approved', 'denied', 'expired',
                       'canceled', 'submitted', 'succeeded', 'failed'):
            Result.stdout = json.dumps({'id': 'lsrq_test', 'status': status,
                'status_details': {'requires_action': {'next_action': next_action}}, 'card': 'SECRET'})
            checkout = backend.create_checkout(offer, 'key')
            self.assertNotEqual(checkout.status, 'paid')
            self.assertEqual(checkout.provider_status, status)
            self.assertNotIn('SECRET', json.dumps(checkout.__dict__))
        self.assertEqual(checkout.required_action['resolution'], 'auto_resume')

    def test_previous_night_pending_request_remains_visible(self):
        class Pending:
            backend = 'link'
            def create_checkout(self, offer, key):
                return Checkout('lsrq_test', None, 'pending', cents(offer.price), 'usd', 'link', key)
        execute_purchase(self.state, Pending(), self.trip, get_offers(self.trip, 1, 0)[0], tick_time(1, 0))
        snapshot = {'night': 2, 'traces': [], 'escalations': []}
        refresh_escalations(snapshot, self.state)
        self.assertEqual(snapshot['escalations'][0]['trip_id'], self.trip.id)


if __name__ == '__main__': unittest.main()
