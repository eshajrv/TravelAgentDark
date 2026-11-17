# Rohan's engine verification — November 16, 2026

The fare simulator, guarded decisions, mock payments, and two-night runner pass offline acceptance. Native Cognee and Link service behavior is still unverified locally.

## Evidence

- `.venv/bin/python -m pytest tests -q`: **24 passed**.
- Full CLI acceptance: `run_night.py --demo --nights 1 2 --run-id acceptance-20261116 --output-dir output/acceptance-20261116`; both nights completed, 96 traces each, no runner errors.
- Esha: Night 1 simulated booking $412; eligible nightly low $287; $125 initial hindsight regret. Different Night 2: replacement $291, simulated full refund $412, $121 replacement savings.
- Rohan: December 3 rejected despite its cheaper $189 offer. Valid booking December 2; Night 2 simulated replacement saves $3.
- Priya: above-cap offers never reach payment; escalation remains in both digests.
- Total Night 2 simulated replacement savings: $124. Confirmed real flight savings: $0.
- Aman's `aman/product-demo` reader accepts both full exports without warnings, including additive observations/executions/bookings fields.
- Installed Cognee 1.6.8 exposes the expected remember/recall/improve signatures; this does not establish a successful service call.

## Integration and failure checks

Tests run Esha's actual `memory.py` against a fake Cognee service and deterministic timing provider. They verify setup once before Night 1, logging during each tick, unchanged public model shapes, current workspace keys, separate memory/UI files, scoped sessions, and Night 2 use of recalled lessons. No live LLM/Cognee inference is claimed.

Failure tests cover crash recovery immediately after booking, trace-write retry without a second purchase, ambiguous Link creation without resubmission, denied-request blocking, stale escalation removal after approval, free-cancellation checks before payment, missing-context rejection, hidden-city/date exclusions, and the $500 request limit. All ten documented Link lifecycle statuses retain their distinct provider state; approval and payment status never become flight confirmation. Sensitive card fields are excluded from exports.

## Remaining live validation

This checkout currently has no configured `LLM_API_KEY`/`OPENAI_API_KEY`, `LLM_MODEL`, or `LINK_MERCHANT_URL`, and `link-cli` is not installed. Therefore live trip extraction, Cognee learning/recall, LLM timing, and Link login/approval/credential retrieval were not run. No real flight purchase or refund was attempted.

Follow ENGINE.md after configuring local services. Use `--llm` with Esha's prose lessons; the offline deterministic baseline does not interpret prose. Only one Cognee script may run at a time. The runner handles setup and must not be launched alongside the standalone memory or live smoke scripts.

## Combined team integration and phone setup — November 16

Tested the engine with Esha's memory wrapper and Aman's dashboard in an isolated integration checkout. The initial combined suite passed 33 tests; actual two-night exports loaded in Streamlit AppTest with no exceptions at replay ticks 0, 12, 24 and 31. Selected totals were $677 and $553; simulated replacement savings were $124. The latest main/dashboard/branding changes were subsequently incorporated for a fresh test pass.

Link CLI 1.5.1 was installed locally. The user completed phone authorization: authenticated with userinfo:read and payment_methods.agentic scopes. The real Link adapter successfully created a $1 USD test-mode request and returned pending_approval plus its approval URL. This establishes successful authentication and request creation; final phone spend approval is tracked separately. No real purchase or charge was performed. Auth files and request records remain outside tracked source.

`scripts/check_link.py REQUEST_ID` checks an existing request through the adapter without expanding card data. Set LINK_AUTH_FILE and, if needed, --executable for your local installation. Wallet connection alone does not switch the dashboard from mock data to Link output.

### Phone approval verified

The user approved the $1 test request on their phone. Live retrieval through LinkPayments returned approved. An isolated integration harness attached that existing request to a synthetic $1 offer (no new request or airline search) and ran the real runner's reconcile() into SQLite and JSON, then loaded the export with Aman's read_night(). Results: approved execution, zero stale pending escalations, zero bookings, zero UI parser warnings. The adapter successfully retrieved a test credential into a private temporary file, which was deleted without reading its contents. No credential data entered exports or source control. This verifies phone authentication, test request creation, approval, credential retrieval and the runner/UI approval handoff. It does not establish merchant payment, flight booking, or live Cognee learning. Latest combined offline suite: 35 tests plus 6 subtests pass.
