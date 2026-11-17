# Flighthawk AI — Build Plan

**Agents After Dark Build Night · Berkeley Haas · Nov 16, 2026 (4:00–9:00 PM)**
Prize targets: **Best Use of Cognee** (primary), **Best Overall**.

> Flighthawk AI is an overnight travel agent for teams too small to have a travel person.
> It reads the team's Slack and email for upcoming work trips, watches fares all night,
> checks every fare against company policy stored in **Cognee**, and pays with a
> single-use card through **Stripe Link** after a human approves on their phone. Every
> decision is logged, and `cognee.improve()` turns those logs into lessons so the next
> night's agent is smarter.

The product name is **Flighthawk AI**.

---

## 0. Final stack and priority order

| Layer | Choice | Notes |
|---|---|---|
| **Memory** | **Cognee** | Rules, workspace facts and the learning loop. Our main prize target. |
| **Payments** | **Stripe Link CLI** (`@stripe/link-cli`) | Replaces Allowance (the Allowance founder recommended it). No Allowance code. `MockPayments` is the default. |
| **Overnight fares** | Seeded simulator (`sim/fares.py`) | The source for the Night 1 / Night 2 demo. |
| **Real prices** | Jinko travel API (MCP at `https://mcp.gojinko.com`) | **Optional.** One real search per trip to set the simulator's base price. Add only after everything else works. |
| **AI model** | One OpenAI key | `LLM_API_KEY` in `.env`, shared by Cognee and the agent. |
| **UI** | Streamlit | `app.py` |

**Priority order:**

1. **Must work:** the Cognee loop (`remember` → `improve` → `recall`) + simulator + agent + **fake payment**. This alone is a complete demo.
2. **Then:** swap the fake payment for **Stripe Link**, so approval happens live on stage.
3. **If there's time:** **Jinko** for real starting prices.

---

## 1. Problem

Small teams (5–50-person startups, university research groups) book work travel by hand, at bad prices, and outside their own rules.

- **Trip plans are scattered:** "I can do Dec 6 or 7 but not the 3rd" lives in a Slack thread; the conference acceptance lives in email.
- **Fares move hour to hour,** and nobody is awake to watch them.
- **Policy is in someone's head:** what counts as a Tier A conference, what the cap is, who needs approval.

Both sponsors we talked to called this a real, common use case ("book SF→NYC whenever it's under $250, within these days").

---

## 2. How we use the sponsors

### Cognee: the agent's memory (three jobs)

| Job | What goes in | What the agent asks |
|---|---|---|
| **1. Rules / ontology** | `data/policy.md`: caps, conference tiers, approval rules | "What's the cap for this trip? Does it need approval?" |
| **2. Workspace facts** | `data/workspace.json`: Slack and email messages | "What are Rohan's constraints for Chicago?" → "Dec 2–4, not Dec 3" |
| **3. Learning loop** | One trace per decision, saved to that night's session | "What lessons do we have for SFO→JFK?" |

**The learning loop (what the Cognee mentor asked to see):**

1. Each tick, the agent's decision is written to the night's session (`night_1`, `night_2`, …) with `cognee.remember`.
2. When the night ends, the simulator reveals the night's **lowest fare**. We add `hindsight_min` and `regret` (paid minus lowest) to every BUY trace. **This is hindsight grading.**
3. Call `cognee.improve(dataset, session_ids=["night_N"])`. Cognee distills the traces into lessons in the permanent graph.
4. The next night, the agent calls `cognee.recall` for rules plus lessons before deciding.

Cognee 1.0 API: `remember`, `recall`, `forget`, `improve`. `improve(dataset, session_ids=[...])` bridges session memory into the permanent graph and applies feedback weights.

**Ontology entities:** Traveler, Trip, Event, Tier, Route, Fare, Rule, Decision, Lesson.
**Relations:** Traveler ATTENDS Event · Event HAS_TIER Tier · Rule APPLIES_TO Tier · Decision ABOUT Trip · Lesson DERIVED_FROM Decision.

**Example trace:**

```json
{"tick": 12, "trip": "esha_sfo_jfk", "price": 412, "decision": "BUY",
 "reason": "under $600 Tier A cap, 21 days out", "rules_used": ["tier_a_cap"],
 "hindsight_min": 287, "regret": 125}
```

**Example lesson after `improve()`:** "SFO→JFK dropped 25%+ after midnight on 3 of 4 nights; wait if more than 10 days out."

### Stripe Link: how the agent pays

We took Allowance's advice: its founder has paused his one-time-card product and recommended **Stripe Link** for agent payments.

**How it works:**

1. When the agent decides **BUY**, and only after the policy check passes, it creates a **spend request**: merchant, amount and a plain-English reason ("SFO→JFK for NeurIPS, $291, under the $600 Tier A cap").
2. The approver gets a **push notification in the Link app** and approves or denies.
3. On approval, the agent gets a **single-use card capped at that amount**.

