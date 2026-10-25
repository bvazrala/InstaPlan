# SerpApi exploration toolkit

Standalone scripts to **explore** SerpApi before any production integration:
real request parameters, real response structures, what data is actually
present, and API behavior. **Not** part of the app — no FastAPI, no database,
no `app.*` imports, plain `httpx` against `https://serpapi.com/search.json`.

Every live call costs SerpApi credits. The scripts never retry, never run in
loops, and `flights` makes exactly 2 calls per live run (outbound + return
selection). Re-running a script is only ever your explicit choice.

## Setup

```bash
cd backend
uv venv .venv && uv pip install -r requirements.txt   # httpx comes from requirements.txt
```

Key — pick one:

1. `export SERPAPI_API_KEY=...` (or `SERPAPI_KEY` — the name used in `.env.example`)
2. add `SERPAPI_API_KEY=...` to `backend/.env` (the scripts read it with a small
   built-in parser; no extra dependency)

Never commit the key. Saved responses land in `outputs/`, which is already
git-ignored; the sanitizer additionally drops `api_key` fields and redacts the
secret from echoed URLs (SerpApi responses sometimes embed `search_url`s with it).

## Shared flags (every script)

| Flag | Effect |
|---|---|
| `--limit N` | how many results to print (per-engine defaults: flights/hotels 5, maps/search/events 10) |
| `--dry-run` | print the **exact** request parameters and where the response would be saved; **no HTTP call, nothing saved, 0 credits** |
| `--use-replay [FILE]` | parse a saved `outputs/` JSON instead of calling the API (no `FILE` = newest for that engine). 0 credits |

Every live run prints the request params before sending and saves the full
sanitized JSON to `outputs/<engine>-<utc-ts>-<tag>.json` for later inspection.

## Scripts

### `test_flights.py` — Google Flights (2 calls)

Round trip AUS → JFK, 2026‑11‑05 → 2026‑11‑09. **Stage 1** is outbound
selection only (top 5: airline, times, duration, stops, price, `departure_token`).
**Stage 2** re-sends the params plus the selected flight's `departure_token`
(default `--select 1`) to obtain the completed round trip; the script labels
the two stages and the two saved files (`…-outbound.json`, `…-roundtrip.json`)
so the distinction stays visible.

```bash
.venv/bin/python scripts/serpapi/test_flights.py --dry-run
.venv/bin/python scripts/serpapi/test_flights.py                      # 2 credits
.venv/bin/python scripts/serpapi/test_flights.py --select 3           # complete flight #3
.venv/bin/python scripts/serpapi/test_flights.py --origin AUS --destination LAX --outbound 2026-12-01 --return-date 2026-12-05
```

Flags: `--origin --destination --outbound --return-date --travel-class --select`.
Replay mode stops after the outbound stage (the token lives in the saved JSON).

### `test_hotels.py` — Google Hotels (1 call)

`hotels in New York City`, check-in 2026‑11‑05, check-out 2026‑11‑09
(4 nights), **4 adults**, vacation rentals included. Prints top 5 with
per-night vs total price, then a **field-coverage report** over the fields we
would trust for group-cost estimation (`price`, `total_price`, `currency`,
`rating`, `guests`, …) — present/absent, not assumed.

```bash
.venv/bin/python scripts/serpapi/test_hotels.py --dry-run
.venv/bin/python scripts/serpapi/test_hotels.py                       # 1 credit
.venv/bin/python scripts/serpapi/test_hotels.py --no-vacation-rentals --bedrooms 2
.venv/bin/python scripts/serpapi/test_hotels.py --check-in 2026-11-16 --check-out 2026-11-19 --adults 6
```

### `test_maps.py` — Google Maps search (1 call)

`restaurants in New York City` (category swappable), top 10 with
`place_id`, `data_id`, coordinates, address, rating/reviews, **price level**
($–$$$$), website.

```bash
.venv/bin/python scripts/serpapi/test_maps.py --dry-run
.venv/bin/python scripts/serpapi/test_maps.py                         # 1 credit
.venv/bin/python scripts/serpapi/test_maps.py --category museums
.venv/bin/python scripts/serpapi/test_maps.py --query "museums in Brooklyn" --min-rating 4.0
.venv/bin/python scripts/serpapi/test_maps.py --ll 40.7549,-73.9840 --zoom 12
```

Flags: `--query --category --city --ll --zoom --min-price --max-price --min-rating --start`.

### `test_search.py` — Google Search (1 call)

`budget friendly attractions in New York City`, top 10 of title/link/snippet,
plus the *other* structured sections present (knowledge graph, FAQs, …) —
that's the "what does this add beyond Maps" comparison.

```bash
.venv/bin/python scripts/serpapi/test_search.py --dry-run
.venv/bin/python scripts/serpapi/test_search.py                       # 1 credit
.venv/bin/python scripts/serpapi/test_search.py --query "best free attractions NYC"
```

### `test_events.py` — Google Events (1 call)

