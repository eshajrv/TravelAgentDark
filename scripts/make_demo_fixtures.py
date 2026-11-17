"""Rebuild dashboard-only fixtures. Does not run the agent or write output/."""
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from models import Trip, Trace, Decision


def main():
    folder = ROOT / "demo" / "fixtures"
    folder.mkdir(parents=True, exist_ok=True)
    trips = [
        Trip("esha_sfo_jfk", "Esha", "SFO", "JFK", ["2026-12-06", "2026-12-07"], [], 600, "tier_a_conference"),
        Trip("rohan_sfo_ord", "Rohan", "SFO", "ORD", ["2026-12-02", "2026-12-04"], ["2026-12-03"], 300, "customer"),
        Trip("priya_bos_sfo", "Priya", "BOS", "SFO", ["2026-12-09", "2026-12-10"], [], 300, "other"),
    ]
    (folder / "trips.json").write_text(json.dumps([asdict(t) for t in trips], indent=2) + "\n")
    curves = {
        1: [448,441,435,429,422,418,414,412,408,397,388,372,361,348,325,306,287,301,312,328,344,355,366,379,388,401,415,428,440,452,460,468],
        2: [444,438,431,425,419,413,409,406,399,389,379,365,351,337,318,300,291,305,315,331,342,353,365,377,389,400,414,426,438,450,459,466],
    }
    for n in (1, 2):
        traces = []
        for tick in range(32):
            if tick <= (7 if n == 1 else 16):
                buy = tick == (7 if n == 1 else 16)
                reason = ("Within the $600 Tier A cap; purchased early." if n == 1 else "Waited for the sample post-midnight dip while staying within the $600 cap.") if buy else ("Watching for an eligible fare." if n == 1 else "Applying the illustrative Night 1 lesson: keep watching this route after midnight.")
                traces.append(Trace(n,tick,trips[0].id,curves[n][tick],Decision("BUY" if buy else "WAIT",reason,["tier_a_cap","allowed_dates"]),min(curves[n]) if buy else None,curves[n][tick]-min(curves[n]) if buy else None))
            if tick <= 18:
                price = 210 if tick == 10 else (278 if tick == 18 else 320 - tick)
                action = "BUY" if tick == 18 else "WAIT"
                reason = "Eligible December 4 fare is within the $300 cap." if tick == 18 else ("Refused the $210 December 3 fare: Rohan is unavailable that day." if tick == 10 else "Watching for a fare on December 2 or 4 within the customer cap.")
                traces.append(Trace(n,tick,trips[1].id,price,Decision(action,reason,["banned_dates","standard_cap"]),278 if tick == 18 else None,0 if tick == 18 else None))
            price = 367 + abs(16-tick)*3
            traces.append(Trace(n,tick,trips[2].id,price,Decision("ESCALATE","Offsite fare exceeds the $300 cap. Human approval required; no purchase.",["standard_cap","cap_escalation"])))
        payload = {"demo":True,"night":n,"traces":[asdict(t) for t in traces],"lessons":["Illustrative lesson: in this simulated Night 1, SFO–JFK fell from $412 to $287 after midnight. Watch longer when the dates and cap allow it. This is fixture text, not a Cognee result."] if n == 1 else ["Illustrative follow-up: Night 2's sample purchase at $291 is $121 below Night 1. One scripted comparison does not establish predictive performance."]}
        (folder / f"night_{n}.json").write_text(json.dumps(payload,indent=2)+"\n")
        # Full market curve is separate from decisions after a purchase.
        (folder / f"market_{n}.json").write_text(json.dumps([{"tick":t,"price":p,"trip_id":trips[0].id} for t,p in enumerate(curves[n])],indent=2)+"\n")


if __name__ == "__main__":
    main()
