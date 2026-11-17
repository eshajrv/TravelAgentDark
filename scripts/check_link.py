"""Inspect an existing Link request through the adapter without displaying credentials.

Set LINK_AUTH_FILE if the wallet uses a non-default credential file.
Use --executable to select a locally installed link-cli binary.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from payments import LinkPayments

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('request_id')
parser.add_argument('--executable', default='link-cli')
args = parser.parse_args()
backend = LinkPayments(executable=args.executable)
# Status only: do not expand card details or create a second request.
result = backend._safe(backend._call(['spend-request', 'retrieve', args.request_id]))
print(json.dumps({k: result[k] for k in
    ('id', 'status', 'raw_status', 'approval_url', 'required_action')}, indent=2))
