# Rohan's night engine

Cognee stays; production imports Esha's `memory` module. `--demo` is explicitly an offline fixture, not evidence of Cognee integration. No real flight purchase occurs in either mode.

## Offline run

```sh
python3 run_night.py --demo --nights 1 2 --run-id demo --output-dir output
python3 -m unittest discover -s tests -v
```

Use a new run ID and output directory for a clean experiment. SQLite retains bookings and lessons between nights. Repeating a completed night returns its saved output. Seeds control fares, not LLM responses. Engine tests run without third-party dependencies (including on Python 3.9); use the team's Python 3.10+ environment for Cognee.

## Cognee and LLM integration

Esha's module supplies `get_trips()`, `recall_context(trip_id)`, `log_trace(trace)`, `end_night(night)`. Sync and async implementations are accepted. An optional `prepare_hindsight(snapshot)` receives eligible observations and confirmed simulated executions before improvement; the same evidence is written to `output/night_N.json` before end_night runs. The function returns `list[str]` lessons. Existing shared models remain unchanged.

```sh
python3 run_night.py --memory-module memory --llm --night 1
```

Set `LLM_API_KEY` (or `OPENAI_API_KEY`) and `LLM_MODEL`. `--llm` uses the OpenAI SDK already in requirements.txt and interprets recalled Cognee prose. Without it, the deterministic timing baseline recognizes JSON context containing `timing_rule: {target_price, lesson}`; plain prose without a structured target produces an under-cap baseline buy. An injected `--decision-provider module:function` can replace timing. Hard checks always run before a payment request.

## Link Agent Wallet, not Stripe Checkout

The backend matches models.py: `MockPayments` and `LinkPayments` expose `request_payment(amount, merchant, reason)` and `get_payment(request_id)`. `PAYMENTS_BACKEND=mock|link` chooses it; CLI `--payment-mode` overrides it. Mock approval and booking are synthetic.

Install and authenticate the official `@stripe/link-cli` separately. Set `LINK_MERCHANT_URL` to the actual merchant URL. Run:

```sh
PAYMENTS_BACKEND=link python3 run_night.py --demo --night 1
PAYMENTS_BACKEND=link python3 run_night.py --reconcile
```

The Link adapter always passes `--test`, uses an idempotency key, enforces the $500 project cap and returns the approval URL. Approval does not mean payment or booking. Reconciliation polls existing request IDs and retrieves approved test credentials with `--output-file` into a protected temporary directory. It never opens that file, logs raw CLI output, submits the card to a merchant, or confirms a real booking. Live wallet authentication/approval was not exercised during offline tests.

Credentials remain in the private temp directory for the operator; remove them after the demonstration. `card_file` is only returned by direct get_payment, never copied into engine JSON. Pending requests become morning escalation items. Unknown creates are blocked for manual reconciliation instead of being retried with a new key. Denied/expired requests are not automatically resubmitted during the same run.

Official references: https://docs.link.com/quickstart/overview and https://docs.link.com/cli/reference . Current docs specify a 30-minute approval window; trust provider status rather than the older plan's 10-minute claim.

## Outputs and limits

`examples/engine_output.json` is a shortened mock example for Aman. Full outputs contain existing trips/traces/lessons plus observations, execution_events, bookings, recalled_context, errors, escalations, and metrics. BUY is a decision; execution status `booked` represents a **simulated** booking only. `approved` on Link is a credential state, never a booking. No shared team budget is enforced; trip caps and the Link $500 cap both apply.

Night 2 uses new fares and retains Night 1 bookings. Mock replacement atomically refunds/replaces only while free cancellation remains valid. Link mode never performs remote refunds or purchases. Hindsight excludes invalid offers and unpaid decisions. First-night lows are observations, not proof of a reliable route trend.

One process holds the state lock. External memory logging is at-least-once across a crash at the acknowledgement boundary; Esha should deduplicate by night/tick/trip. Payment operations have separate durable keys. The engine batches Cognee trace delivery after observation ticks; UI snapshots are written every tick. Native Cognee integration awaits Esha's module and API configuration. Optional Jinko is intentionally deferred.
