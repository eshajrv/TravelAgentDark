import asyncio
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from agent import evaluate_offer
from demo_memory import DemoMemory
from execution_models import tick_time
from models import Decision
from payments import MockPayments, LinkPayments, PaymentError
from run_night import run_night_async, execute_purchase
from sim.fares import get_offers
from state import State

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.state=State(Path(self.tmp.name)/'state.db','test')
        self.memory=DemoMemory(self.state)
        self.trip=self.memory.get_trips()[0]
    def tearDown(self):
        self.state.close();self.tmp.cleanup()
    def test_deterministic_and_different_nights(self):
        first=get_offers(self.trip,1,0)
        get_offers(self.trip,2,4)
        self.assertEqual(first,get_offers(self.trip,1,0))
        self.assertNotEqual(first[0].price,get_offers(self.trip,2,0)[0].price)
    def test_guards_override_provider(self):
        trip=self.memory.get_trips()[1]
        bad=next(o for o in get_offers(trip,1,0) if o.travel_date in trip.banned_dates)
        provider=lambda *args:Decision('BUY','Buy',[])
        self.assertEqual(evaluate_offer(trip,bad,'rules',tick_time(1,0),provider=provider).action,'WAIT')
        offer=get_offers(self.trip,1,0)[0]
        self.assertEqual(evaluate_offer(self.trip,replace(offer,skip_segment=True),'rules',tick_time(1,0),provider=provider).action,'WAIT')
    def test_two_nights_and_repeat(self):
        def run(n):
            return asyncio.run(run_night_async(n,state=self.state,memory=self.memory,backend=MockPayments(),output_dir=self.tmp.name,memory_mode='offline_demo_fixture'))
        one=run(1);two=run(2)
        self.assertEqual(len(one['traces']),96)
        self.assertEqual(len(two['traces']),96)
        booking=self.state.booking(self.trip.id)
        self.assertLess(booking['price'],412)
        self.assertGreater(booking['simulated_refund'],0)
        self.assertTrue(two['lessons'] or self.state.get('lesson',self.trip.id))
        self.assertTrue(any(e['trip_id']=='priya_bos_sfo' for e in two['escalations']))
        self.assertTrue(all(b['travel_date']!='2026-12-03' for b in two['bookings']))
        count=len(self.state.all('operation'));run(2)
        self.assertEqual(count,len(self.state.all('operation')))
    def test_duplicate_execution(self):
        offer=get_offers(self.trip,1,0)[0]
        a=execute_purchase(self.state,MockPayments(),self.trip,offer,tick_time(1,0))
        b=execute_purchase(self.state,MockPayments(),self.trip,offer,tick_time(1,0))
        self.assertEqual(a['booking_id'],b['booking_id'])
        self.assertEqual(len(self.state.all('operation')),1)
    def test_expired_cancellation(self):
        offer=get_offers(self.trip,2,24)[0]
        decision=evaluate_offer(self.trip,offer,'rules',tick_time(2,24),{'price':412,'free_cancel_until':tick_time(1,0).isoformat()})
        self.assertEqual(decision.action,'WAIT')
    def test_link_cap(self):
        with self.assertRaises(PaymentError):MockPayments().request_payment(501,'air','reason')
    def test_link_cli_contract_and_redaction(self):
        calls=[]
        class Result:
            returncode=0
            stdout=json.dumps({'id':'lsrq_123','status':'pending_approval','approval_url':'https://app.link.com/test','card':{'number':'SECRET'}})
        def execute(args,**kwargs):calls.append(args);return Result()
        backend=LinkPayments(merchant_url='https://air.example',card_dir=self.tmp.name,executor=execute)
        result=backend.request_payment(291,'Air','Test',operation_id='operation')
        self.assertEqual(result['status'],'pending')
        self.assertNotIn('SECRET',json.dumps(result))
        self.assertIn('--test',calls[0]);self.assertIn('--idempotency-key',calls[0])
        self.assertEqual(calls[0][calls[0].index('--amount')+1],'29100')
    def test_pending_is_not_booking(self):
        from execution_models import Checkout,cents
        class Pending:
            backend='link'
            def create_checkout(self,offer,key):return Checkout('lsrq_test','https://app.link.com/test','pending',cents(offer.price),'usd','link',key)
        offer=get_offers(self.trip,1,0)[0]
        result=execute_purchase(self.state,Pending(),self.trip,offer,tick_time(1,0))
        self.assertEqual(result['status'],'pending');self.assertIsNone(self.state.booking(self.trip.id))

if __name__=='__main__':unittest.main()
