"""Presentation helpers for the Red-Eye travel desk."""
from base64 import b64encode
from html import escape
from pathlib import Path


COLORS = {"BUY": "#087F88", "WAIT": "#6256C9", "ESCALATE": "#C64238"}

CSS = """<style>
:root {--ink:#142D4E;--muted:#526984;--blue:#1269DE;--line:#DCE6EF}
.stApp {background:#F5F8FC;color:var(--ink)}
.block-container {max-width:1460px;padding:4.5rem 2.7rem 3rem}
h1,h2,h3,h4 {color:var(--ink);letter-spacing:-.035em}
h2 {font-size:1.4rem!important;font-weight:700!important}
h3 {font-size:1.18rem!important;font-weight:650!important}
h4 {font-size:1rem!important}
p,label {font-size:.89rem!important;line-height:1.55}
[data-testid="stCaptionContainer"] {opacity:1!important;color:var(--muted)!important}
[data-testid="stCaptionContainer"] p {font-size:.77rem!important;color:var(--muted);line-height:1.5}
[data-testid="stSidebar"] {background:#EAF1FB;border-right:1px solid #D6E3F2;min-width:230px;max-width:260px}
[data-testid="stSidebar"] .block-container {padding-top:1.5rem}
[data-testid="stSidebar"] hr {border-color:#CCDCEE}
.brand {display:flex;align-items:center;gap:10px;font-size:1.45rem;font-weight:800;letter-spacing:-.06em;margin:8px 0 2px}
.brand-mark {display:grid;place-items:center;background:#1469DE;color:white;width:36px;height:36px;border-radius:11px;font-size:1.3rem;letter-spacing:0}
.brand-sub {font-size:.7rem;color:#526984;margin-left:46px;letter-spacing:.07em;text-transform:uppercase}
.desk-header {display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;gap:12px}
.desk-label {font-size:.7rem;letter-spacing:.14em;font-weight:700;color:#526984}
.desk-badge {font-size:.72rem;color:#294C7B;border:1px solid #D7E2F1;border-radius:30px;padding:5px 12px;background:white}
.flight-hero {position:relative;overflow:hidden;min-height:248px;border-radius:20px;background:#1675E6;margin-bottom:24px;display:flex;align-items:center}
.hero-copy {position:relative;z-index:1;width:58%;padding:30px 34px}
.hero-kicker {display:inline-block;font-size:.65rem;letter-spacing:.14em;font-weight:750;background:#FFDB69;color:#403708;padding:6px 10px;border-radius:5px;margin-bottom:12px}
.flight-hero h1 {color:white;font-size:2.8rem!important;line-height:1.06!important;font-weight:750!important;letter-spacing:-.045em;margin:0 0 12px;padding:0!important}
.flight-hero p {color:#E7F3FF;font-size:.92rem!important;margin:0;max-width:340px;line-height:1.55}
.hero-art {position:absolute;right:0;top:0;width:49%;height:100%;object-fit:cover;object-position:center}
.st-key-summary_metrics {margin:8px 0 22px}
.st-key-summary_metrics [data-testid="stMetric"] {background:#E1EFFF;border:1px solid #CCE1FA;border-radius:14px;padding:17px 20px;min-height:106px}
.st-key-summary_metrics [data-testid="stColumn"]:nth-child(2) [data-testid="stMetric"] {background:#DDF3EE;border-color:#C6E7DE}
.st-key-summary_metrics [data-testid="stColumn"]:nth-child(3) [data-testid="stMetric"] {background:#FFE8E1;border-color:#F8D4C8}
.st-key-summary_metrics [data-testid="stColumn"]:nth-child(4) [data-testid="stMetric"] {background:#FFF1BE;border-color:#EFDF9E}
[data-testid="stMetricValue"] {font-size:2rem;font-variant-numeric:tabular-nums;font-weight:700;letter-spacing:-.04em;color:var(--ink)}
[data-testid="stMetricValue"] p {font-size:2rem!important;line-height:1.2!important}
[data-testid="stMetricLabel"] {color:#36516B}
[data-baseweb="tab-list"] {gap:1.7rem;border-bottom:1px solid #D6E1ED;margin-bottom:16px}
[data-baseweb="tab"] {padding:12px 0;font-weight:600;color:#526984}
[data-baseweb="tab"][aria-selected="true"] {color:#1269DE}
[data-baseweb="select"] > div {border-radius:9px!important;background:white}
button[kind="secondary"] {border-radius:9px!important;background:white;border-color:#C9D9EA;color:#25496F}
button[kind="secondary"]:hover {background:#E6F0FF;border-color:#1269DE;color:#1269DE}
[data-testid="stAlert"] {border-radius:10px;padding:.5rem .75rem}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:14px!important;border-color:var(--line)!important}
.ticket {--ticket-accent:#176ADC;--ticket-wash:#E2EDFF;background:white;border:1px solid #D9E5F0;border-radius:14px;overflow:hidden;margin-bottom:22px}
.ticket.coral {--ticket-accent:#BC453B;--ticket-wash:#FFE6DF}
.ticket.violet {--ticket-accent:#6450B1;--ticket-wash:#ECE6FD}
.ticket-top {background:var(--ticket-wash);color:var(--ticket-accent);padding:12px 17px;display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:.65rem;letter-spacing:.07em;text-transform:uppercase;font-weight:700}
.ticket-top strong {font-size:.9rem;letter-spacing:0;text-transform:none;color:#142D4E}
.ticket-body {padding:19px 18px 16px;min-height:174px}
.airport-route {display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:17px}
.airport {font-size:1.9rem;font-weight:750;letter-spacing:-.04em;line-height:1.1}
.airport small {display:block;font-size:.6rem;font-weight:600;letter-spacing:.1em;color:#60758B;margin-top:6px}
.route-line {flex:1;display:flex;align-items:center;gap:5px;color:var(--ticket-accent);font-size:1.35rem;max-width:95px}
.route-line::before,.route-line::after {content:"";flex:1;border-top:1px dashed #9DB5CC}
.ticket-detail {font-size:.77rem;color:#526984;line-height:1.65;margin-top:5px}
.ticket-detail strong {color:#203E5C;font-weight:600}
.ticket-footer {position:relative;border-top:1px dashed #B7CBDD;padding:15px 18px;min-height:112px;background:#FCFDFF}
.ticket-footer::before,.ticket-footer::after {content:"";position:absolute;width:16px;height:16px;border-radius:50%;background:#F5F8FC;border:1px solid #D9E5F0;top:-9px}
.ticket-footer::before {left:-9px}.ticket-footer::after {right:-9px}
.status-pill {display:inline-block;border-radius:5px;background:#E4F3EF;color:#116751;padding:4px 8px;font-size:.7rem;font-weight:700;margin-bottom:8px}
.status-pill.wait {background:#EDE8FC;color:#5C49AA}.status-pill.escalate {background:#FFE6DE;color:#A7372E}
.ticket-reason {font-size:.78rem!important;color:#526984;line-height:1.5;margin:0;overflow-wrap:anywhere}
.st-key-lessons {background:#F0EBFE;border:1px solid #DCD2F7;border-radius:14px;padding:18px}
@media(max-width:1100px){.block-container{padding:4.5rem 1.5rem 3rem}.flight-hero h1{font-size:2.35rem!important}.hero-copy{padding:28px}.airport{font-size:1.6rem}.ticket-top{flex-wrap:wrap}}
@media(max-width:700px){.block-container{padding:4rem 1rem 2rem}.desk-badge{display:none}.flight-hero{min-height:235px}.hero-copy{width:76%;padding:24px}.hero-art{width:58%;opacity:.3;right:-15%}.flight-hero h1{font-size:2.25rem!important}.flight-hero p{max-width:270px}.st-key-summary_metrics [data-testid="stMetric"]{min-height:95px;padding:13px 16px}[data-baseweb="tab-list"]{gap:1.1rem}.airport{font-size:2rem}}
</style>"""