NYC events 2026‑11‑05…2026‑11‑09, top 10 with name/date/venue/link/price fields.

> ✅ **Verified live 2026-10-25:** the engine works and `location` is honored,
> but the date window is **not** and dates carry no year — see "Live findings →
> Events". Result array is `events_results`.

```bash
.venv/bin/python scripts/serpapi/test_events.py --dry-run
.venv/bin/python scripts/serpapi/test_events.py                       # 1 credit
.venv/bin/python scripts/serpapi/test_events.py --start-date 2026-11-20 --end-date 2026-11-23
```

## Error handling

Typed, distinct failure messages (each = 1 failed call, **no automatic retry**):
400 bad params · 401/403 bad key · **429 = hourly limit *or* credits depleted —
check the dashboard before re-running** · 5xx provider error · timeouts ·
non-JSON bodies · provider-level `"error"` objects (can arrive on HTTP 200) ·
empty/zero-result responses (printed as a normal outcome with the top-level keys,
not a crash).

## Limitations and known caveats (from the offline reference)

- Identical parameter sets are provider-cached ~1 h (free) — vary params or pass
  `no_cache=true` (each `no_cache` hit costs a credit) for genuinely fresh quotes.
- `ll`/city-in-query is a search **origin, not a geofence**; results can fall
  outside the area. Zoom is a view size, never a radius.
- Maps price levels `$`–`$$$$` have no documented dollar mapping — never convert
  them to numbers for the fit math.
- Flights (verified): stage 1 already returns **total** per-person round-trip
  prices; stage 2 (`departure_token`) adds the concrete legs + `booking_token`.
  Prices are per-person totals only — no per-leg prices.
- Hotels rows are quotes, not confirmed inventory; prefer `total_rate` (verified)
  over `rate_per_night` for the stay cost, and use `after_taxes_fees` for the
  true out-the-door number.
- Events (verified): engine works, but the date window is ignored and dates
  carry no year — filter client-side; ticket data is links only, no prices.

## Live findings

### Hotels — ✅ verified live on 2026-10-25 (1 credit used)

Run with defaults (NYC, 4 adults, 2026-11-05→09, `vacation_rentals=true`),
18 results. Verified structure (see `outputs/hotels-20261025T032303Z-*.json`):

- The results array is **`properties`** — NOT `hotels` (my initial guess was wrong).
- Top level also carries: `search_metadata`, `search_parameters`,
  `search_information`, `ads`, `serpapi_pagination` (the `ads` array should be
  excluded when parsing).
- Every row: `name`, `type`, `rate_per_night`, `total_rate`, `gps_coordinates`,
  `property_token`, `images`, `amenities`, `serpapi_property_details_link`.
  15/18 also have `overall_rating`, `reviews`, `link` (a third-party booking URL)
  and `nearby_places`.
- `rate_per_night`/`total_rate` are dicts with **both** `before_taxes_fees`
  and `after_taxes_fees` (plus `extracted_*` numeric variants) — the tax/fee
  split is present (e.g. $740 → $847 after taxes/fees for 4 nights).
- `total_rate` = per-night × nights, so it is the trustworthy field for the
  group's accommodation cost.
- With `vacation_rentals=true` all 18 rows had `type: "vacation rental"` in this
  run (rentals are clearly boosted); rerun with `--no-vacation-rentals` to see
  how hotels rank and whether their row shape differs.
- Fields absent from this run: `price`, `total_price`, `rating`,
  `accommodation_type`, `guests` — the guessed names don't exist in this shape.

### Flights — ✅ verified live on 2026-10-25 (2 credits used)

Both stages executed (AUS→JFK, 2026-11-05→09):

- Stage 1 array names are **`best_flights` (3) + `other_flights` (7)** — not
  `flights`. Every option already carries `type: "Round trip"`, a **TOTAL
  per-person price** (697 for the best three, 629 cheapest overall),
  `total_duration` (minutes — the *outbound* duration in this run), and its
  legs in `flights[]`.
- Legs use `departure_airport`/`arrival_airport` objects
  (`{name, id, time: "2026-11-05 06:47"}`) plus `duration, airline,
  flight_number, airplane, travel_class, legroom` — there are **no**
  `departure`/`arrival`/`stops`/`currency` fields as guessed.
- Multi-leg options exist (`other_flights` JetBlue: AUS→FLL→JFK with 2 legs).
- **`price_insights`** is present and rich: `lowest_price` (629),
  `price_level` ("high"), `typical_price_range` ([295, 620]), `price_history`
  (61 epoch/price points) — directly usable for a "book now / price is high"
  signal in InstaPlan.
