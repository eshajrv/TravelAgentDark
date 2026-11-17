"""Link Agent Wallet spend requests. Test credentials only; never purchases."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid
from execution_models import Checkout, cents

class PaymentError(RuntimeError):
    pass

class MockPayments:
    backend = 'mock'
    def __init__(self):
        self.requests = {}
    def request_payment(self, amount, merchant, reason, *, operation_id=None):
        if cents(amount)>50000:
            raise PaymentError('Link project limit is $500')
        key='mock_'+(operation_id or uuid.uuid4().hex)
        self.requests[key]={'id':key,'approval_url':None,'status':'approved','card_file':None,'simulated':True}
        return self.requests[key].copy()
    def get_payment(self, request_id):
        return self.requests[request_id].copy()
    def create_checkout(self, offer, operation_id):
        result=self.request_payment(offer.price,offer.merchant,'Offline simulated booking',operation_id=operation_id)
        return Checkout(result['id'],None,'paid',cents(offer.price),'usd',self.backend,operation_id)

class LinkPayments:
    backend = 'link'
    def __init__(self, *, executable='link-cli', merchant_url=None, card_dir=None, executor=None):
        self.executable=executable
        self.merchant_url=merchant_url or os.getenv('LINK_MERCHANT_URL','')
        self.card_dir=Path(card_dir or tempfile.mkdtemp(prefix='redeye-link-'))
        self.card_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.executor=executor or subprocess.run
    def _call(self,args):
        try:
            proc=self.executor([self.executable]+args+['--format','json'],capture_output=True,text=True,timeout=30)
        except (OSError,subprocess.TimeoutExpired):
            raise PaymentError('Link CLI unavailable or request unresolved; do not create a duplicate') from None
        if proc.returncode:
            raise PaymentError('Link CLI failed; inspect status locally without logging credentials')
        try:
            data=json.loads(proc.stdout)
            if isinstance(data,list) and len(data)==1: data=data[0]
            if not isinstance(data,dict): raise ValueError()
            return data
        except (ValueError,TypeError):
            raise PaymentError('Invalid Link CLI JSON') from None
    def _safe(self,data):
        rid=data.get('id','')
        if not re.fullmatch(r'lsrq_[A-Za-z0-9_]+',rid): raise PaymentError('Invalid spend request ID')
        raw=data.get('status')
        statuses={'created':'pending','pending_approval':'pending','approved':'approved','denied':'denied',
                  'expired':'expired','canceled':'canceled','requires_action':'requires_action',
                  'failed':'failed','submitted':'submitted','succeeded':'succeeded'}
        if raw not in statuses: raise PaymentError('Unknown Link request state')
        action = ((data.get('status_details') or {}).get('requires_action') or {}).get('next_action')
        safe_action = {k: action[k] for k in ('type','resolution','display_message','action_url','expires_at')
                       if k in action} if isinstance(action,dict) else None
        return {'id':rid,'approval_url':data.get('approval_url'),'status':statuses[raw], 'raw_status':raw,
                'required_action':safe_action,'card_file':None,'test_mode':True}
    def request_payment(self,amount,merchant,reason,*,operation_id=None):
        value=cents(amount)
        if value>50000: raise PaymentError('Link project limit is $500')
        if not self.merchant_url.startswith('https://'): raise PaymentError('Set LINK_MERCHANT_URL to the actual merchant HTTPS URL')
        context=f'Red-Eye TEST ONLY: {reason}. Requesting a test credential for a simulated flight. No real booking or purchase will be made.'
        args=['spend-request','create','--test','--merchant-name',merchant,'--merchant-url',self.merchant_url,'--context',context,'--amount',str(value),'--currency','usd','--idempotency-key',operation_id or uuid.uuid4().hex]
        return self._safe(self._call(args))
    def get_payment(self,request_id):
        if not re.fullmatch(r'lsrq_[A-Za-z0-9_]+',request_id): raise PaymentError('Invalid request ID')
        result=self._safe(self._call(['spend-request','retrieve',request_id]))
        if result['status']=='approved':
            path=self.card_dir/(request_id+'.card.json')
            if not path.exists():
                # Never open the file or include the CLI's raw response in logs.
                self._call(['spend-request','retrieve',request_id,'--include','card','--output-file',str(path)])
            if path.exists():
                path.chmod(0o600)
                result['card_file']=str(path)
        return result
    def create_checkout(self,offer,operation_id):
        r=self.request_payment(offer.price,offer.merchant,f'{offer.origin} to {offer.dest}, {offer.travel_date}, fare ${offer.price:.2f}',operation_id=operation_id)
        return Checkout(r['id'],r['approval_url'],r['status'],cents(offer.price),'usd',self.backend,operation_id,
                        r['raw_status'],r['required_action'])
    def retrieve_checkout(self,request_id,operation_id,amount):
        r=self.get_payment(request_id)
        return Checkout(r['id'],r['approval_url'],r['status'],amount,'usd',self.backend,operation_id,
                        r['raw_status'],r['required_action'])

def get_backend():
    name=os.getenv('PAYMENTS_BACKEND','mock')
    if name=='mock': return MockPayments()
    if name=='link': return LinkPayments()
    raise PaymentError('PAYMENTS_BACKEND must be mock or link')

_default=None
def request_payment(amount,merchant,reason):
    global _default
    if _default is None: _default=get_backend()
    return _default.request_payment(amount,merchant,reason)
def get_payment(request_id):
    if _default is None: raise PaymentError('No payment backend initialized')
    return _default.get_payment(request_id)
