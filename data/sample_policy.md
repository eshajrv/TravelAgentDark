# Flighthawk AI travel policy (stand-in)

Stand-in until Aman's `data/policy.md` is ready. `memory.py` uses `policy.md` if it exists,
otherwise this file.

1. Book economy only.
2. Tier A conferences (NeurIPS, ICML, CVPR, SIGGRAPH): fare cap is $600 round trip.
3. Tier B conferences (Design Systems Summit, local meetups): fare cap is $350 round trip.
4. Customer visits: fare cap is $500 round trip.
5. Anything else: fare cap is $300 round trip.
6. Any fare over the cap needs a manager's approval: ESCALATE instead of buying.
7. Never book a date the traveler said they can't do.
8. International trips always need a manager's approval: ESCALATE.
9. Book at least 7 days before departure.
10. Every booking is a Stripe Link spend request that a human approves on their phone; the
    agent then gets a single-use card capped at the fare.
11. Stripe Link allows at most $500 per request, so any fare over $500 must ESCALATE, even if
    it is under the trip's fare cap.
