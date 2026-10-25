"""Explore SerpApi Google Flights (default: AUS -> JFK round trip).

Two-call workflow (each call costs 1 credit):
  1. options  — `best_flights` + `other_flights` options. Verified live:
                 each option already carries type='Round trip', a TOTAL
                 round-trip per-person `price`, both days' legs in `flights`,
                 plus a `departure_token`. Top-level `price_insights`
                 (lowest price, typical range, price history) is in this file.
  2. roundtrip — second request with the selected option's `departure_token`;
                 returns the concrete legs (verified: the Nov-09 JFK->AUS
                 return leg in the live run) with a `booking_token`.

Stage 1 is a PRICED OPTION LIST, not a booked itinerary; stage 2 is where the
specific legs + booking reference materialize. Both stages keep the same
total price for the selected option (verified: 697 in both).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common

ENGINE_TAG = "flights"  # saved as outputs/flights-<ts>-<tag>.json; shared by both stages


def build_params(args: Any) -> dict[str, Any]:
    return {
        "engine": "google_flights",
        "type": 1,  # 1 = round trip, 2 = one-way, 3 = multi-city
        "departure_id": args.origin,
        "arrival_id": args.destination,
        "outbound_date": args.outbound,
        "return_date": args.return_date,
        "travel_class": args.travel_class,
        "currency": "USD",
        "hl": "en",
    }


def airport(v: Any) -> str:
    if not isinstance(v, dict):
        return common.MISSING
    return f"{v.get('id', '?')} ({v.get('name', '?')}) {v.get('time', '')}".strip()


def leg_line(leg: dict[str, Any]) -> str:
    return (f"{leg.get('airline', common.MISSING)} {leg.get('flight_number', '')} "
            f"{airport(leg.get('departure_airport', leg.get('departure')))} -> "
            f"{airport(leg.get('arrival_airport', leg.get('arrival')))} "
            f"[{leg.get('duration', common.MISSING)} min, {leg.get('travel_class', common.MISSING)}]")


def option_line(n: int, o: dict[str, Any]) -> str:
    legs = o.get("flights", [])
    return (f"{n}. {o.get('type', common.MISSING)} | price={o.get('price', common.MISSING)} "
            f"| option_duration={o.get('total_duration', common.MISSING)} min | legs={len(legs)} | "
            f"token={'yes' if o.get('departure_token') else 'MISSING'} | "
            + " || ".join(leg_line(l) for l in legs))


def price_insights(data: dict[str, Any]) -> None:
    pi = data.get("price_insights")
    if not isinstance(pi, dict):
        print("\n[info] no price_insights in this response")
        return
    hist = pi.get("price_history") or []
    print("\nPrice insights (verified present in the live stage-1 response):")
    for key in ("lowest_price", "price_level", "typical_price_range"):
        if pi.get(key) is not None:
            print(f"  {key} = {pi[key]}")
    if hist:
        prices = [h[1] for h in hist if isinstance(h, (list, tuple)) and len(h) == 2]
        if prices:
            print(f"  price_history = {len(hist)} points, min={min(prices)} max={max(prices)}")
        else:
            print("  price_history = present (unexpected shape — inspect the saved JSON)")


def print_options(data: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    """Stage 1: print best_flights then other_flights; return the pooled list."""
    print(f"\nTop-level keys: {', '.join(data.keys())}")
    pools = [("best_flights", data.get("best_flights") or []), ("other_flights", data.get("other_flights") or [])]
    for name, arr in pools:
        print(f"\n--- {name} ({len(arr)}) ---")
        if not arr:
            continue
        for i, o in enumerate(arr[:limit], start=1):
            print(option_line(i, o))
    price_insights(data)
    return [o for _, arr in pools for o in arr]


def print_roundtrip(data: dict[str, Any], limit: int) -> None:
    """Stage 2: itineraries that materialize the selected option (legs + booking_token)."""
    print(f"\nTop-level keys: {', '.join(data.keys())}")
    its = (data.get("other_flights") or data.get("best_flights") or [])
    if not its:
        print("[warn] No itinerary arrays found under other_flights/best_flights — inspect the saved JSON.")
        return
    print(f"\n{len(its)} stage-2 entr(y/ies) — top {min(limit, len(its))}:")
    for i, it in enumerate(its[:limit], start=1):
        legs = it.get("flights", [])
        print(f"{i}. {it.get('type', common.MISSING)} | TOTAL price={it.get('price', common.MISSING)} "
              f"| duration={it.get('total_duration', common.MISSING)} min | booking_token={'yes' if it.get('booking_token') else 'NO'}")
        for leg in legs:
            line = leg_line(leg)
            extras = [str(x) for x in (leg.get("extensions") or [])][:4]
            print(f"     leg: {line}")
            if extras:
                print(f"     amenities: {', '.join(extras)}")
            if leg.get("airplane"):
                print(f"     aircraft={leg.get('airplane')} | legroom={leg.get('legroom', common.MISSING)}")


def main() -> int:
    args = common.parse_cli(
        "SerpApi Google Flights exploration: priced round-trip options (call 1) + selected option's legs & booking_token (call 2)",
        top_default=5,
        flags=[
            ("--origin", {"default": "AUS", "help": "departure airport code (default AUS)"}),
            ("--destination", {"default": "JFK", "help": "arrival airport code (default JFK)"}),
            ("--outbound", {"default": "2026-11-05", "help": "outbound date YYYY-MM-DD"}),
            ("--return-date", {"default": "2026-11-09", "dest": "return_date", "help": "return date YYYY-MM-DD"}),
            ("--travel-class", {"type": int, "default": 1, "help": "1=economy 2=premium 3=business 4=first"}),
            ("--select", {"type": int, "default": 1, "help": "which stage-1 option (1-based, best_flights first) to complete in call 2"}),
        ],
    )
    params = build_params(args)
    data, _, mode = common.prepare(args, params, ENGINE_TAG, f"{args.origin}-{args.destination}-options")

    if mode == "dry-run":
        print("\n[info] Stage 2 (live only): re-send these params plus the departure_token of "
              f"option #{args.select}. Skipped in dry-run.")
        return 0

    options = print_options(data, args.limit)
    if mode == "replay":
        if options:
            print("\n[stage 1/2] Replayed stage-1 options (priced list, not a booked itinerary).")
        print("\n[note] Replay does not perform the stage-2 call. Live mode makes both calls.")
        return 0

    if not options:
        print("\n[warn] No options found under best_flights/other_flights — inspect the saved JSON.")
        return 0

    selected = min(max(args.select, 1), len(options))
    token = options[selected - 1].get("departure_token")
    if not token:
        print(f"\n[warn] Stage-1 option #{selected} has no 'departure_token'.")
        print("Pick another with --select, or inspect the saved JSON for the token's real field name.")
        return 0

    print(f"\n[stage 2/2] Completing option #{selected} (token: {str(token)[:40]}…) — "
          f"this second request costs 1 credit.")
    data2, _, mode2 = common.prepare(args, {**params, "departure_token": token}, ENGINE_TAG,
                                     f"{args.origin}-{args.destination}-completed")
    if mode2 != "live":
        print("\n[warn] Stage 2 not executed (dry-run/replay).")
        return 0

    print_roundtrip(data2, args.limit)
    print("\nCompare '…-options.json' and '…-completed.json' in outputs/: same total price, "
          "stage 2 adds the concrete legs + booking_token.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except common.SerpApiError as exc:
        print(f"\ntest_flights failed: {exc}", file=sys.stderr)
        sys.exit(1)
