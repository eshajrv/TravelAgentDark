"""Check installed APIs; --run uses a unique dataset and never deletes memory."""
import argparse
import asyncio
import importlib.metadata
import inspect
import os
from pathlib import Path
import sys
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run_night import load_configuration

async def smoke(cognee):
    dataset='redeye_smoke_'+uuid.uuid4().hex
    session='night_1'
    print('Isolated dataset:',dataset)
    await cognee.remember('Tier A conference economy fare cap is $600.',dataset_name=dataset,self_improvement=False)
    await cognee.remember('Observed simulated SFO-JFK buy $412; eligible nightly low $287; regret $125. One observation only.',dataset_name=dataset,session_id=session,self_improvement=False)
    question='What is the cap and what timing lesson is supported by the observed night?'
    before=await cognee.recall(question,datasets=[dataset])
    await cognee.improve(dataset=dataset,session_ids=[session])
    after=await cognee.recall(question,datasets=[dataset])
    print('BEFORE:',before)
    print('AFTER:',after)
    print('Inspect the answers for a supported change; successful calls alone do not prove learning.')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true',help='Call configured LLM/embedding services; may incur API charges')
    args=parser.parse_args()
    load_configuration()
    import cognee
    print('Cognee:',importlib.metadata.version('cognee'))
    checks={'remember':['dataset_name','session_id','self_improvement'],'recall':['datasets'],'improve':['dataset','session_ids']}
    for name,parameters in checks.items():
        signature=inspect.signature(getattr(cognee,name))
        missing=set(parameters)-set(signature.parameters)
        if missing:raise RuntimeError(f'{name} missing parameters {missing}')
        print(name,'API compatible')
    print('LLM_API_KEY configured:',bool(os.getenv('LLM_API_KEY')))
    print('No memory deletion performed.')
    if args.run:
        if not os.getenv('LLM_API_KEY') and not os.getenv('OPENAI_API_KEY'):
            parser.error('Configure local LLM_API_KEY before the OpenAI-backed smoke test')
        asyncio.run(smoke(cognee))
if __name__=='__main__':main()
