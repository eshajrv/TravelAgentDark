"""Aman's read-only Red-Eye dashboard: streamlit run app.py."""
from __future__ import annotations

import json
import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from ui_data import clock_label, comparison, digest, load_nights, purchases, statuses

ROOT = Path(__file__).resolve().parent
DEMO = ROOT / "demo" / "fixtures"
OUTPUT = Path(os.environ.get("REDEYE_OUTPUT_DIR", str(ROOT / "output")))
COLORS = {"BUY": "#2448A6", "WAIT": "#98A0AC", "ESCALATE": "#A65A24"}

st.set_page_config(page_title="Red-Eye / Travel overview", page_icon="R", layout="wide")
st.markdown("""<style>
.block-container {max-width:1420px;padding:2.4rem 3rem 3rem}
h1 {font-size:2rem!important;letter-spacing:-.035em;font-weight:600!important;padding-bottom:.3rem!important}
h2 {font-size:1.35rem!important;font-weight:600!important;letter-spacing:-.025em}
h3 {font-size:1.15rem!important;font-weight:600!important;letter-spacing:-.02em}
h4 {font-size:.95rem!important;font-weight:600!important}
p, label {font-size:.88rem!important;line-height:1.55}
[data-testid="stCaptionContainer"] p {font-size:.76rem!important;color:#626975;line-height:1.5}
[data-testid="stCaptionContainer"] {opacity:1!important;color:#626975!important}
[data-testid="stMetricValue"] {font-size:2rem;font-variant-numeric:tabular-nums;font-weight:500;letter-spacing:-.035em}
[data-testid="stMetricValue"] p {font-size:2rem!important;line-height:1.15!important}
[data-testid="stMetricLabel"] {color:#626975}
[data-testid="stSidebar"] {border-right:1px solid #E2E5E9;background:#F8F9FA;min-width:230px;max-width:260px}
[data-testid="stSidebar"] h2 {font-size:1.3rem!important;letter-spacing:.03em}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:5px!important;border-color:#DFE3E8!important;box-shadow:none!important}
[data-baseweb="tab-list"] {gap:1.8rem;border-bottom:1px solid #DFE3E8}
[data-baseweb="tab"] {padding-left:0;padding-right:0}
[data-baseweb="select"] > div, button {border-radius:4px!important}
[data-testid="stAlert"] {border-radius:4px;padding:.45rem .65rem}
.eyebrow {color:#626975;font-size:.68rem;letter-spacing:.1em;font-weight:600;margin-bottom:.45rem}
.lede {color:#626975;font-size:.88rem;max-width:820px;margin-bottom:.4rem}
@media(max-width:850px){.block-container{padding:2rem 1rem}h1{font-size:1.7rem!important}}
</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## RED–EYE")
    st.caption("Northstar Labs")
    st.divider()
    source = st.radio("Data source", ["Demo fixtures", "Runner output"], key="source")
    demo = source == "Demo fixtures"
    nights = load_nights(DEMO if demo else OUTPUT, demo=demo)
    st.caption("Sample workspace and simulated fares" if demo else "Exported night results")
    if st.button("Refresh results", width="stretch"):
        st.rerun()
    st.divider()
    st.markdown("**Workspace**")
    st.caption("Flight requests\n\nUSD · Economy fares")
    st.markdown("**Connections**")
    st.caption("Cognee · Context & lessons\n\nStripe Link · Payment handoff")
    with st.expander("About this view"):
        st.caption("Read-only results. Purchase decisions are separate from payment and booking confirmations. Unavailable dates and fare caps always apply.")
    st.divider()
    st.caption("Agents After Dark / November 2026")

st.markdown('<div class="eyebrow">TRAVEL OPERATIONS</div>', unsafe_allow_html=True)
st.title("Travel overview")
st.markdown('<div class="lede">Overnight fare decisions, policy exceptions, and the morning handoff.</div>', unsafe_allow_html=True)

if not nights:
    st.info("No night results yet. Choose Demo fixtures to explore the app, or refresh after the runner exports a night.")
    st.code("output/night_1.json\noutput/night_2.json\noutput/trips.json  # optional if each night includes trips")
    st.stop()

control_left, control_right = st.columns([1, 3])
with control_left:
    night_number = st.selectbox("Night", list(nights), format_func=lambda n: f"Night {n}", key="night")
with control_right:
    tick = st.slider("Replay the overnight decisions", 0, 31, 31, format="Tick %d", key="tick")
night = nights[night_number]
visible = [t for t in night.traces if t.tick <= tick]
trip_map = {t.id: t for t in night.trips}
latest = statuses(night, tick)
buys = purchases(night, tick)
needs_review = [t for t in latest.values() if t.decision.action == "ESCALATE"]
if demo:
    st.caption(f"DEMO FIXTURES · {clock_label(tick)} simulated time · Handwritten trips and illustrative lessons. No agent run or payment occurred.")
else:
    st.caption(f"RUNNER OUTPUT · Tick {tick} of 31 · BUY records show intent, not payment or booking confirmation.")
    meta = night.metadata
    st.caption(f"Run: {meta.get('run_id', 'not exported')} / Status: {meta.get('status', 'not exported')} / Memory: {meta.get('memory_mode', 'not exported')} / Payments: {meta.get('payment_backend', 'not exported')}")
    if meta.get("memory_mode") == "offline_demo_fixture":
        st.info("This runner used offline memory fixtures. Its lessons are not evidence of a Cognee run.")
for warning in night.warnings:
    st.warning(warning)

stats = st.columns(4)
stats[0].metric("Trips in view", len(set(trip_map) | {t.trip_id for t in visible}))
stats[1].metric("Purchase decisions", len(buys))
stats[2].metric("Needs human review", len(needs_review))
stats[3].metric("Selected fare total", f"${sum(t.price for t in buys.values()):,.0f}")

overview, decisions, execution, workspace, pitch = st.tabs(["Overview", "Decisions", "Payments & bookings", "Workspace & policy", "Demo & pitch"])

with overview:
    st.subheader("Itineraries")
    if not trip_map:
        st.info("Trip details have not been exported. The chart and log still work from trace IDs; no sample trip details are substituted.")
    for start in range(0, len(night.trips), 3):
        for col, trip in zip(st.columns(3), night.trips[start:start + 3]):
            with col, st.container(border=True):
                status = latest.get(trip.id)
                st.caption(f"{trip.traveler} / {trip.trip_type.replace('_', ' ').title()}")
                st.markdown(f"### {trip.origin} → {trip.dest}")
                st.write("Available: " + ", ".join(trip.dates))
                if trip.banned_dates:
                    st.caption("Unavailable: " + ", ".join(trip.banned_dates))
                st.caption(f"Economy fare cap ${trip.cap:,.0f}")
                if status:
                    label = {"BUY":"Purchase selected", "WAIT":"Watching fares", "ESCALATE":"Needs human review"}[status.decision.action]
                    st.markdown(f"**{label} · ${status.price:,.0f}**")
                    st.caption(status.decision.reason)
                else:
                    st.caption("No decision at this point in the replay.")

    chart_col, lesson_col = st.columns([2, 1], gap="large")
    with chart_col:
        st.subheader("Fare history")
        ids = sorted(set(trip_map) | {t.trip_id for t in night.traces})
        if ids:
            selected = st.selectbox("Route", ids, format_func=lambda key: f"{trip_map[key].traveler} · {trip_map[key].origin} → {trip_map[key].dest}" if key in trip_map else key, key="route")
            traces = [t for t in visible if t.trip_id == selected]
            rows = [{"tick":t.tick,"price":t.price,"action":t.decision.action,"reason":t.decision.reason,"time":clock_label(t.tick) if demo else f"Tick {t.tick}"} for t in traces]
            market = [{"tick":r["tick"],"price":r["price"]} for r in rows]
            eligible = [o for o in night.observations if o["trip_id"] == selected and o["tick"] <= tick and o["eligible"]]
            if eligible:
                lows = {}
                for o in eligible:
                    lows[o["tick"]] = min(lows.get(o["tick"], float("inf")), o["price"])
                market = [{"tick":t,"price":p} for t,p in sorted(lows.items())]
            if demo:
                path = DEMO / f"market_{night_number}.json"
                if path.exists():
                    curve = [r for r in json.loads(path.read_text()) if r["trip_id"] == selected and r["tick"] <= tick]
                    market = curve or market
            if rows:
                x = alt.X("tick:Q", title="15-minute tick · 22:00 to 05:45" if demo else "Observation tick", scale=alt.Scale(domain=[0,31]), axis=alt.Axis(values=[0,4,8,12,16,20,24,28,31]))
                line = alt.Chart(pd.DataFrame(market)).mark_line(color="#6D7A94",strokeWidth=2).encode(x=x,y=alt.Y("price:Q",title="Fare (USD)",scale=alt.Scale(zero=False)))
                marks = alt.Chart(pd.DataFrame(rows)).mark_point(filled=True,size=85).encode(x=x,y="price:Q",color=alt.Color("action:N",title="Decision",scale=alt.Scale(domain=list(COLORS),range=list(COLORS.values()))),shape=alt.Shape("action:N",scale=alt.Scale(domain=list(COLORS),range=["triangle-up","circle","diamond"]),legend=None),tooltip=["time:N","action:N",alt.Tooltip("price:Q",format="$,.2f"),"reason:N"])
                chart = line + marks
                if selected in trip_map:
                    cap = alt.Chart(pd.DataFrame([{"cap":trip_map[selected].cap}])).mark_rule(color="#A65A24",strokeDash=[4,4],opacity=.65).encode(y="cap:Q",tooltip=[alt.Tooltip("cap:Q",title="Policy cap",format="$,.0f")])
                    chart += cap
                st.altair_chart(chart.properties(height=310).configure_view(strokeWidth=0),width="stretch")
                st.caption("Dashed line = policy cap. Hover over a marker for the reason. Market observations may continue after a purchase decision." if demo else ("Line = lowest eligible observed fare per tick. Markers = decisions; rejected offers appear below." if eligible else "Dashed line = policy cap. Chart shows exported decisions; unobserved fares are not invented."))
                if tick == 31:
                    graded = [t for t in traces if t.decision.action == "BUY" and t.hindsight_min is not None]
                    for t in graded:
                        st.caption(f"Hindsight: selected ${t.price:,.0f}; eligible low ${t.hindsight_min:,.0f}" + (f"; reported regret ${t.regret:,.0f}." if t.regret is not None else "."))
            else:
                st.info("No fare decisions for this route at the selected tick.")
            rejected = [o for o in night.observations if o["trip_id"] == selected and o["tick"] <= tick and not o["eligible"]]
            if rejected:
                with st.expander(f"Rejected fare observations ({len(rejected)})"):
                    st.dataframe(pd.DataFrame(rejected)[["tick","date","price","rules"]],hide_index=True,width="stretch")
    with lesson_col:
        st.subheader("Lessons & follow-up")
        with st.container(border=True):
            st.caption("ILLUSTRATIVE LESSONS" if demo else "EXPORTED LESSONS / " + night.metadata.get("memory_mode", "source not supplied"))
            if tick < 31:
                st.write("End-of-night lessons appear when the replay finishes.")
            elif night.lessons:
                for lesson in night.lessons:
                    st.write(lesson)
            else:
                st.write("No lessons exported for this night yet.")
            st.caption("Lessons can change timing. They cannot override policy.")
        st.markdown("#### Payment handoff")
        st.write("Stripe Link is the payment direction. A purchase decision alone does not prove a payment succeeded or a flight was booked.")

    st.divider()
    savings_col, digest_col = st.columns([1, 1], gap="large")
    with savings_col:
        st.subheader("Night 1 vs. Night 2")
        if tick < 31:
            st.info("Finish the replay to reveal the comparison.")
        elif 1 in nights and 2 in nights:
            comparison_rows = comparison(nights[1], nights[2])
            if comparison_rows:
                saved = sum(r["Savings"] for r in comparison_rows)
                st.metric("Lower selected fares" if saved >= 0 else "Higher selected fares", f"${abs(saved):,.0f}")
                st.dataframe(pd.DataFrame(comparison_rows),hide_index=True,width="stretch",column_config={k:st.column_config.NumberColumn(format="$%.2f") for k in ("Night 1","Night 2","Savings")})
                st.caption("Matched trips with BUY decisions in both nights only. This comparison is not realized savings and does not include payment failures, refunds, or rebooking fees.")
            else:
                st.info("No matched purchase decisions across both nights yet.")
        else:
            st.info("Both night_1.json and night_2.json are needed for a comparison.")
    with digest_col:
        st.subheader("Morning brief" if tick == 31 else "Replay brief")
        for key, t in latest.items():
            name = trip_map[key].traveler if key in trip_map else key
            st.markdown(f"**{name} · {t.decision.action} · ${t.price:,.0f}**")
            st.caption(t.decision.reason)
        if not latest:
            st.info("No decisions yet.")
        st.download_button("Download morning brief",digest(night,tick),file_name=f"red-eye-night-{night_number}.txt",mime="text/plain")

with decisions:
    st.subheader("Decision records")
    actions = st.multiselect("Show decisions",list(COLORS),default=list(COLORS),key="actions")
    search = st.text_input("Find a traveler, rule, or reason",key="search")
    rows = [{"Time":clock_label(t.tick),"Tick":t.tick,"Trip":t.trip_id,"Fare":t.price,"Decision":t.decision.action,"Reason":t.decision.reason,"Rules":", ".join(t.decision.rules_used)} for t in visible if t.decision.action in actions]
    if not demo:
        for row in rows:
            row.pop("Time")
    rows = [r for r in rows if search.lower() in " ".join(map(str,r.values())).lower()]
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df,hide_index=True,width="stretch",column_config={"Fare":st.column_config.NumberColumn(format="$%.2f")},height=470)
        st.download_button("Export filtered decisions",df.to_csv(index=False),file_name=f"night-{night_number}-decisions.csv",mime="text/csv")
    else:
        st.info("No decisions match these filters.")

with execution:
    st.subheader("Payment and booking status")
    st.caption("A Link spend approval grants a credential. It does not mean the merchant was paid or a flight was booked. Mock bookings remain simulated.")
    events = [e for e in night.executions if e["Tick"] <= tick]
    if events:
        st.dataframe(pd.DataFrame(events),hide_index=True,width="stretch",column_config={"Fare":st.column_config.NumberColumn(format="$%.2f")})
    else:
        st.info("No payment execution records at this point. Demo fixtures never request approval or make a purchase.")
    if tick == 31:
        if night.bookings:
            st.markdown("#### Booking records")
            st.dataframe(pd.DataFrame(night.bookings),hide_index=True,width="stretch",column_config={"Fare":st.column_config.NumberColumn(format="$%.2f")})
        if "simulated_replacement_savings" in night.metrics:
            st.metric("Reported simulated replacement savings",f"${night.metrics['simulated_replacement_savings']:,.2f}")
            st.caption("Runner metric after simulated replacements/refunds. This is separate from the selected-fare comparison in Overview.")
    else:
        st.caption("Final booking snapshots and replacement metrics appear after the replay finishes.")

with workspace:
    st.subheader("Source workspace")
    st.caption("Synthetic source workspace for this project. In Runner output mode, extracted trip cards come from the runner export, not from this sample.")
    data = json.loads((ROOT / "data" / "workspace.json").read_text())
    messages_col, policy_col = st.columns([1, 1],gap="large")
    with messages_col:
        query = st.text_input("Search workspace messages",key="workspace_search",placeholder="Try graduation, JFK, or offsite")
        for item in data["slack_messages"]:
            if query.lower() in json.dumps(item).lower():
                with st.expander(f"{item['id']} · #{item['channel']} · {item['sender']}"):
                    st.write(item["text"])
                    st.caption(item["timestamp"])
        for item in data["emails"]:
            if query.lower() in json.dumps(item).lower():
                with st.expander(f"{item['id']} · {item['subject']}"):
                    st.caption(f"From {item['from']}")
                    st.write(item["body"])
    with policy_col:
        st.markdown((ROOT / "data" / "policy.md").read_text())

with pitch:
    st.subheader("A three-minute product story")
    st.write("Start with the scattered travel requests. Show Esha’s early decision, Rohan’s unavailable date, and Priya’s escalation. Finish with the comparison and the morning brief.")
    for filename, label in [("pitch.html","Download four-slide offline deck"),("DEMO_SCRIPT.md","Download three-minute script & judge Q&A")]:
        path = ROOT / "demo" / filename
        if path.exists():
            st.download_button(label,path.read_bytes(),file_name=filename,mime="text/html" if filename.endswith("html") else "text/markdown")
    video = ROOT / "demo" / "backup-demo.mp4"
    if video.exists():
        st.video(str(video))
    st.caption("The fixtures demonstrate the product story. Verify the runner’s actual results before claiming live extraction, learning, payment, or booking success.")
