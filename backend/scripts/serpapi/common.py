"""Shared helpers for the standalone SerpApi exploration scripts.

Standalone by design: no FastAPI, no database, no ``app.*`` imports.
Every live call costs SerpApi credits, so the code never retries and a
re-run only happens when you invoke the script again explicitly.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ENDPOINT = "https://serpapi.com/search.json"
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parents[1]  # backend/
OUTPUT_DIR = SCRIPT_DIR / "outputs"
MISSING = "\u2014"  # em-dash placeholder for absent fields

# Set by prepare() so saved JSON can redact the key even inside echoed URLs.
_current_key: str = ""


class SerpApiError(Exception):
    """Base class for all script failures."""


class MissingKey(SerpApiError):
    def __init__(self) -> None:
        super().__init__(
            "No SerpApi key found. Set SERPAPI_API_KEY (or SERPAPI_KEY) in the environment, "
            "or add it to backend/.env. Or run with --dry-run (no request) / "
            "--use-replay (parse a saved outputs/ JSON)."
        )


class RequestTimeout(SerpApiError):
    pass


class NetworkError(SerpApiError):
    pass


class BadKey(SerpApiError):  # 401/403
    pass


class BadParams(SerpApiError):  # 400
    pass


class RateLimited(SerpApiError):  # 429
    pass


class ServerError(SerpApiError):  # 5xx
    pass


class EmptyResponse(SerpApiError):
    pass


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def load_key() -> str:
    for name in ("SERPAPI_API_KEY", "SERPAPI_KEY"):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    for name, value in _read_env_file(BACKEND_DIR / ".env").items():
        if name in ("SERPAPI_API_KEY", "SERPAPI_KEY") and value.strip():
            return value.strip()
    raise MissingKey()


def sanitize(obj: Any, key: str = "") -> Any:
    """Copy of obj without api_key fields and without the secret inside strings."""
    if isinstance(obj, dict):
        return {k: sanitize(v, key) for k, v in obj.items() if k != "api_key"}
    if isinstance(obj, list):
        return [sanitize(v, key) for v in obj]
    if isinstance(obj, str) and key and key in obj:
        return obj.replace(key, "***")
    return obj


def search(params: dict[str, Any], *, timeout: float = 20) -> dict[str, Any]:
    """One SerpApi search. Raises typed errors; never retries (credits)."""
    global _current_key
    key = load_key()
    _current_key = key
    full = {**params, "output": "json", "api_key": key}
    try:
        resp = httpx.get(ENDPOINT, params=full, timeout=timeout)
    except httpx.TimeoutException as exc:
        raise RequestTimeout(
            f"Timed out after {timeout}s. The search may still have counted against your "
            "credits — check the SerpApi dashboard before re-running."
        ) from exc
    except httpx.HTTPError as exc:
        raise NetworkError(f"Could not reach serpapi.com: {exc}") from exc

    status = resp.status_code
    try:
        data: Any = resp.json()
    except ValueError:
        raise SerpApiError(f"HTTP {status}: response is not JSON ({resp.text[:200]!r}).") from None

    if status == 429:
        raise RateLimited(
            "HTTP 429: either the hourly throughput limit or the monthly credits are depleted. "
            "Check serpapi.com/dashboard — if credits are 0, re-running will keep failing."
        )
    if status in (401, 403):
        raise BadKey(f"HTTP {status}: invalid key, or this account is not allowed the engine. Check your key.")
    if status == 400:
        raise BadParams(f"HTTP 400: SerpApi rejected the parameters: {_body_hint(data, resp.text)}")
    if status >= 500:
        raise ServerError(f"HTTP {status}: SerpApi server error. Not a parameter problem — safe to retry later.")
    if status != 200:
        raise SerpApiError(f"HTTP {status}: unexpected status. Body: {_body_hint(data, resp.text)}")

    if isinstance(data, dict) and data.get("error"):
        raise SerpApiError(f"SerpApi error object in body: {data['error']}")
    if not isinstance(data, dict):
        raise EmptyResponse(f"Expected a JSON object, got {type(data).__name__}.")
    return data


def _body_hint(data: Any, text: str) -> str:
    if isinstance(data, dict):
        return json.dumps(data)[:300]
    return text[:300]


def slug(text: str, limit: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:limit].rstrip("-")


def save_response(data: dict[str, Any], engine: str, tag: str = "") -> Path:
    """Write sanitized JSON under outputs/ (git-ignored) and return the path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    name = "-".join(filter(None, [engine, stamp, tag])) + ".json"
    path = OUTPUT_DIR / name
    path.write_text(json.dumps(sanitize(data, _current_key), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def find_saved(engine: str) -> Path | None:
    if not OUTPUT_DIR.is_dir():
        return None
    files = sorted(OUTPUT_DIR.glob(f"{engine}-*.json"))
    return files[-1] if files else None


def load_saved(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SerpApiError(f"Could not read saved response {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise EmptyResponse(f"Saved file {path} is not a JSON object.")
    return data


def print_request_params(params: dict[str, Any]) -> None:
    print("Request parameters (credentials never printed):")
    for k, v in params.items():
        if k == "api_key":
            continue
        shown = "***" if _current_key and isinstance(v, str) and _current_key in v else v
        print(f"  {k} = {shown}")


def parse_cli(description: str, top_default: int, flags: list[tuple[str, dict[str, Any]]]) -> argparse.Namespace:
    """argparse with the shared flags (--limit/--dry-run/--use-replay) plus engine flags."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--limit", type=int, default=top_default, help="results to print (default %(default)s)")
    parser.add_argument("--dry-run", action="store_true", help="print the request parameters and output path; make NO HTTP request and save nothing")
    parser.add_argument("--use-replay", nargs="?", const="__newest__", default=None, metavar="FILE",
                        help="parse a saved outputs/ JSON instead of calling the API (no FILE = newest saved for this engine)")
    for cli_name, kw in flags:
        parser.add_argument(cli_name, **kw)
    return parser.parse_args()


def prepare(args: argparse.Namespace, params: dict[str, Any], engine: str, tag: str) -> tuple[dict[str, Any], Path | None, str]:
    """Branch on --dry-run / --use-replay / live, and return (data, path, mode)."""
    print_request_params(params)
    if args.dry_run:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        print("\n[dry-run] No request made, nothing saved.")
        print(f"[dry-run] Live run would save: {OUTPUT_DIR / ('-'.join(filter(None, [engine, stamp, tag])) + '.json')}")
        return {}, None, "dry-run"
    if args.use_replay is not None:
        path = Path(args.use_replay) if args.use_replay != "__newest__" else (find_saved(engine) or Path())
        if not path.is_file():
            hint = f"no {engine}-*.json saved yet under {OUTPUT_DIR}" if not path.name else str(path)
            raise SerpApiError(f"Replay file not found: {hint}. Do a live run first, or pass the exact path.")
        print(f"\n[replay] Reading saved response: {path}")
        return load_saved(path), path, "replay"
    data = search(params)
    path = save_response(data, engine, tag)
    print(f"\n[live] Saved response: {path}")
    return data, path, "live"


META_KEYS = {"search_metadata", "serpapi_pagination", "search_links", "serpapi_error", "ads"}


def find_list(data: dict[str, Any], preferred: tuple[str, ...]) -> tuple[str, list[dict[str, Any]]]:
    """Locate the results array. Falls back to the first list-of-objects top-level key
    so unknown engines (e.g. google_events) still expose their data."""
    for name in preferred:
        value = data.get(name)
        if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
            return name, value
    for name, value in data.items():
        if name in META_KEYS:
            continue
        if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
            return name, value
    return "", []


def print_listing(name: str, items: list[dict[str, Any]], limit: int, render: Callable[[int, dict[str, Any]], str]) -> None:
    show = min(limit, len(items))
    print(f"\n{len(items)} result(s) in '{name}' — showing top {show}:")
    for i, item in enumerate(items[:show], start=1):
        print(render(i, item))
    print(f"\nFirst item keys (for field mapping): {', '.join(items[0].keys())}")


def show(item: dict[str, Any], key: str, default: str = MISSING) -> str:
    value = item.get(key)
    return default if value in (None, "", [], {}) else str(value)


def show_price(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value not in (None, "", [], {}):
            currency = item.get("currency")
            return f"{value} {currency}".strip() if currency else str(value)
    return MISSING
