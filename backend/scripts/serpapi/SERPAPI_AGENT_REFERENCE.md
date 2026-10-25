# SerpAPI Offline Integration Reference — HackTX

Verified against official SerpAPI documentation on **2026-10-24**. Intended for a coding agent without internet access. Documentation facts are distinguished from **implementation recommendations**. Examples are illustrative, not live API results. The user should supply `SERPAPI_KEY`; never commit credentials.

## 0. Your mission

Implement external *place discovery* for a collaborative group trip planner. The backend should transform loosely specified group interests, locality, dates, and constraints into candidate destinations/activities, then leave group preference matching, time feasibility, and ranking to the application's own logic.

Suggested architecture:

```
user/group constraints -> pipeline.generate_options
  -> integrations/serpapi_client.py (HTTP + SerpAPI schema)
  -> integrations/cache.py (application cache)
  -> logic/fit.py (hard requirements and travel feasibility)
  -> logic/ranking.py (transparent utility score)
  -> frontend/components/trip/options/ (normalized options)
```

SerpAPI supplies discovered candidates and metadata, **not** guaranteed reservations, ticket inventory, future business openings, or a mathematically enforced search radius. Do not claim an option is available for a precise requested time merely because the place appears in Maps.

## 1. Common HTTP protocol

- Base endpoint: `https://serpapi.com/search.json` (equivalent JSON search endpoint for documented engines).
- Request method: `GET`, URL query parameters.
- Authentication: `api_key=<SECRET>`, kept server side.
- Important shared parameters: `engine`, `hl` (language), `no_cache`, `async`, `output`, `api_key`.
- JSON is best for production structured parsing: `output=json` (default). `output=md` is an alternate agent-friendly format, **not** a substitute for typed JSON parsing.
- SerpAPI search metadata includes `search_metadata.status` (typically `Processing`, `Success`, or `Error`), `.id`, and timing information. An `error` field can describe failure.
- Provider cache: identical parameter sets may be cached for **1 hour**, and cached searches are free. Set `no_cache=true` to bypass it when warranted, at the cost of a new search. `no_cache` and `async` cannot be combined.
- `async=true`: submit job and collect later through Search Archive API. Prefer synchronous requests for this hackathon unless there is a specific reason to build polling.
- `zero_trace=true` is Enterprise-only; do not assume available.
- Keep the HTTP timeout bounded and log engine/query/status/request ID, but NEVER log the API key.

Official: https://serpapi.com/google-maps-api ; https://serpapi.com/api-status-and-error-codes

### HTTP status/error handling

| Status | Documented meaning | Recommended response |
|---|---|---|
| 200 | Success at HTTP level | Still check `error` and status/payload |
| 400 | Malformed/missing argument | Do not retry unchanged; log sanitized params |
| 401 | Invalid key | Fatal configuration issue |
| 403 | Account not permitted | Fatal account/permission issue |
| 404 | Resource not found | Return typed not-found result |
| 410 | Archived search expired | Re-run original query if appropriate |
| 429 | Hourly throughput limit **or** searches depleted | Backoff carefully; depleted quota needs intervention |
| 500 / 503 | Provider/server failure | Retry boundedly with exponential backoff and jitter |

Additionally handle network exceptions, timeouts, JSON parsing failures, schema drift, and `error` JSON objects. Do not conflate **no matching venues** with **provider error**.

Official: https://serpapi.com/api-status-and-error-codes

## 2. Google Maps SEARCH — primary discovery API

Endpoint: `GET /search.json?engine=google_maps&type=search&q=...`

### Parameters

