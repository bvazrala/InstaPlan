"""Explore SerpApi Google Events: NYC events during the trip window.

Verified live 2026-10-25: the engine WORKS (search_metadata.status=Success).
Real names: results array `events_results`; row fields `title`, `date`
({start_date, when} — NO YEAR), `venue` ({name, link}), `address` (list),
`ticket_info` (list of {source, link, link_type} — links only, NO prices),
`event_token`, `serpapi_event_details_link`.

Verified caveat: the requested start_date/end_date window was NOT honored in
the live run (results spanned Oct 26–Dec 31, only 1/10 inside Nov 5–9) —
filter client-side.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common

ENGINE_TAG = "events"
PREFERRED = ("events_results", "events")


def build_params(args: Any) -> dict[str, Any]:
    return {
        "engine": "google_events",
        "q": args.query,
        "location": args.city,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "hl": "en",
        "gl": "us",
    }


def when(value: Any) -> str:
    if isinstance(value, dict):
        return value.get("when") or value.get("start_date") or common.MISSING
    return str(value) if value else common.MISSING


def venue_of(e: dict[str, Any]) -> str:
    v = e.get("venue")
    if isinstance(v, dict):
        return v.get("name") or common.MISSING
    return str(v) if v else common.MISSING


def tickets(e: dict[str, Any]) -> str:
    ti = e.get("ticket_info")
    if not ti:
        return "none"
    sources = [t.get("source", "?") for t in ti if isinstance(t, dict)]
    first = next((t.get("link") for t in ti if isinstance(t, dict) and t.get("link")), None)
    out = f"{', '.join(sources) or '?'}"
    if first:
        out += f" (link: {first[:60]}…)"
    return out + " [link only — no price in API response]"


def render_event(i: int, e: dict[str, Any]) -> str:
    parts = [
        f"name={e.get('title') or common.MISSING}",
        f"date={when(e.get('date'))}",
        f"venue={venue_of(e)}",
        f"address={' / '.join(e.get('address') or []) or common.MISSING}",
        f"tickets={tickets(e)}",
        f"event-token={'yes' if e.get('event_token') else 'MISSING'}",
    ]
    return f"{i}. " + " | ".join(parts)


def main() -> int:
    args = common.parse_cli(
        "SerpApi Google Events exploration: NYC, default window 2026-11-05..2026-11-09 (date window may be ignored by the provider — verify per run)",
        top_default=10,
        flags=[
            ("--query", {"default": "events in New York", "help": "event query"}),
            ("--city", {"default": "New York"}),
            ("--start-date", {"default": "2026-11-05", "help": "trip start YYYY-MM-DD"}),
            ("--end-date", {"default": "2026-11-09", "help": "trip end YYYY-MM-DD"}),
        ],
    )
    data, _, mode = common.prepare(
        args, build_params(args), ENGINE_TAG,
        common.slug(f"{args.city} {args.start_date}"),
    )
    if mode == "dry-run":
        return 0

    name, items = common.find_list(data, PREFERRED)
    print(f"\nTop-level keys: {', '.join(data.keys())}")
    print(f"location_used: {data.get('search_parameters', {}).get('location_used', common.MISSING)}")
    if not items:
        print("[warn] No events found under 'events_results' — inspect the saved JSON.")
        return 0
    common.print_listing(name, items, args.limit, render_event)
    print("\nVerified caveats to re-check on every run:")
    print("  - dates carry NO YEAR (start_date like 'Nov 5') — compare month/day, not full dates")
    print("  - the date window was ignored in the live run (1/10 in-window) — filter client-side")
    print("  - ticket_info is ticket-purchase LINKS only; prices are not in the API response")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except common.SerpApiError as exc:
        print(f"\ntest_events failed: {exc}", file=sys.stderr)
        sys.exit(1)
