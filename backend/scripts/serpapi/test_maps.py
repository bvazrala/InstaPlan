"""Explore SerpApi Google Maps search: restaurants and activities in NYC.

Caveat from the offline reference (SERPAPI_AGENT_REFERENCE.md): the city in
``q`` (or ``ll``) is a search *origin*, not a geofence — results are not
guaranteed to be inside the area. Don't treat a hit as "in NYC" without a
distance check.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common

ENGINE_TAG = "maps"
PREFERRED = ("local_results",)


def build_params(args: Any) -> dict[str, Any]:
    query = args.query or (f"{args.category} in {args.city}" if args.category else args.city)
    params: dict[str, Any] = {
        "engine": "google_maps",
        "type": "search",
        "q": query,
        "hl": "en",
    }
    if args.ll:
        lat, _, lon = args.ll.partition(",")
        params["ll"] = f"@{lat.strip()},{lon.strip()},{args.zoom}z"
    if args.min_price is not None:
        params["min_price"] = args.min_price
    if args.max_price is not None:
        params["max_price"] = args.max_price
    if args.min_rating is not None:
        params["min_rating"] = args.min_rating
    if args.start is not None:
        params["start"] = args.start
    return params


def coords(place: dict[str, Any]) -> str:
    gps = place.get("gps_coordinates")
    if isinstance(gps, dict):
        return f"({gps.get('latitude')},{gps.get('longitude')})"
    return common.MISSING


def render_place(i: int, p: dict[str, Any]) -> str:
    rating = p.get("rating")
    reviews = p.get("reviews")
    parts = [
        f"title={common.show(p, 'title')}",
        f"category={common.show(p, 'type')}",
        f"price={common.show(p, 'price')}",
        f"rating={rating if rating is not None else common.MISSING}" + (f" ({reviews} reviews)" if reviews else ""),
        f"address={common.show(p, 'address')}",
        f"coords={coords(p)}",
        f"place_id={common.show(p, 'place_id')}",
        f"data_id={common.show(p, 'data_id')}",
        f"website={'yes' if p.get('website') else common.MISSING}",
    ]
    return f"{i}. " + " | ".join(parts)


def main() -> int:
    args = common.parse_cli(
        "SerpApi Google Maps exploration: places (restaurants/activities) in NYC",
        top_default=10,
        flags=[
            ("--query", {"default": None, "help": "full query string (overrides --category/--city)"}),
            ("--category", {"default": "restaurants", "help": "restaurants, museums, breweries, …"}),
            ("--city", {"default": "New York City"}),
            ("--ll", {"default": None, "help": "explicit origin 'lat,lon' with --zoom (omit to rely on city in q)"}),
            ("--zoom", {"type": int, "default": 10, "help": "view size for --ll, NOT a radius"}),
            ("--min-price", {"type": int, "default": None}),
            ("--max-price", {"type": int, "default": None}),
            ("--min-rating", {"type": float, "default": None}),
            ("--start", {"type": int, "default": None, "help": "pagination offset (0/20/40…); stop around 100"}),
        ],
    )
    data, _, mode = common.prepare(
        args, build_params(args), ENGINE_TAG,
        common.slug(args.query or (f"{args.category} {args.city}")),
    )
    if mode == "dry-run":
        return 0

    name, items = common.find_list(data, PREFERRED)
    print(f"\nTop-level keys: {', '.join(data.keys())}")
    if not items:
        print("[warn] No local_results found. Inspect the saved JSON (or the city string was rejected).")
        return 0
    common.print_listing(name, items, args.limit, render_place)
    probes = ("title", "type", "rating", "reviews", "address", "gps_coordinates",
              "place_id", "data_id", "phone", "website", "open_state", "price",
              "price_description", "reserve_a_table")
    present = [k for k in probes if any(it.get(k) not in (None, "", [], {}) for it in items)]
    print(f"\nField coverage over ALL {len(items)} results on the page:")
    print(f"  present: {', '.join(present)}")
    print(f"  absent:  {', '.join(k for k in probes if k not in present)}")
    if "price" not in present:
        print("  -> no $-levels on this run's rows (restaurants had 0/20 in the live run) — "
              "do not assume price data from Maps")
    print("\nAlways re-check: every row really inside the city? (origin != geofence)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except common.SerpApiError as exc:
        print(f"\ntest_maps failed: {exc}", file=sys.stderr)
        sys.exit(1)
