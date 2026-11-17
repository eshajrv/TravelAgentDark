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
COLORS = {"BUY": "#74E2C0", "WAIT": "#8CACE6", "ESCALATE": "#FFBE7A"}

st.set_page_config(page_title="Red-Eye / Overnight travel desk", page_icon="🌙", layout="wide")
st.markdown("""<style>
.block-container {max-width:1440px;padding-top:2.4rem;padding-bottom:3rem}
h1 {font-size:3.2rem!important;letter-spacing:-.07em;font-weight:750!important}
h2 {letter-spacing:-.035em} h3 {letter-spacing:-.02em}
[data-testid="stMetricValue"] {font-variant-numeric:tabular-nums;font-weight:650}
[data-testid="stMetricLabel"] {color:#A6B8CD}
[data-testid="stSidebar"] {border-right:1px solid #243246}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:16px}
.eyebrow {color:#74E2C0;font-size:.75rem;letter-spacing:.18em;font-weight:700}
.lede {color:#A6B8CD;font-size:1.1rem;max-width:820px;margin-bottom:1.6rem}
</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## ◐ Red-Eye")
    st.caption("THE OVERNIGHT TRAVEL DESK")
    st.divider()
    source = st.radio("Data source", ["Demo fixtures", "Runner output"], key="source")
    demo = source == "Demo fixtures"
    nights = load_nights(DEMO if demo else OUTPUT, demo=demo)
    st.caption("Synthetic workspace · simulated fares" if demo else "Reading exported results from the night runner")
    if st.button("Refresh results", width="stretch"):
        st.rerun()
    st.divider()
    st.markdown("**Policy first.**")
    st.caption("Unavailable dates stay unavailable. Over-budget fares need a human.")
    st.markdown("**Payments: Stripe Link**")
    st.caption("Integration owned by the runner. This dashboard never charges a card or approves a purchase.")
    st.divider()
    st.caption("Northstar Labs / Agents After Dark")

st.markdown('<div class="eyebrow">NORTHSTAR LABS / TRAVEL OPERATIONS</div>', unsafe_allow_html=True)
st.title("Good morning. Here’s your night.")
st.markdown('<div class="lede">Travel plans become clear decisions. See what the agent chose, why it waited, and what needs your attention.</div>', unsafe_allow_html=True)

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
    st.caption(f"RUNNER OUTPUT · {clock_label(tick)} simulated time · BUY records show intent, not payment or booking confirmation.")
for warning in night.warnings:
    st.warning(warning)

stats = st.columns(4)
stats[0].metric("Trips in view", len(set(trip_map) | {t.trip_id for t in visible}))
stats[1].metric("Purchase decisions", len(buys))
stats[2].metric("Needs human review", len(needs_review))
stats[3].metric("Selected fare total", f"${sum(t.price for t in buys.values()):,.0f}")

overview, decisions, workspace, pitch = st.tabs(["Overnight overview", "Decision log", "Workspace & policy", "Demo & pitch"])

with overview:
    st.subheader("The travel desk")
    if not trip_map:
        st.info("Trip details have not been exported. The chart and log still work from trace IDs; no sample trip details are substituted.")
    for start in range(0, len(night.trips), 3):
        for col, trip in zip(st.columns(3), night.trips[start:start + 3]):
            with col, st.container(border=True):
                status = latest.get(trip.id)
                st.caption(f"{trip.traveler.upper()} / {trip.trip_type.replace('_', ' ').upper()}")
                st.markdown(f"### {trip.origin} → {trip.dest}")
                st.write("Available: " + ", ".join(trip.dates))
                if trip.banned_dates:
                    st.warning("Unavailable: " + ", ".join(trip.banned_dates))
                st.caption(f"Economy fare cap ${trip.cap:,.0f}")
                if status:
                    label = {"BUY":"Purchase selected", "WAIT":"Watching fares", "ESCALATE":"Needs human review"}[status.decision.action]
                    st.markdown(f"**{label} · ${status.price:,.0f}**")
                    st.caption(status.decision.reason)
                else:
                    st.caption("No decision at this point in the replay.")

    chart_col, lesson_col = st.columns([2, 1], gap="large")
    with chart_col:
        st.subheader("The night, one decision at a time")
        ids = sorted(set(trip_map) | {t.trip_id for t in night.traces})
        if ids:
            selected = st.selectbox("Route", ids, format_func=lambda key: f"{trip_map[key].traveler} · {trip_map[key].origin} → {trip_map[key].dest}" if key in trip_map else key, key="route")
            traces = [t for t in visible if t.trip_id == selected]
            rows = [{"tick":t.tick,"price":t.price,"action":t.decision.action,"reason":t.decision.reason,"time":clock_label(t.tick)} for t in traces]
            market = [{"tick":r["tick"],"price":r["price"]} for r in rows]
            if demo:
                path = DEMO / f"market_{night_number}.json"
                if path.exists():
                    curve = [r for r in json.loads(path.read_text()) if r["trip_id"] == selected and r["tick"] <= tick]
                    market = curve or market
            if rows:
                x = alt.X("tick:Q", title="15-minute tick · 22:00 to 05:45", scale=alt.Scale(domain=[0,31]), axis=alt.Axis(values=[0,4,8,12,16,20,24,28,31]))
                line = alt.Chart(pd.DataFrame(market)).mark_line(color="#8CACE6",strokeWidth=2.5).encode(x=x,y=alt.Y("price:Q",title="Fare (USD)",scale=alt.Scale(zero=False)))
                marks = alt.Chart(pd.DataFrame(rows)).mark_point(filled=True,size=85).encode(x=x,y="price:Q",color=alt.Color("action:N",title="Decision",scale=alt.Scale(domain=list(COLORS),range=list(COLORS.values()))),shape=alt.Shape("action:N",scale=alt.Scale(domain=list(COLORS),range=["triangle-up","circle","diamond"]),legend=None),tooltip=["time:N","action:N",alt.Tooltip("price:Q",format="$,.2f"),"reason:N"])
                chart = line + marks
                if selected in trip_map:
                    cap = alt.Chart(pd.DataFrame([{"cap":trip_map[selected].cap}])).mark_rule(color="#FFBE7A",strokeDash=[5,5]).encode(y="cap:Q",tooltip=[alt.Tooltip("cap:Q",title="Policy cap",format="$,.0f")])
                    chart += cap
                st.altair_chart(chart.properties(height=310).configure_view(strokeWidth=0),width="stretch")
                st.caption("Dashed line = policy cap. Hover over a marker for the reason. Market observations may continue after a purchase decision." if demo else "Dashed line = policy cap. Chart shows exported decisions; unobserved fares are not invented.")
                if tick == 31:
                    graded = [t for t in traces if t.decision.action == "BUY" and t.hindsight_min is not None]
                    for t in graded:
                        st.caption(f"Hindsight: selected ${t.price:,.0f}; eligible low ${t.hindsight_min:,.0f}" + (f"; reported regret ${t.regret:,.0f}." if t.regret is not None else "."))
            else:
                st.info("No fare decisions for this route at the selected tick.")
    with lesson_col:
        st.subheader("What the night taught us")
        with st.container(border=True):
            st.caption("ILLUSTRATIVE LESSONS" if demo else "EXPORTED COGNEE LESSONS")
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
        st.subheader("Your morning brief" if tick == 31 else "Replay brief so far")
        for key, t in latest.items():
            name = trip_map[key].traveler if key in trip_map else key
            st.markdown(f"**{name} · {t.decision.action} · ${t.price:,.0f}**")
            st.caption(t.decision.reason)
        if not latest:
            st.info("No decisions yet.")
        st.download_button("Download morning brief",digest(night,tick),file_name=f"red-eye-night-{night_number}.txt",mime="text/plain")

with decisions:
    st.subheader("Every decision has a reason")
    actions = st.multiselect("Show decisions",list(COLORS),default=list(COLORS),key="actions")
    search = st.text_input("Find a traveler, rule, or reason",key="search")
    rows = [{"Time":clock_label(t.tick),"Tick":t.tick,"Trip":t.trip_id,"Fare":t.price,"Decision":t.decision.action,"Reason":t.decision.reason,"Rules":", ".join(t.decision.rules_used)} for t in visible if t.decision.action in actions]
    rows = [r for r in rows if search.lower() in " ".join(map(str,r.values())).lower()]
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df,hide_index=True,width="stretch",column_config={"Fare":st.column_config.NumberColumn(format="$%.2f")},height=470)
        st.download_button("Export filtered decisions",df.to_csv(index=False),file_name=f"night-{night_number}-decisions.csv",mime="text/csv")
    else:
        st.info("No decisions match these filters.")

with workspace:
    st.subheader("The details were already in the conversation")
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