- Stage 2 (same option's `departure_token`) returned **3 entries carrying the
  return leg** (Nov 09, JFK→AUS, AA 416 / AA 1180 / AA 2772), each with
  `booking_token` (the actual booking reference) and the **same total 697**.
  So: stage 1 = priced options, stage 2 = concrete legs + booking token.
- `airports` top-level array maps the airport codes to names.
- Credits note: a full live exploration = exactly 2 searches.

### Maps — ✅ verified live on 2026-10-25 (1 credit used)

`local_results` (20 rows) for "restaurants in New York City":

- **All 20/20:** `title`, `type`/`types`, `rating`, `reviews`, `address`,
  `gps_coordinates`, `place_id`, `data_id` (+`data_cid`, `provider_id`,
  `place_id_search`), `phone`, `website`, `open_state`, `hours`,
  `operating_hours`, `reserve_a_table` (booking CTA for restaurants).
- **`price` / `price_description`: 0/20** — no $-levels at all for this
  query. Do not assume price data from Maps; treat cost as unknown.
- Extra fields: `description`, `extensions`, `unsupported_extensions`,
  `reviews_link`, `photos_link`, `thumbnail`, `country`.
- `ads` was absent in this run (the hotels run did have one — always skip it).
- Origin ≠ geofence caveat still stands: verify coordinates when the area
  matters (rows can be "near NYC" — see hotels run's NJ results).

### Search — ✅ verified live on 2026-10-25 (1 credit used)

"budget friendly attractions in New York City":

- `organic_results` (9 rows): `title`, `link`, `redirect_link`, `snippet`,
  `snippet_highlighted_words`, `position`, `date`, `source`,
  `about_this_result`, `read_more_link`.
- What this engine adds beyond Maps (all present in this response):
  `ai_overview` (LLM summary), `local_map` + `local_results` (a Maps-style
  pack inside the same search!), `related_questions` (4), `related_searches`
  (8), `filters` (4).
- Good fit for InstaPlan's "local tips / what's free" content and for
  cross-checking events, but not a price source.

### Events — ✅ verified live on 2026-10-25 (1 credit used)

Engine **works** (status Success, `location_used`=NYC). Real names:

- Array is **`events_results`** (10); top-level also `events_map`.
- Row: `title`, `date` = `{start_date: "Nov 5", when: "Nov 5, 6:00 PM"}` —
  **no year**, `venue` = `{name, link}`, `address` (list), `ticket_info`
  (list of `{source, link, link_type}` — **ticket links only, no prices**;
  sources seen: dice.fm, eventbrite, vividseats), `event_token` (10/10),
  `event_location_map`, `serpapi_event_details_link`, `thumbnail`.
- **The requested date window (Nov 5–9) was ignored** — results spanned
  Oct 26 → Dec 31, only 1/10 inside the window. Filter client-side and handle
  the missing year (Dec 31 is presumably 2026 for a 2026 trip, but verify).

## Comparison table (complete — all five verified live 2026-10-25)

| API | Relevant fields (live-verified) | Missing/uncertain data | Additional calls needed | MVP usefulness |
|---|---|---|---|---|
| Flights | `best_flights`/`other_flights`: `type` ("Round trip"), **total per-person `price`**, legs (`departure_airport`/`arrival_airport` w/ time, `duration`, `flight_number`, `airline`, `airplane`, `legroom`), `departure_token`; `price_insights` (`lowest_price`, `typical_price_range`, `price_history`) | Per-leg prices (total only); return-leg details (only via stage 2); "stops" count (count legs instead) | Stage-2 call per selected option (`departure_token`) for legs + `booking_token` — 2 credits per full exploration | **High** — total price + durations + price-history signal feed the option cards and "book now" directly |
| Hotels | `properties`: `name, type, rate_per_night, total_rate` (both with `before/after_taxes_fees` + `extracted_*`), `overall_rating, reviews, gps_coordinates, property_token, link, amenities, images` | occupancy per row; `ads` must be skipped; all-`vacation rental` skew with `vacation_rentals=true` (hotels not in this run's rows) | detail lookup via `serpapi_property_details_link` (1 credit) if amenity depth is needed | **High** — stay-total price incl. taxes is exactly the per-person-cost input |
| Maps | `local_results`: `title, type, rating, reviews, address, gps_coordinates, place_id/data_id, phone, website, open_state, operating_hours, reserve_a_table` | **no price data at all** (0/20 in this run); availability at trip time (open_state is "now") | place details/reviews via `place_id` (1 credit each) | **High** for place discovery + coordinates for fit math; **not** a cost source |
| Search | `organic_results` (title/link/snippet) + bonus sections `ai_overview`, `local_map`/`local_results`, `related_questions`, `related_searches` | no structured prices, availability, or times | none for tips; use the `local_results` pack to avoid a separate Maps call | **Medium** — trip ideas/free-things content + a cheap bundled local pack; not for per-person costs |
| Events | `events_results`: `title, date {start_date,when (no year)}, venue {name,link}, address, ticket_info (links only), event_token, serpapi_event_details_link` | **date window ignored server-side**; no year on dates; ticket prices (links only) | detail via `serpapi_event_details_link` (1 credit) for exact time/price if needed | **Medium-low** — works, but filter client-side; prices unknown → treat as "bring-your-own-info" content |
