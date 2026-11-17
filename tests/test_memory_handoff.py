"""Exercise Esha's actual wrapper with a fake Cognee service, never live APIs."""
import asyncio
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from agent import decide
from demo_memory import DemoMemory
from models import Decision, Trace
from payments import MockPayments
from run_night import run_night_async
from state import State


class MemoryHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calls = []
        cls.extracted = [asdict(t) for t in DemoMemory(None).get_trips()]
        async def remember(text, **kwargs):
            cls.calls.append(('remember', text, kwargs))
        async def recall(question, **kwargs):
            cls.calls.append(('recall', question, kwargs))
            if 'extracting upcoming work trips' in question:
                return json.dumps(cls.extracted)
            return 'Economy only; obey dates, trip cap and $500 Link limit.'
        async def improve(**kwargs):
            cls.calls.append(('improve', '', kwargs))
        fake = types.SimpleNamespace(remember=remember, recall=recall, improve=improve)
        dotenv = types.SimpleNamespace(load_dotenv=lambda *a, **kw: None)
        spec = importlib.util.spec_from_file_location('memory_handoff_fixture', Path(__file__).parents[1] / 'memory.py')
        cls.memory = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'cognee': fake, 'dotenv': dotenv}):
            spec.loader.exec_module(cls.memory)

    @classmethod
    def tearDownClass(cls):
        cls.memory._loop.call_soon_threadsafe(cls.memory._loop.stop)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        self.state = State(self.path / 'engine.db', 'handoff')
        self.memory.configure_run('handoff', self.path)
        self.calls.clear()

    def tearDown(self):
        self.state.close()
        self.tmp.cleanup()

    def test_current_workspace_ingestion(self):
        text = self.memory._workspace_text(self.memory._workspace())
        self.assertIn('s09', text)
        self.assertIn('e02', text)
        self.assertIn('not the 3rd', text)
        legacy = self.memory._workspace_text({'slack': [{'user': 'Rohan', 'text': 'SFO to ORD'}]})
        self.assertIn('Rohan: SFO to ORD', legacy)

    def test_log_trace_deduplicates_without_overwriting_runner(self):
        export = self.path / 'night_1.json'
        export.write_text('{"runner_owned": true}')
        trace = Trace(1, 0, 'esha_sfo_jfk', 412, Decision('BUY', 'Under cap', ['trip_cap']))
        self.memory.log_trace(trace)
        self.memory.log_trace(trace)
        self.assertEqual(json.loads(export.read_text()), {'runner_owned': True})
        self.assertEqual(len(self.memory._load_night(1)), 1)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][2]['session_id'], 'handoff:night_1')

    def test_two_night_native_contract_and_setup_once(self):
        def timing(trip, price, context):
            # Deterministic test double for the optional prose-reading LLM.
            if 'Try waiting for a comparable fare' in context and price > 301.35:
                return Decision('WAIT', 'Recalled observed target', ['recalled_timing_lesson'])
            return decide(trip, price, context)
        def run(n):
            return asyncio.run(run_night_async(n, state=self.state, memory=self.memory,
                backend=MockPayments(), output_dir=self.path, decision_provider=timing))
        one = run(1)
        two = run(2)
        self.assertEqual((one['status'], two['status']), ('completed', 'completed'))
        self.assertEqual(len(one['traces']), 96)
        self.assertEqual(len(two['traces']), 96)
        setups = [c for c in self.calls if c[0] == 'remember' and c[1].startswith('Team workspace messages')]
        self.assertEqual(len(setups), 1)
        self.assertEqual(len(self.memory._load_night(1)), 96)
        self.assertEqual(len(self.memory._load_night(2)), 96)
        self.assertEqual(self.state.booking('esha_sfo_jfk')['price'], 291)
        self.assertTrue(any(t['decision']['action'] == 'WAIT' and 'recalled_timing_lesson' in t['decision']['rules_used'] for t in two['traces']))
        self.assertEqual(self.state.booking('esha_sfo_jfk')['replacement_savings'], 121)
        self.assertEqual(two['metrics']['simulated_replacement_savings'], 124)
        self.assertTrue(any(e['trip_id'] == 'priya_bos_sfo' for e in two['escalations']))
        # The first tick was logged before the next trip's context was recalled.
        first_log = next(i for i,c in enumerate(self.calls) if c[0] == 'remember' and '(tick 0)' in c[1])
        next_recall = next(i for i,c in enumerate(self.calls) if i > first_log and c[0] == 'recall')
        last_log = max(i for i,c in enumerate(self.calls) if c[0] == 'remember' and '(tick 31)' in c[1])
        self.assertLess(next_recall, last_log)
        self.assertEqual(json.loads((self.path / 'night_1.json').read_text())['schema_version'], 1)
        calls = len(self.calls)
        run(2)
        self.assertEqual(len(self.calls), calls)

    def test_pending_buy_and_invalid_fare_do_not_become_purchase_regret(self):
        from execution_models import Checkout, cents
        class Pending:
            backend = 'link'
            def create_checkout(self, offer, key):
                return Checkout('lsrq_' + key[:12], None, 'pending', cents(offer.price), 'usd', 'link', key)
        result = asyncio.run(run_night_async(1, state=self.state, memory=self.memory,
            backend=Pending(), output_dir=self.path))
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(result['bookings'])
        self.assertTrue(all(t['regret'] is None for t in result['traces']))
        self.assertTrue(all('simulated booking at' not in lesson for lesson in result['lessons']))
        self.assertTrue(any('no policy-eligible fare' in s for s in result['lessons']))
        self.assertGreater(result['metrics']['eligible_hindsight_min']['rohan_sfo_ord'], 189)


if __name__ == '__main__':
    unittest.main()