**Setup:**

- A Link account with a saved payment method, and the Link app on the approver's phone.
- Install: `npm i -g @stripe/link-cli`. Call it from Python with `subprocess`.

**Limits:**

- Requests must be approved within **10 minutes**, or they expire.
- **$500 per request** cap. A fare over $500 is **ESCALATE**, even if it's under the policy cap (Tier A's cap is $600).
- **US/Canada only.**

**Rules:**

- Always use `--output-file`, so card numbers never enter the agent's prompt or logs.
- **Demo rule:** issue the card live on stage, but **do not check out with it. No real purchases.**

**Overnight framing:** the agent watches all night and only pings a human when it finds a deal worth taking. Requests that aren't approved, or expire, become **ESCALATE** items in the morning digest.

**Backends:** `payments.py` has `MockPayments` (the default) and `LinkPayments`, chosen by `PAYMENTS_BACKEND=mock|link` in `.env`. Both expose `request_payment()` and `get_payment()`.

### Jinko: real starting prices (optional)

Only after priorities 1 and 2 work. `sim/jinko.py` makes **one real search per trip** through Jinko's MCP server (`https://mcp.gojinko.com`) and uses the lowest fare as the simulator's base price. The overnight movement still comes from the seeded simulator, so the demo stays repeatable. If Jinko access is unclear, skip it.

---

## 3. User flow

1. **Connect the workspace** (demo: mock Slack and email export).
2. **Extract trips:** traveler, origin, destination, date window, hard constraints, preferences.
3. **Set policy once,** in plain English → Cognee graph.
4. **Watch overnight:** every 15 simulated minutes: fetch fare → recall rules + lessons → decide BUY / WAIT / ESCALATE, with a reason.
5. **Pay:** a Stripe Link spend request; the approver approves on their phone; the agent gets a single-use card.
6. **Learn:** grade the night in hindsight → `improve()`.
7. **Morning digest:** what was booked, money saved, what needs a human.

---

## 4. Architecture

```
workspace.json + policy.md
        │  remember()
        ▼
   ┌─────────┐   recall()   ┌──────────────┐    ┌──────────────┐
   │ Cognee  │◄────────────►│ Decision     │◄───│ Fare         │
   │ graph   │              │ agent (LLM)  │    │ simulator    │
   └─────────┘              └──────┬───────┘    └──────────────┘
        ▲                          │ BUY
        │ improve()                ▼
   ┌─────────┐  remember()  ┌──────────────┐
   │ Session │◄─────────────│ Payments     │  Stripe Link / mock
   │ traces  │   (trace)    │ adapter      │
   └─────────┘              └──────────────┘
```

| Component | Built with | Job |
|---|---|---|
| Workspace ingest | Python + mock JSON | Load messages into Cognee |
| Trip extractor | LLM + `cognee.recall` | Messages → `TripRequest` objects |
| Policy graph | Cognee | Caps, tiers, approval rules |
| Fare feed | Seeded simulator (+ optional Jinko base price) | Fare per route per tick |
| Decision agent | LLM with tool calls | BUY / WAIT / ESCALATE + reason + rules cited |
| Payments | Stripe Link CLI, or mock | Spend request → phone approval → single-use card |
| Memory loop | `remember` (session) + `improve` | Traces → lessons |
| UI | Streamlit | Fare timeline, decision log, lessons, digest |

**Stack:** Python 3.10+, `cognee`, one OpenAI key (`LLM_API_KEY`, shared by Cognee and the agent), `streamlit`, `@stripe/link-cli` (Node), optional Jinko MCP.

---

## 5. Repo layout

```
flighthawk-ai/
├── BUILD_PLAN.md
├── README.md
├── requirements.txt          # cognee, streamlit, openai, python-dotenv
├── .env.example              # LLM_API_KEY=, PAYMENTS_BACKEND=mock, JINKO_API_KEY=
├── data/
│   ├── workspace.json        # ~20 Slack msgs + 5 emails
│   └── policy.md             # ~10 travel rules
├── sim/
│   ├── fares.py              # seeded fare generator + hindsight_min()
│   └── jinko.py              # optional: one real Jinko search per trip (base price)
├── memory.py                 # Cognee wrapper: ingest, recall, log_trace, improve
├── agent.py                  # decide(trip, price, context) -> (decision, reason)
├── payments.py               # MockPayments (default) + LinkPayments (Stripe Link CLI)
├── run_night.py              # the overnight loop (CLI)
└── app.py                    # Streamlit demo UI
```

---

## 6. The core loop

