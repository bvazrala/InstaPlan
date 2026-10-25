"""Google Maps lookups, proxied through the lab server so the key never reaches the browser."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

NAME = "GOOGLE_MAPS_API_KEY"


def _key() -> str:
    """Read only the Maps key, from the environment or the lab's / backend's .env file."""
    if os.environ.get(NAME):
        return os.environ[NAME]
    for path in (Path(__file__).parent / ".env", Path(__file__).resolve().parents[2] / ".env"):
        if path.is_file():
            for line in path.read_text().splitlines():
                key, _, value = line.partition("=")
                if key.strip() == NAME and value.strip():
                    return value.strip().strip("\"'")
    return ""


def configured() -> bool:
    return bool(_key())


def _call(url: str, body: dict | None = None, headers: dict | None = None) -> dict:
    key = _key()
    if not key:
        raise RuntimeError(f"{NAME} is missing; Google Maps search is unavailable")
    request = urllib.request.Request(
        url, data=json.dumps(body).encode() if body is not None else None,
        method="POST" if body is not None else "GET",
        headers={"X-Goog-Api-Key": key, "Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Google Maps returned HTTP {exc.code}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Google Maps connection failed: {exc.reason}") from None


def autocomplete(query: str, token: str = "") -> list[dict]:
    query = query.strip()
    if len(query) < 2:
        return []
    body = {"input": query[:200]} | ({"sessionToken": token[:64]} if token else {})
    found = _call("https://places.googleapis.com/v1/places:autocomplete", body)
    results = []
    for item in found.get("suggestions", []):
        prediction = item.get("placePrediction")
        if prediction:
            fmt = prediction.get("structuredFormat", {})
            results.append({"place_id": prediction["placeId"],
                            "main": fmt.get("mainText", {}).get("text") or prediction["text"]["text"],
                            "secondary": fmt.get("secondaryText", {}).get("text", "")})
    return results[:6]


def details(place_id: str) -> dict:
    """An exact, Google-verified place: id, name, address and coordinates."""
    if not place_id or len(place_id) > 300 or not place_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("Invalid Google place id")
    data = _call(f"https://places.googleapis.com/v1/places/{urllib.parse.quote(place_id)}",
                 headers={"X-Goog-FieldMask": "id,displayName,formattedAddress,location"})
    return {"place_id": data["id"], "name": data.get("displayName", {}).get("text", ""),
            "address": data.get("formattedAddress", ""),
            "lat": data["location"]["latitude"], "lng": data["location"]["longitude"]}


def reverse_label(lat: float, lng: float) -> str:
    """A short readable label for device coordinates; falls back to the coordinates."""
    fallback = f"{lat:.3f}, {lng:.3f}"
    try:
        query = urllib.parse.urlencode({"latlng": f"{lat},{lng}", "result_type": "locality", "key": _key()})
        with urllib.request.urlopen(f"https://maps.googleapis.com/maps/api/geocode/json?{query}", timeout=10) as response:
            results = json.load(response).get("results", [])
        return results[0]["formatted_address"] if results else fallback
    except (urllib.error.URLError, KeyError, ValueError):
        return fallback
