"""Explore SerpApi Google Hotels: New York City, 4 adults, 4 nights default.

Prints lodging (hotels + vacation rentals) top fields and then which price
fields are actually present in the results, so you can judge which ones are
trustworthy for estimating group accommodation cost.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common

ENGINE_TAG = "hotels"
PREFERRED = ("properties", "hotels")


def build_params(args: Any) -> dict[str, Any]:
    params: dict[str, Any] = {
        "engine": "google_hotels",
        "q": args.query,
        "check_in_date": args.check_in,
        "check_out_date": args.check_out,
        "adults": args.adults,
        "currency": args.currency,
        "hl": "en",
        "gl": "us",
    }
    if not args.no_vacation_rentals:
        params["vacation_rentals"] = "true"
    if args.bedrooms > 0:
        params["bedrooms"] = args.bedrooms
    if args.start is not None:
        params["start"] = args.start
    return params


def money(value: Any) -> str:
    """rate_per_night/total_rate dicts carry display_price plus before/after taxes-fees numbers."""
    if isinstance(value, dict):
        base = value.get("before_taxes_fees") or value.get("display_price") or common.MISSING
        after = value.get("after_taxes_fees")
        return f"{base} (after taxes/fees {after})" if after and after != base else str(base)
    if value in (None, "", [], {}):
        return common.MISSING
    return str(value)


def render_hotel(i: int, h: dict[str, Any]) -> str:
    name = h.get("name") or h.get("title") or common.MISSING
    kind = h.get("type") or h.get("accommodation_type") or common.MISSING
    gps = h.get("gps_coordinates")
    loc = f"({gps['latitude']:.4f},{gps['longitude']:.4f})" if isinstance(gps, dict) else common.MISSING
    rating = h.get("overall_rating")
    parts = [
        f"name={name}",
        f"kind={kind}",
        f"per-night={money(h.get('rate_per_night') or h.get('price'))}",
        f"total-stay={money(h.get('total_rate') or h.get('total_price'))}",
        f"rating={rating if rating is not None else common.MISSING}"
        + (f" ({h.get('reviews')} reviews)" if h.get("reviews") else ""),
        f"coords={loc}",
        f"property-token={'yes' if h.get('property_token') else 'MISSING'}",
        "booking-link=yes" if (h.get("link") or h.get("booking_link")) else "booking-link=no",
    ]
    return f"{i}. " + " | ".join(parts)


def trust_report(items: list[dict[str, Any]]) -> None:
    """Which of the fields we care about are actually populated (whole page, not just the top rows)."""
    probes = ("name", "type", "rate_per_night", "total_rate", "overall_rating", "reviews",
              "gps_coordinates", "property_token", "link", "serpapi_property_details_link",
              # legacy/alternative names kept in case the shape changes
              "price", "total_price", "rating", "accommodation_type", "guests")
    present = [k for k in probes if any(it.get(k) not in (None, "", [], {}) for it in items)]
    absent = [k for k in probes if k not in present]
    print("\nField coverage over ALL results on the page (basis for trusting cost estimates):")
    print(f"  present: {', '.join(present) if present else 'none'}")
    print(f"  absent:  {', '.join(absent) if absent else 'none'}")
    if "total_rate" in present or "total_price" in present:
        print("  -> a stay-total price field is populated — trust it for the group's accommodation cost")
    elif "rate_per_night" in present or "price" in present:
        print("  -> only per-night prices found — multiply by nights, then add taxes/fees (check the rate dict for after_taxes_fees)")
    else:
        print("  -> no numeric price field populated — do not estimate cost from these rows yet")


def main() -> int:
    args = common.parse_cli(
        "SerpApi Google Hotels exploration: NYC, 4 adults, 4 nights default; hotels + vacation rentals",
        top_default=5,
        flags=[
            ("--query", {"default": "hotels in New York City", "help": "free-text location query"}),
            ("--check-in", {"default": "2026-11-05", "help": "check-in YYYY-MM-DD"}),
            ("--check-out", {"default": "2026-11-09", "help": "check-out YYYY-MM-DD (default +4 nights)"}),
            ("--adults", {"type": int, "default": 4}),
            ("--bedrooms", {"type": int, "default": 0, "help": "vacation rentals only; 0 = provider default"}),
            ("--no-vacation-rentals", {"action": "store_true", "help": "omit vacation_rentals=true (hotels only)"}),
            ("--currency", {"default": "USD"}),
            ("--start", {"type": int, "default": None, "help": "pagination offset (0/20/40…)"}),
        ],
    )
    data, _, mode = common.prepare(args, build_params(args), ENGINE_TAG, common.slug(args.query))
    if mode == "dry-run":
        return 0

    name, items = common.find_list(data, PREFERRED)
    print(f"\nTop-level keys: {', '.join(data.keys())}")
    if not items:
        print("[warn] No hotel list found under 'properties'/'hotels'. Inspect the saved JSON for the real array name.")
        return 0
    common.print_listing(name, items, args.limit, render_hotel)
    trust_report(items)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except common.SerpApiError as exc:
        print(f"\ntest_hotels failed: {exc}", file=sys.stderr)
        sys.exit(1)
