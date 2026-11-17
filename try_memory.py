"""Run the real two-night memory/engine check, using mock payments.

Replaces the legacy fake-fare script, which reset the entire Cognee graph.
Configure LLM_API_KEY and LLM_MODEL first. Only run one Cognee script at a time.
Additional run_night.py arguments may be supplied, e.g. a fresh --run-id and
--output-dir. Setup runs once through the runner; no reset is performed.
"""
from pathlib import Path
import subprocess
import sys

if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    command = [sys.executable, str(root / 'run_night.py'), '--memory-module', 'memory',
               '--llm', '--payment-mode', 'mock', '--nights', '1', '2',
               '--run-id', 'cognee-check', '--output-dir', str(root / 'output' / 'cognee-check')]
    raise SystemExit(subprocess.call(command + sys.argv[1:]))
