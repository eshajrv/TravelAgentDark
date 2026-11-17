# Flighthawk AI

An overnight travel desk for small teams. It finds trips in Slack and email, follows company policy, watches fares, and learns from each night through **Cognee**. Payments use **Stripe Link Agent Wallet**. A purchase decision, a spend request, a payment credential, and a confirmed flight booking are separate states.

Built at **Agents After Dark**, UC Berkeley Build Night (Nov 16, 2026). Current direction: **keep Cognee; remove Allowance**. Older virtual-card/payment sketches in the original planning documents are superseded. The runner uses the Link CLI for human-approved test payment credentials. Approval is not payment or booking. See the [Link quickstart](https://docs.link.com/quickstart/overview).

## Run Aman's dashboard

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-ui.txt
.venv/bin/python -m streamlit run app.py
```

If this checkout already has a virtual environment managed by uv, use `uv pip install --python .venv/bin/python -r requirements-ui.txt` instead. No credentials are needed for the dashboard. Run commands from the repository root.

The app starts in **Demo fixtures** mode. These are handwritten extracted trips, scripted decisions, and illustrative lessons, not an actual Cognee run. The workspace contains 20 Slack messages and five emails. The policy has ten named rules. Esha owns actual extraction and Cognee learning; Rohan owns the runner and Stripe integration.

Switch to **Runner output** and refresh to read `output/night_N.json`. The app never invokes the runner, memory, or payments. It never substitutes fixture trips or lessons when runner data is missing. `FLIGHTHAWK_OUTPUT_DIR` can point to another results directory (`REDEYE_OUTPUT_DIR` remains supported for existing setups).

## Data handoff

- Esha ingests `data/workspace.json` (`slack_messages`, `emails`) and `data/policy.md`. Message IDs preserve source evidence. Rohan's later unavailability in `s09` overrides the broad date window in `s08` and `e02`.
- Rohan is the sole writer of `output/night_N.json`. Write to a temporary file and atomically replace the final file so readers do not see partial JSON.
- The UI accepts a bare list of `dataclasses.asdict(Trace)` records or an envelope containing `traces`, optional `trips`, and optional `lessons: list[str]`. `decision` stays nested. Additional envelope fields are allowed.
- Trip exports use the existing `Trip` shape. An optional `output/trips.json` array supplies trip cards when the envelope omits them. Esha's `output/lessons.json` array of `{night, route, trip_id, lesson}` records supplies lessons for the selected night. `output/lessons_N.json` is also supported.
- Ticks are integers 0–31. Demo fixtures display 22:00–05:45 in 15-minute steps; runner output uses tick indices without inventing a wall-clock time. Invalid records produce a visible warning. Money is in USD.
- Versioned exports also supply observations, execution_events, bookings, metrics, and run/memory/payment status. The UI plots eligible observed lows and shows rejected offers separately. It copies only approved display fields from payment records; credential paths and raw CLI output are never retained.
- The Payments & bookings tab shows exported execution states and simulated replacement savings. Link approval is a credential state, not a completed purchase. Offline memory is labeled explicitly.
- An optional `team_budget: {budget, booked}` night summary supplies `Team budget: $booked of $budget used` in the on-screen and downloaded morning brief. Both amounts are USD. The final snapshot appears only at tick 31; missing values are not inferred from BUY decisions.
- Comparisons match trips with BUY decisions in both nights and count the first BUY once per trip. They are labeled selected-fare differences, not realized savings. Payment/booking outcomes must be confirmed independently by the runner.

## Memory integration

Esha’s memory layer is included on main. The runner calls `setup()` once before Night 1, `log_trace()` on every tick, and `end_night(n)` after each night. `recall_context(trip_id)` supplies policy, the $500 Link request limit, and learned lessons. Run only one Cognee script at a time. Install memory dependencies from `requirements.txt` separately from the UI dependencies; on macOS, an OpenSSL load error may require `brew install openssl@3`.

## Validation

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/make_demo_fixtures.py
```

The second command regenerates `demo/fixtures/` only. It never writes runner output. Do not run the legacy `test_cognee.py` as part of UI validation: it calls the live memory service and clears its dataset.

Coordination and milestone commits are posted in [GitHub issue #1](https://github.com/eshajrv/TravelAgentDark/issues/1). The original [build plan](BUILD_PLAN.md) and [team split](Flighthawk%20AI%20Team%20Split%20Esha,%20Rohan,%20Aman.md) provide project context; this README and the latest issue decisions govern the current payment scope.