| Parameter | Meaning | Notes |
|---|---|---|
| `engine=google_maps` | Select Maps engine | Required |
| `type=search` | List places | Required for list mode |
| `q` | Natural-language venue query | Required in search mode, e.g. `coffee shops`, `bowling alleys near downtown Austin` |
| `ll` | Origin/viewpoint | `@latitude,longitude,zoomz` e.g. `@30.2672,-97.7431,14z`; or map height e.g. `@43.8521864,11.2168835,10410m` |
| `location` + `z`/`m` | Text location geolocated by provider | Alternative to `ll`; don't combine incompatible geo options |
| `lat` + `lon` + `z`/`m` | Separate numeric origin | Alternative to `ll` |
| `nearby` | Bias toward origin | Recommended for `near me` queries; **not** recommended when `q` already includes a city/area |
| `hl` | UI language | e.g. `en`, `es`, `es-419` |
| `start` | Pagination offset | `0`, `20`, `40`, ...; provider suggests stopping around offset `100` |
| `min_price`, `max_price`, `min_rating` | Optional provider filters | Filters have engine-specific meanings; verify results after fetching |
| `no_cache` | Bypass provider cached result | Default false |
| `output` | `json`, `html`, `md` | Use `json` in backend |

**Critical geographic caveat:** `ll` is a search origin, NOT a guaranteed circular geofence. The provider explicitly says results are not guaranteed to lie inside the supplied geographic location. The backend MUST compute distance or otherwise validate allowed region. For `near me` searches, pair coordinates with `nearby=true` and a non-geographic category query; for named city searches, include the name in `q` and ordinarily omit `nearby`.

**Map zoom is not a radius in kilometers.** Never state `14z` means a strict X-km radius.

Request example:

```bash
curl -G 'https://serpapi.com/search.json' \
  --data-urlencode 'engine=google_maps' \
  --data-urlencode 'type=search' \
  --data-urlencode 'q=coffee shops' \
  --data-urlencode 'll=@30.2672,-97.7431,14z' \
  --data-urlencode 'nearby=true' \
  --data-urlencode 'hl=en' \
  --data-urlencode "api_key=${SERPAPI_KEY}"
```

### Search response schema

Top-level array typically: `local_results` (and sometimes `ads`). Actual presence of each field is not guaranteed.

```json
{
  "search_metadata": {"id": "EXAMPLE", "status": "Success"},
  "local_results": [
    {
      "position": 1,
      "title": "Example Coffee Shop",
      "place_id": "EXAMPLE_PLACE_ID",
      "data_id": "0xEXAMPLE:0xEXAMPLE",
      "data_cid": "123456789",
      "gps_coordinates": {"latitude": 30.26, "longitude": -97.74},
      "rating": 4.5,
      "reviews": 328,
      "price": "$$",
      "type": "Coffee shop",
      "types": ["Coffee shop"],
      "address": "Example Street, Austin, TX",
      "open_state": "Open ⋅ Closes 8 PM",
      "operating_hours": {"saturday": "8 AM–8 PM"},
      "website": "https://example.org",
      "thumbnail": "https://example.org/image.jpg"
    }
  ],
  "serpapi_pagination": {
    "next": "https://serpapi.com/search.json?...&start=20..."
  }
}
```

**EXAMPLE / synthetic payload** above: values are illustrations of documented field names, not actual locations or confirmed availability. Additional useful optional fields include `phone`, `hours`, `description`, `service_options`, `extensions`, `amenities`, `reviews_link`, `photos_link`, `serpapi_thumbnail`, and sometimes booking-related links.

The direct `serpapi_pagination.next` URL is a provider supplied next-page link. If calling it from your backend, validate host `serpapi.com`, ensure an API key is attached securely if needed, and prevent passing arbitrary supplied URLs to the HTTP client. A simpler alternative is reproducing params with incremented `start` (`0`, `20`, `40`). Stop when no next page, exhausted result budget, or results are mostly duplicates.

**IDs:** `place_id` is a Google Maps Place ID (often beginning `ChIJ`); `data_id` is a different SerpAPI/Maps identifier like `0x...:0x...`; `data_cid` is a CID represented as a string. Do NOT interchange these identifiers. Notably, the `place_id` in the separate Google Search/Google Local API can mean the Maps `data_cid` — normalize based on engine, not a field name in isolation.

Official: https://serpapi.com/google-maps-api ; https://serpapi.com/maps-local-results

