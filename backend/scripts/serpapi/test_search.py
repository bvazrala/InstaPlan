"""Explore SerpApi Google Search: travel info such as budget-friendly NYC attractions.

Goal: see what a generic web search adds on top of Google Maps
(e.g. article context, lists with prices written in text, seasonal guides).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common

ENGINE_TAG = "search"
PREFERRED = ("organic_results",)


def build_params(args: Any) -> dict[str, Any]:
    params: dict[str, Any] = {
        "engine": "google",
        "q": args.query,
        "gl": args.gl,
        "hl": args.hl,
    }
    if args.start is not None:
        params["start"] = args.start
    return params


def render_result(i: int, r: dict[str, Any]) -> str:
    snippet = (r.get("snippet") or "").replace("\n", " ")
    if len(snippet) > 160:
        snippet = snippet[:157] + "..."
    return f"{i}. {common.show(r, 'title')} | {common.show(r, 'link')} | {snippet or common.MISSING}"


def main() -> int:
    args = common.parse_cli(
        "SerpApi Google Search exploration: travel-info queries (default: budget-friendly NYC attractions)",
        top_default=10,
        flags=[
            ("--query", {"default": "budget friendly attractions in New York City", "help": "search query"}),
            ("--gl", {"default": "us", "help": "country code"}),
            ("--hl", {"default": "en", "help": "language"}),
            ("--start", {"type": int, "default": None, "help": "pagination offset (0/10/20…)"}),
        ],
    )
    data, _, mode = common.prepare(args, build_params(args), ENGINE_TAG, common.slug(args.query))
    if mode == "dry-run":
        return 0

    name, items = common.find_list(data, PREFERRED)
    print(f"\nTop-level keys: {', '.join(data.keys())}")
    if not items:
        print("[warn] No organic_results found. Inspect the saved JSON.")
        return 0
    common.print_listing(name, items, args.limit, render_result)
    extra = [k for k in data if k not in ("search_metadata", "serpapi_pagination", "ads", "organic_results")]
    if extra:
        print(f"\nExtra structured sections available (what this adds beyond Maps data): {', '.join(extra)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except common.SerpApiError as exc:
        print(f"\ntest_search failed: {exc}", file=sys.stderr)
        sys.exit(1)
