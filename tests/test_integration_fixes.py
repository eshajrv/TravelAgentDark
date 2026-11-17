import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from execution_models import Checkout, cents, tick_time
from payments import MockPayments
from run_night import load_configuration, reconcile, execute_purchase, run_night_async
from demo_memory import DemoMemory
from sim.fares import get_offers
from state import State

class IntegrationFixTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)
        self.state=State(self.path/'state.db','test');self.memory=DemoMemory(self.state)
    def tearDown(self):self.state.close();self.tmp.cleanup()
    def test_dotenv_load_preserves_exported_settings(self):
        (self.path/'.env').write_text('PAYMENTS_BACKEND=link\nLLM_MODEL=fixture-model\n')
        with patch('run_night.__file__',str(self.path/'run_night.py')), patch.dict(os.environ,{'PAYMENTS_BACKEND':'mock'},clear=True):
            load_configuration()
            self.assertEqual(os.environ['PAYMENTS_BACKEND'],'mock')
            self.assertEqual(os.environ['LLM_MODEL'],'fixture-model')
    def test_reconcile_clears_stale_pending_escalation(self):
        class Pending:
            backend='link'
            def create_checkout(self,offer,key):return Checkout('lsrq_test','https://app.link.com/test','pending',cents(offer.price),'usd','link',key)
            def retrieve_checkout(self,rid,key,amount):return Checkout(rid,None,'approved',amount,'usd','link',key)
        trip=self.memory.get_trips()[0];offer=get_offers(trip,1,0)[0]
        op=execute_purchase(self.state,Pending(),trip,offer,tick_time(1,0))
        snapshot={'night':1,'status':'completed','execution_events':[{**op,'trace_index':0}], 'traces':[], 'observations':[], 'bookings':[], 'escalations':[{'trip_id':trip.id,'reason':'pending'}]}
        with self.state.transaction():self.state.put('night',1,snapshot)
        reconcile(self.state,Pending(),self.path)
        result=self.state.get('night',1)
        self.assertEqual(result['escalations'],[])
        self.assertEqual(result['execution_events'][0]['status'],'approved')
        self.assertEqual(result['bookings'],[])
    def test_denial_does_not_trigger_new_request(self):
        class Denied:
            backend='link'
            def __init__(self):self.count=0
            def create_checkout(self,offer,key):
                self.count+=1
                return Checkout('lsrq_denied',None,'denied',cents(offer.price),'usd','link',key)
        backend=Denied()
        snapshot=asyncio.run(run_night_async(1,state=self.state,memory=self.memory,backend=backend,output_dir=self.path))
        self.assertEqual(backend.count,2)
        self.assertEqual(len(snapshot['bookings']),0)
        self.assertEqual(len(snapshot['escalations']),3)
    def test_async_memory_contract(self):
        wrapped=self.memory
        class AsyncMemory:
            async def get_trips(self):return wrapped.get_trips()
            async def recall_context(self,key):return wrapped.recall_context(key)
            async def log_trace(self,trace):wrapped.log_trace(trace)
            async def prepare_hindsight(self,snapshot):wrapped.prepare_hindsight(snapshot)
            async def end_night(self,night):return wrapped.end_night(night)
        snapshot=asyncio.run(run_night_async(1,state=self.state,memory=AsyncMemory(),backend=MockPayments(),output_dir=self.path))
        self.assertEqual(snapshot['status'],'completed')
        self.assertTrue(snapshot['lessons'])