## 3. Google Maps PLACE details — enrichment

Endpoint: `GET /search.json?engine=google_maps&type=place&place_id=<GOOGLE_MAPS_PLACE_ID>`

Current base Maps docs say `type` is optional when using `place_id` or `data_cid`. **Recommended:** send `type=place` explicitly for clarity, use *either* `place_id` or `data_cid`, never both.

An older/alternative `data` parameter builds a cumbersome `!4m5!3m4!1s<DATA_ID>!8m2!3d<LAT>!4d<LON>` token and is marked deprecated in the general Maps docs. Avoid for new integration.

The response has `place_results` instead of `local_results` and may expose `title`, `rating`, `reviews`, `price`, `type`, `address`, `phone`, `website`, `description`, `open_state`, `hours`, `operating_hours`, `extensions`, `gps_coordinates`, `data_id`, `data_cid`, `images`, `user_reviews`, `booking_link`, and more. Fields are optional and context-dependent. Enrich only top candidates to save request quota.

```python
params = {
    "engine": "google_maps",
    "type": "place",
    "place_id": place_id,
    "hl": "en",
}
# response["place_results"] if present
```

Official: https://serpapi.com/maps-place-results ; https://serpapi.com/google-maps-api

## 4. Google Maps DIRECTIONS — feasibility/travel-time checks

Different engine: `engine=google_maps_directions`.

```python
params = {
    "engine": "google_maps_directions",
    "start_coords": "30.2672,-97.7431",
    "end_coords": "30.2750,-97.7500",
    "travel_mode": "2",  # WALKING — numeric provider code, NOT 'walking'
    "distance_unit": "0", # kilometers
    "hl": "en",
}
```

Source/destination can instead use `start_addr`/`end_addr` or `start_data_id`/`end_data_id`.

| travel_mode | Official meaning |
|---|---|
| `6` | Best (default) |
| `0` | Driving |
| `9` | Two-wheeler |
| `3` | Transit |
| `2` | Walking |
| `1` | Cycling |
| `4` | Flight |

`distance_unit=0` is km, `1` miles; `avoid=highways,tolls,ferries` accepts comma-separated compatible preferences. For transit, `prefer=bus,subway,train,tram_light_rail` is supported with `travel_mode=3`.

Directions responses are nested; inspect actual JSON samples before fixing extraction of distance/time. Convert parsed routes to standard `travel_minutes` and `distance_meters`, preserve raw source snippets for debugging, and handle missing routes. The directions API is not a bulk distance-matrix service; fetching every pairwise combination of N places causes O(N²) calls. For first-pass ranking use straight-line distance (Haversine), then real routes for shortlist / final itinerary.

Official: https://serpapi.com/google-maps-directions-api

## 5. Reviews and photos — selective enrichment

### Reviews

Engine: `google_maps_reviews`. Specify *either* `data_id` or `place_id`. Optional `sort_by` values: `qualityScore` (default), `newestFirst`, `ratingHigh`, `ratingLow`; optional `query` or `topic_id` (not both); `num` 1–20 (default 10); pagination uses `next_page_token`, **not `start`**. Use aggregate ratings from Maps search for first-pass ranking; fetch review text only when genuinely needed for preference matching.

Official: https://serpapi.com/google-maps-reviews-api

### Photos

Engine: `google_maps_photos`. Uses a *place* `data_id`; yields `photos` with `thumbnail` and `image` and optional metadata links. Use original returned image URLs instead of constructing/replacing query strings. Images may be externally hosted and subject to licensing/display conditions; do not treat all content as reusable without checking rights.

Official: https://serpapi.com/google-maps-photos-api

## 6. Hotel and flight discovery — NOT initial scope unless trip has travel legs

### Hotels

Engine `google_hotels`. Main query `q` (e.g., `hotels in Austin`), `check_in_date=YYYY-MM-DD`, `check_out_date=YYYY-MM-DD`; `adults` defaults 2, `children` 0, optional `children_ages`, `currency` (default USD), `hl`, and `gl`. Hotels should not be represented as confirmed inventory or quoted final price unless a specific current result supports it.

