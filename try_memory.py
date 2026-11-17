"""Esha's end-to-end check for memory.py, with stand-ins for Rohan's fares and agent.

Runs: setup -> extract trips -> before/after proof around a fake Night 1.

    python try_memory.py

The fake fares follow the plan: about $412 early, falling to about $287 after midnight.
The fake agent buys as soon as a fare is under the cap (the naive strategy), so Night 1
has regret for Cognee to learn from. Delete this file once run_night.py is real.
"""
from memory import end_night, get_trips, log_trace, recall_context, setup, ask
from models import Decision, Trace

QUESTION = "When should we buy SFO-JFK fares overnight?"


def fake_fare(tick: int) -> float:  # stand-in for Rohan's get_fare
    curve = [412, 409, 405, 401, 398, 392, 388, 380, 371, 360, 349, 336, 322, 309, 298, 291,
             287, 289, 294, 301, 312, 326, 340, 352, 361, 369, 377, 384, 390, 396, 401, 405]
    return float(curve[tick])


def fake_decide(trip, price, already_bought):  # stand-in for Rohan's decide
    if already_bought:
        return Decision("WAIT", "already booked", [])
    if trip.cap and price <= trip.cap:
        return Decision("BUY", f"${price:.0f} is under the ${trip.cap:.0f} cap", ["fare_cap"])
    return Decision("ESCALATE", f"${price:.0f} is over the ${trip.cap:.0f} cap", ["over_cap_needs_approval"])


if __name__ == "__main__":
    print("1) Loading policy + workspace into Cognee...")
    setup(reset=True)

    print("\n2) Trips Cognee found in the messages:")
    trips = get_trips(refresh=True)
    for t in trips:
        print("  ", t)

    jfk = next((t for t in trips if t.dest == "JFK"), None)
    if not jfk:
        raise SystemExit("No SFO-JFK trip found; check the extraction above.")

    print("\n3) BEFORE Night 1:", QUESTION)
    print("  ", ask(QUESTION))

    print("\n4) Fake Night 1 for", jfk.id)
    bought = False
    for tick in range(32):
        price = fake_fare(tick)
        decision = fake_decide(jfk, price, bought)
        bought = bought or decision.action == "BUY"
        log_trace(Trace(night=1, tick=tick, trip_id=jfk.id, price=price, decision=decision))

    print("\n5) end_night(1) -> lessons:")
    for lesson in end_night(1):
        print("  -", lesson)

    print("\n6) AFTER Night 1:", QUESTION)
    print("  ", ask(QUESTION))

    print("\n7) What Rohan's agent will see for", jfk.id)
    print(recall_context(jfk.id))