```python
for tick in range(32):                          # 8 hrs × every 15 min
    for trip in open_trips:
        price   = sim.get_fare(trip, night, tick)
        context = await memory.recall(f"Rules and lessons for {trip.id}")
        decision, reason = agent.decide(trip, price, context)
        if decision == "BUY":
            req = payments.request_payment(price, merchant="airline", reason=decision.reason)
            # approver approves on their phone; poll get_payment(req["id"])
            # "approved" -> card_file (never printed or logged); "denied"/"expired" -> ESCALATE
        await memory.log_trace(trace, session=f"night_{night}")

memory.add_hindsight(night)                     # reveal lowest fare, compute regret
await cognee.improve(dataset="redeye", session_ids=[f"night_{night}"])
```

**Cognee code sketch.** The operations are from the docs; the `remember` argument names are **our guess, so confirm them with the Cognee team**:

```python
import cognee, json
DATASET = "redeye"

await cognee.remember(policy_text, dataset_name=DATASET)
await cognee.remember(workspace_dump, dataset_name=DATASET)

await cognee.remember(json.dumps(trace), dataset_name=DATASET,
                      session_id=f"night_{n}", self_improvement=False)

await cognee.improve(dataset=DATASET, session_ids=[f"night_{n}"])

ctx = await cognee.recall("Rules and lessons for esha_sfo_jfk", datasets=[DATASET])
```

**Payments interface** (same two functions in `MockPayments` and `LinkPayments`):

```python
def request_payment(amount: float, merchant: str, reason: str) -> dict:
    # {"id": "lsrq_...", "approval_url": str, "status": "pending"}

def get_payment(request_id: str) -> dict:
    # {"id", "status": "pending" | "approved" | "denied" | "expired", "card_file": str | None}
```

---

## 7. Simulated data

| Trip | Traveler | Route | Window | Type | Cap | Demo twist |
|---|---|---|---|---|---|---|
| A | Esha | SFO→JFK | Dec 6–7 | Tier A conference | $600 | Night 1 buys early at $412; the night's low is $287 |
| B | Rohan | SFO→ORD | Dec 2–4, **not Dec 3** | Customer meeting | $300 | Cheapest fare is Dec 3, so the agent must refuse it |
| C | Priya | BOS→SFO | Dec 9–10 | Team offsite | $300 | Fares stay above cap, so the agent must ESCALATE |

**Fare simulator:**
- 32 ticks per night.
- `price = base × time_of_night_curve × days_to_departure_trend × (1 ± 8% noise)`
- Random flash drops (−25% for 1–2 ticks) and demand spikes.
- Fixed seed per night, so the demo replays the same way every time.
- `hindsight_min(trip, night)` returns the night's lowest fare.

Bury the constraints in casual chat so extraction is a real job.

**Sample policy rules:**
- Tier A conference: economy cap $600.
- Tier B conference: cap $350.
- Customer meeting or other: cap $300; above that, ESCALATE.
- Economy only for flights under 6 hours.
- Never book a date a traveler said they can't do.

---

## 7b. Step 0: agree on `models.py` (10 min, all three)

Before anyone codes, agree on the data shapes and function names so the three pieces fit together at the end. A draft is in [`models.py`](models.py); read it together, tweak names, then commit it.

**The four questions to settle:**
1. What info does a trip have?
2. What does the agent's decision look like?
3. What gets logged at each step?
4. What are the function names, and who writes each one?

**Small rules:**
- Dates are `"YYYY-MM-DD"` strings and prices are plain dollars.
- Trip IDs are `traveler_origin_dest`.
- `recall_context` returns plain text, so the agent can paste it straight into its prompt.
- Traces are also saved to `output/night_N.json`, so the UI can read them without calling Cognee.

**Dummy versions:** each person writes a fake version of anyone else's function they need, so their own part runs right away (e.g. Rohan's stand-in `recall_context` returns hardcoded rules). When the real one is ready, delete the fake and import the real one.

**The one rule:** if anyone needs to change a field or a function name, tell the other two first.

---

## 8. Timeline and roles

**Roles:** **Memory** owns Cognee, policy and `improve()`. **Agent** owns the simulator, decision loop and payments. **UI & pitch** owns mock data, Streamlit and the demo.

| Time | Memory | Agent | UI & pitch |
|---|---|---|---|
| 4:00–4:30 | Install Cognee, LLM key, hello-world `remember`/`recall` | Repo, `MockPayments`, install `@stripe/link-cli` | Write `workspace.json` + `policy.md` |
| 4:30–5:30 | Ingest policy + workspace; extraction returns 3 trips | Fare simulator + seeds; tick loop prints prices | Streamlit skeleton |
| 5:30–6:45 | `recall` rules + lessons per trip; traces to session | Decision agent; mock payments wired | Fare timeline with decision markers |
| 6:45–7:30 | Hindsight grading + `improve()`; before/after `recall` | Night 2 uses lessons; B refuses Dec 3, C escalates | Lessons panel + morning digest |
| 7:30–8:15 | Improve lesson quality; pre-ingest for demo | `LinkPayments` live; optional Jinko; freeze seeds | 3–4 pitch slides; approval states in the app |
| 8:15–8:45 | Rehearse 2× | Record backup demo video | Rehearse 2× |
| 8:45 | Submit | Submit | Submit |