Official: https://serpapi.com/google-hotels-api

### Flights

Engine `google_flights`. `type=1` round trip (default), `2` one-way, `3` multi-city; `outbound_date` and `return_date` for round trip, `departure_id` and `arrival_id` for airport identifiers, `travel_class` codes `1` economy, `2` premium economy, `3` business, `4` first. Multi-city uses `multi_city_json`; round trips can require a follow-on request with `departure_token` for return leg. Flight quotes are dynamic; a result is not an issued booking.

Official: https://serpapi.com/google-flights-api

## 7. Python client choices

**Official current SDK** (distinct from the legacy package):

```bash
pip install serpapi
```

```python
import os
import serpapi

client = serpapi.Client(api_key=os.environ["SERPAPI_KEY"], timeout=10)
response = client.search({
    "engine": "google_maps", "type": "search",
    "q": "museums", "ll": "@30.2672,-97.7431,14z", "hl": "en",
})
places = response.get("local_results", [])
```

SDK exceptions: `serpapi.HTTPError`, inspect `.status_code` and `.error`; `serpapi.TimeoutError` for timeouts. Do not assume imports from older `google-search-results` examples such as `from serpapi import GoogleSearch` are valid with this package.

**Suggested alternative for transparent hackathon scripts:** `requests` with direct GET endpoint, fewer dependency/API-surface surprises:

```python
import os
import requests

ENDPOINT = "https://serpapi.com/search.json"

def query_serpapi(params: dict) -> dict:
    key = os.environ["SERPAPI_KEY"]
    p = {**params, "api_key": key, "output": "json"}
    response = requests.get(ENDPOINT, params=p, timeout=(5, 20))
    response.raise_for_status()
    data = response.json()
    if data.get("error") or data.get("search_metadata", {}).get("status") == "Error":
        raise RuntimeError(data.get("error", "SerpAPI search failed"))
    return data
```

This is a minimal smoke-test wrapper, **not a production retry implementation**. Log sanitizer should exclude request URL if it contains the key.

Official: https://serpapi.com/integrations/python

## 8. Normalized internal contract — recommendation, not SerpAPI schema

Do NOT send raw SerpAPI JSON to the frontend. Define a stable `PlaceCandidate`:

```json
{
  "id": "google_maps:<place_id-or-data_id>",
  "provider": "google_maps",
  "provider_place_id": "nullable string",
  "provider_data_id": "nullable string",
  "name": "Example Coffee Shop",
  "category": "coffee_shop",
  "address": "Example Street, Austin, TX",
  "coordinates": {"latitude": 30.26, "longitude": -97.74},
  "rating": 4.5,
  "review_count": 328,
  "price_level": "$$",
  "price_amount": null,
  "price_currency": null,
  "website_url": null,
  "image_url": null,
  "opening_hours_raw": null,
  "availability_at_requested_time": "unknown",
  "source": {"engine": "google_maps", "query": "coffee shops"},
  "warnings": []
}
```

**Do not** convert `$$` to exact dollars without a documented mapping. **Do not** infer that open *now* implies open at the planned future time. **Do not** assume booking links equal live bookability. Missing fields stay `null` or `unknown` rather than fabricated.

Normalization rules:

1. Coerce/validate latitude in [-90, 90], longitude in [-180, 180]; skip coordinates when missing, don't invent.
2. Deduplicate by `place_id` first, `data_id` second, and conservative normalized-name-plus-address fallback third.
3. Preserve source IDs for later detail/reviews/directions operations.
4. Treat ratings as optional 0–5 numbers, review counts as optional nonnegative integers.
5. Preserve opening-hour strings but don't parse them into guaranteed calendar availability without separate validation.
6. Keep external URLs in allowlisted/validated fields; never forward API-key-bearing SerpAPI URLs to frontend.

## 9. Application cache — recommendation

