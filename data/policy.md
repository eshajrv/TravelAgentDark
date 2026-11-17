# Northstar Labs travel policy

Synthetic policy for the Red-Eye demo. Effective November 16, 2026. All amounts are US dollars for one outbound fare including taxes and mandatory fees.

1. **tier_a_cap**: Approved Tier A conferences have a $600 economy fare cap. The Tier A list is Applied AI Summit, NeurIPS, and ICML. Only an explicitly confirmed work trip to a listed event qualifies.
2. **tier_b_cap**: Approved Tier B conferences have a $350 economy fare cap. The Tier B list is Regional ML Practitioners Day and Data Engineering Exchange. An unlisted conference uses the ordinary $300 cap pending review.
3. **standard_cap**: Customer meetings, team offsites, and other authorized work travel have a $300 economy fare cap. Customer visits use `customer`; offsites and other trips use `other`.
4. **cap_escalation**: A fare above its cap must be escalated to a human. A low fare on another route or spare budget on another trip does not authorize an exception. Never issue a card for an unapproved fare.
5. **banned_dates**: Never buy on a date the traveler said they cannot travel. A later, explicit traveler constraint overrides an earlier broad date window, including dates offered by an external host. Cheap fares do not override unavailable dates.
6. **allowed_dates**: Only book within the traveler's confirmed available dates. Do not infer extra travel days. Ask a human to resolve missing or conflicting dates, airports, or trip purposes before purchase.
7. **economy_only**: This demo permits economy only. No premium economy, business, or first class. Seat, lounge, baggage, hotel, and return-flight purchases are outside this demo's scope.
8. **confirmed_work_only**: Extract only confirmed work trips. Ignore newsletters, hypothetical plans, declined events, and personal weekends. Use the traveler's requested airports; alternatives require confirmation.
9. **payment_limit**: After all policy checks pass, the payment adapter may issue a single-use virtual card for the fare plus $5, restricted to the booking merchant and expiring in one hour. The buffer does not raise the fare cap. Demo payments and bookings are simulated unless separately labeled by the adapter.
10. **audit_and_learn**: Log each decision with the fare, reason, and rule IDs. Review hindsight only after the night ends. Lessons may change purchase timing but may never relax caps, dates, cabin, or approval requirements. Human approval is required for exceptions; the dashboard itself cannot grant approval.
