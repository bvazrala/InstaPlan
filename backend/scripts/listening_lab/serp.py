"""Category photos from SerpApi Google Images, cached on disk so each query is paid for once.

The key stays server-side; the browser only receives the public thumbnail URL."""

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .settings import env

CACHE = Path(__file__).parent / ".cache" / "category_images.json"
_lock = threading.Lock()

# What a photo-led card for each built-in category should look like (Yelp / Google-Maps style).
PRESET_QUERIES = {
    "Dining": "restaurant dinner table friends food",
    "Travel": "travel destination scenic beach mountains",
    "Entertainment": "live concert crowd stage lights",
}


def configured() -> bool:
    return bool(env("SERPAPI_KEY"))


def _load() -> dict:
    try:
        return json.loads(CACHE.read_text())
    except (OSError, ValueError):
        return {}


def _fetch(query: str) -> dict | None:
    params = urllib.parse.urlencode({"engine": "google_images", "q": query, "api_key": env("SERPAPI_KEY"),
                                     "safe": "active", "ijn": "0"})
    try:
        with urllib.request.urlopen(f"https://serpapi.com/search.json?{params}", timeout=15) as response:
            results = json.load(response).get("images_results", [])
    except (urllib.error.URLError, ValueError):
        return None
    usable = [r for r in results if str(r.get("thumbnail", "")).startswith("https://")]
    # Prefer a landscape photo: it crops well into a wide card.
    wide = [r for r in usable if (r.get("original_width") or 0) > (r.get("original_height") or 1)]
    pick = (wide or usable or [None])[0]
    if not pick:
        return None
    return {"url": pick["thumbnail"], "title": pick.get("title", ""), "source": pick.get("source", "")}


def category_image(query: str) -> dict | None:
    """A photo for a search phrase, from the disk cache or one SerpApi call. None when unavailable."""
    query = " ".join(query.split())[:80].lower()
    if len(query) < 3:
        return None
    with _lock:
        cache = _load()
        if query in cache:
            return cache[query]
    if not configured():
        return None
    found = _fetch(query)
    if found:  # misses are not cached, so a transient failure is retried next time
        with _lock:
            cache = _load()
            cache[query] = found
            CACHE.parent.mkdir(exist_ok=True)
            CACHE.write_text(json.dumps(cache, indent=1))
    return found


def preset_images() -> dict[str, dict | None]:
    return {name: category_image(query) for name, query in PRESET_QUERIES.items()}


def custom_query(label: str) -> str:
    return f"{label} activity friends group"
