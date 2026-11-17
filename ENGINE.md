# Rohan's night engine

Cognee stays. Native runs use Esha's `memory.py`; `--demo` is an explicitly labeled offline memory fixture. Fares, bookings and refunds are simulated. Neither mode purchases a real flight.

## Offline acceptance run

```sh
.venv/bin/python run_night.py --demo --nights 1 2 --run-id acceptance --output-dir output/acceptance
.venv/bin/python -m pytest tests -q
```

Use a new run ID **and output directory** for a clean experiment. SQLite preserves bookings and lessons between nights; repeating a completed night returns the saved output. Seeds determine fares, not LLM responses.

The deterministic fixture buys Esha at $412 on Night 1, observes an eligible $287 low, then recalls a trial target and replaces at $291 on a different Night 2. Her simulated full refund is $412 and replacement savings is $121. Rohan's forbidden December 3 fare is rejected; Priya stays above cap and escalates. These are synthetic results, not measured travel savings or a reliable fare trend.

## Esha's memory handoff

The agreed public imports remain:

```python
from memory import setup, get_trips, recall_context, log_trace, end_night
```

The runner calls `setup()` once before Night 1, records its successful completion in SQLite, then calls `get_trips()`. Each tick recalls policy/lessons for trips needing a decision and sends each trip's trace through `log_trace()`, sequentially. At the end it calls `end_night(n)`. A failed trace write stops progress and is retried before a later tick without repeating a payment. No automatic reset or `forget()` occurs.

Optional additive handoffs are implemented: `configure_run(run_id, output_dir)` selects local caches and run-scoped Cognee session IDs; `prepare_hindsight(snapshot)` supplies eligible offers and confirmed simulated execution evidence before grading. No existing Trip/Decision/Trace fields or public function signatures changed.

The runner alone owns `output_dir/night_N.json`. Memory uses `output_dir/.memory/traces_N.json`, `hindsight_N.json`, and `lessons.json`. Trace retries deduplicate by night/tick/trip; a crash after Cognee accepts a write but before the local acknowledgement can still redeliver that external write. Aman's current `slack_messages`/`emails` and Esha's older `slack`/`email` input keys are both accepted. Tick 0 is 22:00 Pacific in the engine, memory, and dashboard.

**Only run one Cognee script at a time.** Do not run `memory.py`, `try_memory.py`, the native runner or the live preflight concurrently.

## Native Cognee and decision LLM

The local Python 3.12 environment has Cognee 1.6.8. `requirements-engine.lock.txt` records installed engine/test versions for macOS arm64. Configure the team's `LLM_API_KEY` and `LLM_MODEL` in the local `.env` (exported environment variables take precedence); never commit keys.

```sh
.venv/bin/python scripts/check_cognee.py
.venv/bin/python run_night.py --memory-module memory --llm --payment-mode mock --nights 1 2 --run-id cognee-check --output-dir output/cognee-check
```

The first command only checks imports and function signatures. `scripts/check_cognee.py --run` is an optional service smoke test using a unique dataset, without deleting memory. The runner automatically handles setup; do not separately run a reset.

Use `--llm` for native Cognee prose lessons. Without it, the deterministic baseline buys eligible under-cap fares and recognizes only JSON `timing_rule` targets; it does not interpret Esha's prose. `--decision-provider module:function` can inject another timing provider. Code always checks dates, itinerary, cap, quote expiry, and free cancellation before payment. The $500 Link request limit applies alongside trip caps.

Live model calls, extraction quality, Cognee service learning and Link approval remain unverified locally: no model key/model, merchant URL or Link CLI is configured. Tests exercise Esha's actual wrapper against a fake Cognee service and a deterministic timing provider; that is interface evidence, not a live learning claim.

## Link Agent Wallet payments

`MockPayments` and `LinkPayments` preserve `request_payment(amount, merchant, reason)` and `get_payment(request_id)`. Set `PAYMENTS_BACKEND=mock|link`, or use CLI `--payment-mode`. `--demo` selects fixture memory; payment backend selection remains explicit and consistent in the Python and CLI entry points.

Install and authenticate the official `@stripe/link-cli` separately and set `LINK_MERCHANT_URL` to the actual merchant HTTPS URL. Link mode always uses `--test`, a durable idempotency key, and the $500 request cap.

```sh
.venv/bin/python run_night.py --demo --payment-mode link --night 1 --run-id link-check --output-dir output/link-check
.venv/bin/python run_night.py --payment-mode link --reconcile --run-id link-check --output-dir output/link-check
```

Pending requests expose an approval URL. `requires_action` retains the provider's resolution/message/action URL for human follow-up. Approved credentials, submitted payments, and succeeded payment statuses remain distinct and never become a flight booking. Denied/expired/canceled/failed requests require explicit retry authorization. Unknown creates remain blocked for manual reconciliation instead of being automatically resubmitted.

Reconciliation retrieves approved test credentials via `--output-file` into a protected temporary directory; it never reads the credential file, logs raw CLI output, sends the card to a merchant, or confirms a flight. Delete the private temporary credential file after the demonstration. `card_file` is returned only by the direct payment API and is excluded from engine JSON.

Official references: [CLI](https://docs.link.com/cli/reference), [request lifecycle](https://docs.link.com/concepts/spend-requests), [quickstart](https://docs.link.com/quickstart/overview). The approval window is currently 30 minutes; use provider status and returned expiry values.

## Exports and recovery

Versioned exports retain nested decisions and trips/traces/lessons, plus observations, execution_events, bookings, recalled_context, errors, escalations and metrics. `booked` means a confirmed **simulated** booking. Only those executions receive purchase regret. Forbidden dates and otherwise ineligible offers are excluded from eligible minima; unapproved BUY proposals cannot generate purchase regret or booking savings.

Night 2 retains Night 1's booking and uses different fares. Mock replacement checks free cancellation and a cheaper total before issuing payment, then atomically records full refund and replacement in SQLite. Failed replacement preserves the original. Link mode has no remote booking/refund orchestration.

One runner holds the state-file lock. Durable decision intents preserve the original decision across a crash after booking; per-trip checkpoints and the trace outbox prevent duplicate trip/tick rows and repeated purchases on resume. Exports are written atomically. Jinko remains deferred.
