# SerpApi Provider Limitations for Trip-Candidate Generation

This file summarizes known constraints from each SerpApi engine that affect how
`serpapi_normalized.py` models and `serpapi_candidate_generator.py` handle data.
All facts are verified against the live run on **2026-10-25** (AUS → JFK, NYC)
and the official reference (`backend/scripts/serpapi/SERPAPI_AGENT_REFERENCE.md`).

---

## Flights (google_flights engine)

| Area | Constraint | How we handle it |
|---|---|---|
| **Two-stage workflow** | Stage-1 returns a priced option list; stage-2 with `departure_token` materialises concrete legs + `booking_token`. A candidate is only "complete" when both are available. | TripCandidate carries `flight_stages: "stage1_only" \| "complete"` and sets `completeness` accordingly. |
| **Prices** | Only total per-person round-trip price — no per-leg or per-class breakdown. | Stored as `flight_price_usd`; source field records it came from the `price` key. |
| **legs data** | Legs in stage-1 use abbreviated airport objects (`{id, name, time}`). Stage-2 adds `direction`, `airplane`, and `legroom_cm`. | Parsed separately; direction distinguishes outbound vs return. |
| **Multi-leg options** | Some entries (e.g. JetBlue via FLL) have 2 legs already in stage-1. | Each leg is a separate FlightLeg object; total_duration reflects the outbound portion only. |
| **price_insights** | `lowest_price`, `typical_price_range`, `price_level`, and `price_history` are useful signals but not guaranteed on every run. | Extracted when present; never used for per-person cost math. |
| **Stability** | Flight quotes are dynamic — a result is not an issued booking. | The example output carries `priced_at` timestamp to indicate quote age. |

## Hotels / Vacation Rentals (google_hotels engine)

| Area | Constraint | How we handle it |
|---|---|---|
| **Array name** | Results are under `properties`, not `hotels`. Ads live in a separate `ads` array with similar shape. | Parser reads only `properties`; ads are silently excluded. |
| **Pricing hierarchy** | `total_rate.after_taxes_fees` is the trusted full-stay price; `rate_per_night.display_price` × nights is a fallback. | Generator prefers extracted variant when present, then `.after_taxes_fees`, then display. |
| **Missing total_rate** | Some rows omit `total_rate`; occupancy (guests) is never returned. | Occupancy stays `None` — we never invent a default or derive it from price levels. |
| **Vacation rental skew** | `vacation_rentals=true` boosts rentals in results; hotels may appear at different ranking with the flag omitted. | Property type (`accommodation_type`) is preserved as-is; no re-weighting. |
| **Ads field** | Sponsored rows carry identical price dict shapes and must be skipped. | Parser explicitly reads only `properties`. |

## Google Maps / Places (google_maps engine)

| Area | Constraint | How we handle it |
|---|---|---|
| **Origin ≠ geofence** | `ll`/city-in-query is a search origin; results can fall outside the area. | TripCandidate generators do not filter by city — only a heuristic bbox warning is added for NYC coordinates far from Manhattan. |
| **Zoom ≠ radius** | Zoom level (e.g. `14z`) is never a strict X-km radius. | Not used for distance enforcement; Haversine recommended before routing calls. |
| **Price levels** | `$`, `$$`, `$$$`, `$$$$` have no documented dollar mapping. | Preserved as-is; never converted to numbers in any math. |
| **open_state / hours** | `"Open now"` reflects current state, not trip-time availability. | Stored raw in `open_state`; generator does not infer open/closed for requested dates. |
| **ID fields** | `place_id`, `data_id`, `data_cid` are distinct identifiers — never interchange them. | Each stored on its own field; tests assert they differ. |

## Google Events (google_events engine)

| Area | Constraint | How we handle it |
|---|---|---|
| **Date window ignored** | The provider ignores `start_date`/`end_date`; results span a wide range regardless of the query window. | Candidates that include event data must filter client-side by month/day match against trip dates. |
| **No year on dates** | Dates like `"Nov 5"` carry no year — December dates are assumed to be the current/upcoming trip year. | Event model stores `date_start_month_day` separately; month-day splitting available via `month_day_parts`. |
| **Ticket info links only** | No prices in ticket_info — only `{source, link, link_type}` pairs for purchase vendors. | Stored verbatim; no cost field populated from event rows. |

## Google Search (google engine)

| Area | Constraint | How we handle it |
|---|---|---|
| **Unstructured content** | organic_results are article snippets — titles, links, summaries — not structured venue data. | Parsed as `SearchResult`; provides trip-idea context but no per-person costs or availability. |
| **Related sections may vary** | `ai_overview`, `related_questions`, `local_map`/`local_results`, `related_searches` appear unpredictably. | Optional parsers return `None` when absent; caller checks before use. |

---

## Shared constraints across all engines

1. **Provider cache**: Identical parameter sets may be cached for ~1 hour and served free of charge. Set `no_cache=true` (costs a credit) to bypass.
2. **Rate limits**: HTTP 429 can mean either hourly throughput limit or depleted monthly credits. Check the dashboard before retrying.
3. **Error objects on HTTP 200**: Some engines return `{"error": "..."}` inside the JSON body even on success status — always check.
4. **Pagination**: Maps uses offset steps of `20` (stop ~100); search uses offset steps of `10`. Events does not document pagination.
5. **No booking guarantee**: All prices are quotes, not guaranteed reservations — a trip candidate is an estimate until purchased.
