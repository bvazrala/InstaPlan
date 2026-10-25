# Multi-origin group candidates

`app.logic.candidates.build_group_candidates` is a pure, offline builder. It accepts
normalized `RoundTripFlight` and `Property` objects; it does not fetch prices, read
private preferences, score fit, or apply the ranking strategies.

```python
from app.logic.candidates import Participant, build_group_candidates

participants = [
    Participant(user_id="alice", origin_airport="AUS"),
    Participant(user_id="bob", origin_airport="BOS"),
    Participant(user_id="cara", origin_airport="LAX"),
]
# flights_by_user: user_id -> list of validated RoundTripFlight objects
# properties: normalized Property objects priced for this full stay and group
candidates = build_group_candidates(
    participants, flights_by_user, properties,
    checkin="2026-11-05", checkout="2026-11-09",
    destination_city="New York City", destination_airports=["JFK", "EWR"],
    max_candidates=12, max_flights_per_participant=3, max_lodgings=4,
)
```

Participant IDs map to attending users and origins in the universal planning
context (`where.origins`). Resolve airport codes and exact dates before invoking
the builder. Pass only attending participants; do not pass the whole context or
its budget/private fields. The context, API schemas and pipeline are unchanged.

Each `TripCandidate.participants` row contains the selected round trip, quoted
flight cost and currency, exact lodging allocation, flight-plus-lodging estimated
subtotal, and round-trip elapsed travel duration in minutes. Flight source metadata,
legs, booking/departure tokens and retrieval times survive on `row.flight`.
Return duration uses the provider's elapsed return total when all supplied stage-two
legs are returns, with a single-leg fallback for nonstop returns. Mixed-direction
provider totals are not treated as return-only durations; connected returns without
an authoritative elapsed total remain unknown.
Lodging coverage, currency, source metadata and retrieval time remain on
`lodging_price`, `lodging_source`, and `lodging_priced_at`. `priced_at` is the oldest
quote timestamp, or unknown when any input timestamp is missing.

For flight costs of $100, $200 and $300 and a $100.01 full-stay lodging quote:

| Participant | Flight | Lodging allocation | Estimated subtotal |
| --- | ---: | ---: | ---: |
| alice | 100.00 | 33.34 | 133.34 |
| bob | 200.00 | 33.34 | 233.34 |
| cara | 300.00 | 33.33 | 333.33 |

`group_total` is $700.01: lodging is allocated exactly once. Decimal arithmetic
rounds provider amounts to cents; remainder cents go to sorted user IDs. No food,
activities or ground transportation are implied. The legacy single-flight cost
and average lodging fields are `None` on group candidates; use participant rows.

`complete` describes pricing/itinerary evidence: every flight is complete, every
price exists, lodging is quoted with taxes, and currencies are known and match.
It is independent of feasibility. Nightly-derived lodging remains an estimate;
its estimated group total may be present while `complete` is false.

`feasibility` describes only structural evidence, with `feasibility_reasons`:

- `feasible`: supported routes, destination dates, capacity and costs.
- `unverified`: missing flights, dates, durations, capacity, prices or currency.
- `infeasible`: known incompatible dates/routes, insufficient capacity, or mixed currencies.

Unknown lodging capacity never becomes verified. Missing participant flights
remain as explicit rows and prevent a complete group total. Currency mismatches
never produce a cross-currency sum. Missing data and known conflicts are diagnostic
candidates; callers must check feasibility separately from price completeness.
Arrival at the destination must be on check-in day, and the return must depart on
checkout day; an overnight outbound can leave the origin the previous day. Without
an explicit destination airport allowlist, all members must use the same airport.
Lodging quotes are assumed to cover the supplied dates, group size and entire shared
property; the normalized provider model has no fields to verify those search inputs.

Generation sorts and deduplicates inputs deterministically, limits each member to
F flight choices, retains at most B partial combinations after each member, and
limits lodging to L properties. It evaluates at most B*F expansions per member and
B*L final candidates, returning at most B (`max_candidates`). Evidence quality is
used to keep supported candidates ahead of diagnostics; price/time/preferences do
not drive selection. This is bounded sampling, so it does not guarantee finding the
best or every feasible combination. IDs depend on member-to-itinerary assignments,
lodging identity and dates, never prices; reordered inputs produce identical output.

Existing imports from `app.integrations.serpapi_candidate_generator` and the
single-origin `build_all_candidates` examples remain supported. The pure engine now
lives under `app/logic/`. Synthetic coverage is in `backend/tests/test_logic.py`.


## Live flow and verification

The pure builder is used by the live pipeline. See [the API contract](api-contract.md#live-option-generation)
for public inputs, run status, pricing semantics, and server-side selection rules.

Run `cd backend && pytest`, then `cd frontend && npm test && npm run lint && npm run build`.
Frontend tooling requires Node 22.13 or newer. For desktop/mobile browser checks,
install a Playwright Chromium browser (`npx playwright install chromium`), build the
frontend, and run `npm run test:browser`. On Windows an installed Edge can be used
by setting `PLAYWRIGHT_CHANNEL=msedge`. Browser tests intercept all travel API responses;
they do not need login credentials, a running backend, or paid provider requests.
The browser preview runs on 127.0.0.1:3100 and may reuse an existing preview there.

For an explicit, bounded live-provider smoke test, from `backend/` run:

```powershell
python -m scripts.smoke_options --live --checkin 2027-02-05 --checkout 2027-02-09 --request-limit 12
```

Choose future dates and set `SERPAPI_KEY` in the backend environment first. The command
uses a temporary scratch cache and never connects to the application's database. It
prints public candidate evidence counts/statuses only. It does not test authentication,
private preferences or live Muse normalization; the deterministic integration suite
covers those boundaries with mocks. Live provider availability remains variable.