Use a canonical key combining engine, normalized query, coordinates/zoom, locale, filters, pagination and schema version. Exclude the secret API key from cache keys and logs. Suggested app TTL: 15–60 minutes for venue discovery; shorter for dynamic business status, and very short for any quote/availability-like signal. Separate provider's documented ~1 hour cache from *your own* cache (two independent layers). Never cache failures as successful empty result sets.

## 10. Candidate generation / fit / ranking — recommendation

Suggested `pipeline.generate_options` behavior:

1. Translate group interests into 2–5 category search queries (museum, coffee, live music, etc.).
2. Search in parallel with a small concurrency limit and strict per-run call budget.
3. Normalize and dedupe all search responses.
4. Hard-filter known mismatches: geographic bound, incompatible category, missing required accessibility if conclusively known; otherwise flag unknowns, do not over-reject.
5. Estimate proximity from Haversine; ask directions API only for a shortlist, if necessary.
6. Apply preference score, distance penalty, cost-fit penalty, and uncertainty penalty transparently. Mark heuristic and derived fields distinct from provider facts.
7. Optionally enrich top K via Place details; display 3–10 diverse choices.
8. Give the frontend normalized JSON with explanation and caveats, not raw provider schema.

Avoid false claims: subjective `fit_score` is **your** application score, not a Google rating or proof all attendees will enjoy the venue.

## 11. Smoke-test scripts for API validation

Create three separate scripts first; save both **raw sanitized JSON** and **summary** in `scripts/output/`:

### `scripts/serpapi_search_smoke.py`
- Query `coffee shops` at Austin coordinates; fetch page 0 and optionally page 20.
- Print metadata, result count, representative venue keys, normalized candidates, and missing-fields summary.
- Check results can lie outside a desired area (do not claim strict geographic containment).

### `scripts/serpapi_place_smoke.py`
- Take the first returned place ID; request `type=place`; print `place_results` keys and enrichment fields.
- Skip gracefully if no `place_id`.

### `scripts/serpapi_directions_smoke.py`
- Use two distinct known coordinates, `travel_mode=2` walking, and inspect returned routes and timing structures.
- Record ambiguous or missing route structure before implementing the production parser.

Each script should support `--offline <fixture.json>` for a fully disconnected agent test and `--live` only where environment allows network + API key. No network calls during offline tests.

## 12. Testing and acceptance criteria

- Unit tests run with fixtures and NO network/API key.
- Separate integration smoke tests are opt-in and require key/network.
- Empty `local_results` yields an empty successful list, **not** an exception.
- HTTP 400/401/429/5xx, timeout, JSON error, and missing IDs are distinguishable.
- Provider schema may omit `gps_coordinates`, `rating`, `website`, or `thumbnail`; parser doesn't crash.
- No key in logs, frontend JSON, exceptions, fixture files, or copied URLs.
- Search pagination uses offsets `0,20,40...`; reviews use tokens, not offsets.
- `place_id`, `data_id`, and `data_cid` remain distinct.
- Query location is not confused with geographic validation.
- Frontend consumes normalized `PlaceCandidate` with explicit uncertainty instead of raw API response.

## 13. Source index (official SerpAPI documentation)

- Maps overview/search parameters: https://serpapi.com/google-maps-api
- Maps search schema: https://serpapi.com/maps-local-results
- Maps place details: https://serpapi.com/maps-place-results
- Maps directions: https://serpapi.com/google-maps-directions-api
- Maps reviews: https://serpapi.com/google-maps-reviews-api
- Maps photos: https://serpapi.com/google-maps-photos-api
- Python official SDK: https://serpapi.com/integrations/python
- HTTP errors: https://serpapi.com/api-status-and-error-codes
- Google Hotels: https://serpapi.com/google-hotels-api
- Google Flights: https://serpapi.com/google-flights-api
- General Google Search: https://serpapi.com/search-api

**Agent instruction:** the source index is archival context. Implement using the verified rules above; do not assume browsing is possible, don't invent parameters or success schemas, and treat unknown provider behavior as a fixture-first validation task.