**Hard checkpoint at 6:45:** if `improve()` isn't working yet, everyone helps Memory.

### Team roles

- **Esha (memory, Cognee):** unchanged. `memory.py`: `get_trips`, `recall_context`, `log_trace`, `end_night`, and the before/after proof.
- **Rohan (agent + payments):** `sim/fares.py`, `agent.py`, `run_night.py`, and `payments.py`, with **`MockPayments` first, then `LinkPayments`** via `link-cli`. Optional `sim/jinko.py`.
  **Done when:** Night 2 buys cheaper, refuses Rohan's Dec 3 fare, escalates Priya, and **on stage a real Link approval appears on the phone.**
- **Aman (data, UI, pitch):** `data/workspace.json`, `data/policy.md`, `app.py`, slides and demo. Add to the Streamlit app a **"Pending approval" state with the approval link**, and an **"Approved, card issued" state**. Add the Link approval moment to the demo script.

---

## 9. Demo script (3 min)

| Time | Show | Say |
|---|---|---|
| 0:00 | Title | "Your startup has three trips buried in Slack and no one to book them." |
| 0:20 | Slack → trip cards | "Flighthawk AI pulls out who, where, when, and the constraints." |
| 0:40 | Policy graph | "Company rules live in a Cognee graph the agent must follow." |
| 1:00 | Night 1 fare timeline | "It bought at $412. The night's low was $287: $125 of regret." |
| 1:30 | `improve()` + before/after `recall` | "Cognee turns the night's traces into a lesson." |
| 1:55 | Night 2 | "Buys at about $291, refuses Rohan's Dec 3 fare, escalates Priya." |
| 2:15 | Phone: Link approval → app shows "Approved, card issued" | "It only wakes a human for a deal worth taking. We took Allowance's advice and used Stripe Link for agent payments: I approve on my phone, and the agent gets a single-use card capped at the fare." (Don't check out with it.) |
| 2:35 | Morning digest | "Booked, saved, needs approval." |
| 2:50 | Close | "An overnight travel desk for teams that can't afford one." |

---

## 10. Judge Q&A

| Question | Answer |
|---|---|
| Why memory? Isn't this a price alert? | A price alert can't pull constraints out of Slack, enforce a tiered policy, or learn that a route drops after midnight. |
| Is 2–4 AM really cheapest? | We don't assume so. The agent learns per route from hindsight-graded traces. |
| Real bookings? | Fares and booking sit behind one interface; swap the simulator for a flight API's test mode. |
| Isn't it risky to let an agent spend money? | It never holds a real card. Every buy is a Stripe Link spend request a human approves on their phone; the card is single-use, capped at the fare, and written to a file the agent never reads into its prompt. Over the cap is ESCALATE. |
| Privacy? | Opt-in channels only; we store trip facts, not whole conversations. |
| Business model? | Per-booking fee, or a share of savings vs. the first price seen. |

---

## 11. Risks and fallbacks

| Risk | Fallback |
|---|---|
| Link setup fails or Wi-Fi drops | Fall back to the mock backend (`PAYMENTS_BACKEND=mock`) |
| Jinko access unclear | Skip it; simulator only |
| Cognee or LLM calls slow | Pre-ingest; small dataset; cache `recall` |
| Vague lessons from `improve()` | Explicit numbers (`regret`, `hindsight_min`) in traces; ask how to customize `improve` |
| `remember` arguments differ | Check the docs quickstart first; ask the mentor |
| Live demo breaks | Backup video recorded at 8:15 |
| Scope creep | Flights only, simulator only, until 7:30 |

---

## 12. Ask sponsors tonight

**Jinko / organizers**
- [ ] How do we get Jinko API or MCP access tonight?

**Cognee**
- [ ] Exact `remember()` arguments for session vs. permanent memory.
- [ ] Best way to load our ontology and rules.
- [ ] How to customize `improve()` ("session context entry").
- [ ] Best way to show the graph in the demo.
- [ ] What makes a strong "Best Use of Cognee" entry?

---

## Sources

- [Cognee: improve operation](https://docs.cognee.ai/core-concepts/main-operations/improve)
- [Cognee: self-improvement quickstart](https://docs.cognee.ai/guides/self-improvement-quickstart)
- [Cognee on PyPI](https://pypi.org/project/cognee/)
- Stripe Link CLI: `npm i -g @stripe/link-cli`
- Jinko MCP server: `https://mcp.gojinko.com`
- Our conversations with the Allowance and Cognee teams at the event