def hero() -> str:
    artwork = b64encode((Path(__file__).parent / "assets" / "flight-hero.svg").read_bytes()).decode()
    return f'''<div class="desk-header"><span class="desk-label">NORTHSTAR LABS / TRAVEL DESK</span><span class="desk-badge">Overnight decisions. Morning clarity.</span></div>
<section class="flight-hero"><div class="hero-copy"><span class="hero-kicker">RED–EYE / OVERNIGHT TRAVEL</span><h1>Good nights.<br>Better flights.</h1><p>Your team's next journey, with every fare, decision, and detail in view.</p></div><img class="hero-art" src="data:image/svg+xml;base64,{artwork}" alt="An airplane following a dotted route through a blue sky, beside a colorful travel ticket"></section>'''


def ticket(trip, status, index: int) -> str:
    """Render exported text as escaped content, never as markup."""
    e = escape
    variant = ("blue", "coral", "violet")[index % 3]
    dates = ", ".join(trip.dates)
    banned = f'<div class="ticket-detail">Unavailable <strong>{e(", ".join(trip.banned_dates))}</strong></div>' if trip.banned_dates else ""
    if status:
        action = status.decision.action
        label = {"BUY": "Purchase selected", "WAIT": "Watching fares", "ESCALATE": "Needs human review"}[action]
        pill = f'<span class="status-pill {action.lower()}">{label} · ${status.price:,.0f}</span>'
        reason = e(status.decision.reason)
    else:
        pill = '<span class="status-pill wait">Awaiting first decision</span>'
        reason = "No decision at this point in the replay."
    return f'''<article class="ticket {variant}"><div class="ticket-top"><strong>{e(trip.traveler)}</strong><span>{e(trip.trip_type.replace('_', ' '))}</span></div><div class="ticket-body"><div class="airport-route"><div class="airport">{e(trip.origin)}<small>DEPARTURE</small></div><div class="route-line" aria-hidden="true">✈</div><div class="airport">{e(trip.dest)}<small>ARRIVAL</small></div></div><div class="ticket-detail">Available <strong>{e(dates)}</strong></div>{banned}<div class="ticket-detail">Economy · Fare cap <strong>${trip.cap:,.0f}</strong></div></div><div class="ticket-footer">{pill}<p class="ticket-reason">{reason}</p></div></article>'''
