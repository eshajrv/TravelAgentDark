"""Rohan's engine. Use --demo for offline fixtures; default memory is Esha's."""
import argparse
import asyncio
from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import importlib
import inspect
import json
from pathlib import Path
import re
import os

from agent import decide, eligibility_errors, evaluate_offer, OpenAITimingProvider
from demo_memory import DemoMemory
from execution_models import Checkout, Offer, tick_time, parse_time
from models import Trip, Trace, Decision
from output import write_snapshot, grade_snapshot
from payments import MockPayments, LinkPayments, get_backend
from sim.fares import get_offers
from state import State


def load_configuration():
    """Load the repo-local .env without overriding exported settings."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return  # Dependency-free offline fixture still works.
    load_dotenv(Path(__file__).resolve().parent / '.env', override=False)


def refresh_escalations(snapshot, state):
    booked = {b['trip_id'] for b in state.all('booking')}
    items = {}
    for trace in snapshot['traces']:
        if trace['decision']['action'] == 'ESCALATE' and trace['trip_id'] not in booked:
            items[trace['trip_id']] = {'trip_id': trace['trip_id'], 'reason': trace['decision']['reason']}
    for op in sorted(state.all('operation'), key=lambda op: (op['offer']['night'], op['offer']['tick'])):
        if op['offer']['night'] > snapshot['night']:
            continue
        tid = op['offer']['trip_id']
        if op['status'] in {'pending','unknown','creating','denied','expired','canceled','failed','requires_action','paid_unbooked'}:
            items[tid] = {'trip_id': tid, 'reason': 'Spend request ' + op['status'],
                          'approval_url': (op.get('checkout') or {}).get('url'),
                          'required_action': (op.get('checkout') or {}).get('required_action')}
        elif op['status'] in {'approved','booked','submitted','succeeded'}:
            items.pop(tid, None)
    snapshot['escalations'] = list(items.values())


async def call(fn, *args):
    value = fn(*args)
    return await value if inspect.isawaitable(value) else value


@contextmanager
def runner_lock(path):
    path = Path(str(path)+'.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another runner is using this state file') from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def execute_purchase(state, backend, trip, offer, now):
    # Defense in depth at the actual side-effect boundary.
    if eligibility_errors(trip, offer, now) or offer.price > min(trip.cap,500):
        raise ValueError('Payment blocked by policy recheck')
    existing = next((op for op in state.all('operation')
                     if op['offer']['id'] == offer.id and op['backend'] == backend.backend), None)
    if existing:
        # Crash recovery must not resubmit an ambiguous remote request.
        if existing['status'] == 'booked' or (backend.backend == 'link' and not existing['checkout']):
            return existing
    old = state.booking(trip.id)
    if old and backend.backend != 'mock':
        raise ValueError('Stripe replacement requires separate refund orchestration')
    if old and (now >= parse_time(old['free_cancel_until']) or offer.price >= old['price']):
        raise ValueError('Replacement must be cheaper and freely cancellable before payment')
    op = state.prepare(offer, backend.backend, trip)
    if op['status'] == 'booked':
        return op
    try:
        if op['checkout']:
            checkout = Checkout(**op['checkout'])
        else:
            checkout = backend.create_checkout(offer, op['id'])
            op = state.record_checkout(op['id'], checkout)
        if checkout.status == 'paid':
            op = state.finalize(op['id'], trip, now)
        return op
    except Exception as exc:
        state.record_error(op['id'], type(exc).__name__)
        raise


def event_from(op, trace_index):
    return {**op, 'trace_index': trace_index}


async def run_night_async(night, *, state, memory, backend, output_dir='output', seed=17,
                          decision_provider=decide, memory_mode='cognee_module'):
    tick_time(night,0)  # Validate night before any side effects.
    if hasattr(memory, 'configure_run'):
        await call(memory.configure_run, state.run_id, output_dir)
    if hasattr(memory, 'setup') and not state.get('memory_setup', 'done'):
        if night != 1:
            raise ValueError('Run Night 1 first so setup() runs once before extraction')
        await call(memory.setup)
        with state.transaction():
            state.put('memory_setup', 'done', {'completed': True})
    trips = await call(memory.get_trips)
    if not isinstance(trips,list) or not trips or not all(isinstance(t,Trip) for t in trips):
        raise ValueError('get_trips must return a nonempty list[Trip]')
    if len({t.id for t in trips}) != len(trips):
        raise ValueError('Trip IDs must be unique')
    identity = {'seed':seed,'payment_backend':backend.backend,'memory_mode':memory_mode,
                'trips':[asdict(t) for t in trips]}
    state.configure(identity)
    snapshot = state.get('night',night)
    if snapshot is None:
        snapshot = dict(schema_version=1,run_id=state.run_id,night=night,status='running',
                        mode='simulated_fares_and_bookings',payment_backend=backend.backend,
                        memory_mode=memory_mode,trips=[asdict(t) for t in trips],traces=[],lessons=[],
                        observations=[],execution_events=[],bookings=[],escalations=[],errors=[],
                        recalled_context=[],metrics={},next_tick=0)
    output_path = Path(output_dir)/f'night_{night}.json'
    if snapshot['status']=='completed':
        write_snapshot(output_path,snapshot)
        return snapshot

    def checkpoint():
        snapshot['bookings'] = state.all('booking')
        with state.transaction():
            state.put('night',night,snapshot)
        write_snapshot(output_path,snapshot)

    async def deliver_traces():
        # Sequential delivery per tick. A failed write is retried before any
        # later tick, independently of already persisted payment operations.
        for item in state.all('trace_outbox'):
            data = item['trace']
            if data['night'] != night or item['sent']:
                continue
            try:
                trace = Trace(**{**data, 'decision': Decision(**data['decision'])})
                await call(memory.log_trace, trace)
                with state.transaction():
                    state.put('trace_outbox', f"{night}:{data['tick']}:{data['trip_id']}", {**item, 'sent': True})
            except Exception as exc:
                snapshot['errors'].append({'component': 'log_trace', 'error': type(exc).__name__})
                snapshot['status'] = 'memory_failed'
                checkpoint()
                return False
        return True

    if not await deliver_traces():
        return snapshot

    for tick in range(snapshot['next_tick'],32):
        now = tick_time(night,tick)
        for trip in trips:
            if any(t['tick'] == tick and t['trip_id'] == trip.id for t in snapshot['traces']):
                continue  # A prior process checkpointed only part of this tick.
            offers = get_offers(trip,night,tick,seed)
            eligible = []
            for offer in offers:
                rejected = eligibility_errors(trip,offer,now)
                spending_rules = (['cap_escalation'] if offer.price > trip.cap else []) + (['link_request_cap'] if offer.price > 500 else [])
                snapshot['observations'].append({'offer':asdict(offer), 'eligible':not rejected and not spending_rules,
                                                 'rejection_rules':rejected + spending_rules})
                if not rejected:
                    eligible.append(offer)
            # One decision per trip/tick, but all rejected offers remain visible.
            offer = min(eligible or offers,key=lambda o:o.price) if offers else None
            if offer is None:
                snapshot['errors'].append({'trip_id':trip.id,'tick':tick,'component':'offers','error':'No offers/dates'})
                continue
            booking = state.booking(trip.id)
            pending = state.pending(trip.id)
            context = ''
            terminal = next((op for op in state.all('operation') if op['offer']['trip_id']==trip.id and op['status'] in {'denied','expired','canceled','failed'}),None)
            if terminal:
                decision = Decision('ESCALATE','Earlier request denied/expired; explicit retry authorization required',['approval_required'])
            elif pending:
                decision = Decision('WAIT','Existing checkout requires payment/reconciliation',['pending_checkout'])
            elif booking and booking['night']==night:
                decision = Decision('WAIT','Already booked this night; observing fares for hindsight',['already_booked'])
            else:
                try:
                    context = await call(memory.recall_context,trip.id)
                    if not isinstance(context,str):
                        raise ValueError('recall_context must return text')
                except Exception as exc:
                    snapshot['errors'].append({'trip_id':trip.id,'tick':tick,'component':'recall','error':type(exc).__name__})
                decision = evaluate_offer(trip,offer,context,now,booking,decision_provider)
                if decision.action=='BUY' and offer.price>500:
                    decision = Decision('ESCALATE','Fare exceeds Link $500 request cap',['link_request_cap'])
                if decision.action=='BUY' and booking and backend.backend!='mock':
                    decision = Decision('ESCALATE','Stripe replacement requires confirmed refund orchestration; retaining original booking',['replacement_requires_review'])
            intent_key = f'{night}:{tick}:{trip.id}'
            intent = state.get('decision_intent', intent_key)
            if intent:
                # Preserve the original BUY/rationale across a crash between
                # an external side effect and the following snapshot write.
                offer = Offer.from_dict(intent['offer'])
                decision = Decision(**intent['decision'])
                context = intent['context']
            else:
                with state.transaction():
                    state.put('decision_intent', intent_key, {'offer': asdict(offer),
                              'decision': asdict(decision), 'context': context})
            trace = Trace(night,tick,trip.id,offer.price,decision)
            trace_index = len(snapshot['traces'])
            snapshot['traces'].append(asdict(trace))
            if context:
                snapshot['recalled_context'].append({'trace_index':trace_index,'text':context})
            if decision.action=='BUY':
                try:
                    op = execute_purchase(state,backend,trip,offer,now)
                    snapshot['execution_events'].append(event_from(op,trace_index))
                except Exception as exc:
                    op = state.pending(trip.id)
                    if op:
                        snapshot['execution_events'].append(event_from(op,trace_index))
                    snapshot['errors'].append({'trip_id':trip.id,'tick':tick,'component':'payment','error':type(exc).__name__})
            # Persist a durable trace outbox separately from payment operations.
            with state.transaction():
                key = f'{night}:{tick}:{trip.id}'
                if not state.get('trace_outbox',key):
                    state.put('trace_outbox',key,{'trace':asdict(trace),'sent':False})
            checkpoint()
        snapshot['next_tick']=tick+1
        checkpoint()
        if not await deliver_traces():
            return snapshot

    # Recover execution evidence if a crash occurred after booking but before a tick export.
    known={e['id'] for e in snapshot['execution_events']}
    for op in state.all('operation'):
        if op['offer']['night']==night and op['id'] not in known:
            indices=[i for i,t in enumerate(snapshot['traces']) if t['trip_id']==op['offer']['trip_id'] and t['tick']==op['offer']['tick']]
            if indices:
                snapshot['execution_events'].append(event_from(op,indices[0]))
    grade_snapshot(snapshot)
    # Esha can read this evidence file or implement optional prepare_hindsight.
    snapshot['status']='grading'
    checkpoint()
    try:
        if hasattr(memory,'prepare_hindsight'):
            await call(memory.prepare_hindsight,snapshot)
        lessons = await call(memory.end_night,night)
        if not isinstance(lessons,list) or not all(isinstance(x,str) for x in lessons):
            raise ValueError('end_night must return list[str] lessons')
        snapshot['lessons']=lessons
        snapshot['status']='completed'
    except Exception as exc:
        snapshot['errors'].append({'component':'end_night','error':type(exc).__name__})
        snapshot['status']='learning_failed'
    refresh_escalations(snapshot,state)
    checkpoint()
    return snapshot


def run_night(night: int, *, memory=None, backend=None, state_path='output/engine.sqlite3',
              run_id='default', output_dir='output', seed=17, demo=False, decision_provider=decide) -> list[Trace]:
    """Synchronous contract; async callers should use run_night_async directly."""
    load_configuration()
    with runner_lock(state_path):
        state = State(state_path,run_id)
        try:
            memory = memory or (DemoMemory(state) if demo else importlib.import_module('memory'))
            snapshot = asyncio.run(run_night_async(night,state=state,memory=memory,
                backend=backend or get_backend(),
                output_dir=output_dir,seed=seed,decision_provider=decision_provider,
                memory_mode='offline_demo_fixture' if demo else 'cognee_module'))
            return [Trace(**{**t,'decision':Decision(**t['decision'])}) for t in snapshot['traces']]
        finally:
            state.close()


def reconcile(state, backend, output_dir):
    """Explicit server-side polling for this local test CLI, never trust redirect."""
    changed = []
    for op in state.all('operation'):
        if op['backend']!='link' or op['status']=='booked':
            continue
        if not op['checkout']:
            # Keep ambiguous creates blocked. Rerunning the original operation
            # is possible only with its durable idempotency key within retention.
            changed.append({'operation_id':op['id'],'status':'requires_manual_reconciliation'})
            continue
        try:
            checkout = backend.retrieve_checkout(op['checkout']['id'],op['id'],op['checkout']['amount_cents'])
            current = state.record_checkout(op['id'],checkout)
            if checkout.status=='paid':
                # Synthetic quotes are not live inventory. Verify again at the
                # original simulated tick; label the resulting booking simulated.
                offer = Offer.from_dict(op['offer'])
                current = state.finalize(op['id'],Trip(**op['trip']),tick_time(offer.night,offer.tick))
            changed.append({'operation_id':op['id'],'status':current['status']})
        except Exception as exc:
            changed.append({'operation_id':op['id'],'status':'reconciliation_error','error':type(exc).__name__})
    for snapshot in state.all('night'):
        for event in snapshot['execution_events']:
            op = state.get('operation',event['id'])
            event.update(op)
        snapshot['bookings']=state.all('booking')
        grade_snapshot(snapshot)
        refresh_escalations(snapshot,state)
        # Newly completed payments require fresh grading/learning on rerun.
        if any(x['status']=='booked' for x in changed):
            snapshot['status']='needs_regrading'
        with state.transaction():
            state.put('night',snapshot['night'],snapshot)
        write_snapshot(Path(output_dir)/f"night_{snapshot['night']}.json",snapshot)
    return changed


def main():
    load_configuration()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--night',type=int,default=1)
    parser.add_argument('--nights',type=int,nargs='+')
    parser.add_argument('--demo',action='store_true',help='Explicit offline memory fixture (not Cognee)')
    parser.add_argument('--memory-module',default='memory',help="Esha's Cognee-backed module")
    parser.add_argument('--payment-mode',choices=['mock','link'],default=os.getenv('PAYMENTS_BACKEND','mock'))
    parser.add_argument('--llm',action='store_true',help='Use OpenAI timing with LLM_API_KEY and LLM_MODEL')
    parser.add_argument('--decision-provider',help='Optional module:function timing provider returning Decision')
    parser.add_argument('--run-id',default='demo')
    parser.add_argument('--seed',type=int,default=17)
    parser.add_argument('--output-dir',default='output')
    parser.add_argument('--state-path')
    parser.add_argument('--reconcile',action='store_true')
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+',args.run_id):
        parser.error('run-id must contain letters, digits, _ or -')
    path=args.state_path or str(Path(args.output_dir)/'engine.sqlite3')
    backend=MockPayments() if args.payment_mode=='mock' else LinkPayments()
    with runner_lock(path):
        state=State(path,args.run_id)
        try:
            if args.reconcile:
                if args.payment_mode!='link':
                    parser.error('--reconcile requires --payment-mode link')
                print(json.dumps(reconcile(state,backend,args.output_dir),indent=2))
                return
            memory=DemoMemory(state) if args.demo else importlib.import_module(args.memory_module)
            provider=OpenAITimingProvider() if args.llm else decide
            if args.decision_provider:
                mod,name=args.decision_provider.split(':',1)
                provider=getattr(importlib.import_module(mod),name)
            for night in args.nights or [args.night]:
                snapshot=asyncio.run(run_night_async(night,state=state,memory=memory,backend=backend,
                    output_dir=args.output_dir,seed=args.seed,decision_provider=provider,
                    memory_mode='offline_demo_fixture' if args.demo else args.memory_module))
                print(json.dumps({'night':night,'status':snapshot['status'],'traces':len(snapshot['traces']),
                                  'payment_backend':backend.backend,'bookings':len(snapshot['bookings']),
                                  'output':str(Path(args.output_dir)/f'night_{night}.json')}))
                if snapshot['status']!='completed':
                    raise SystemExit(1)
        finally:
            state.close()


if __name__=='__main__':
    main()
