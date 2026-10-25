"""Stateless Muse calls. Uses only the standard library and lab data."""

import json
import os
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

NAMES = {"u1": "Jordan", "u2": "Maya", "u3": "Alex", "u4": "Sam"}
BEFORE, AFTER = 4, 2  # context window around each batch, not the whole chat
PROMPT = (Path(__file__).parent / "prompt.md").read_text()
PREDICT_PROMPT = (Path(__file__).parent / "predict.md").read_text()


def _muse_settings() -> dict[str, str]:
    """Read only Muse settings; the lab never loads app settings or database configuration."""
    selected = {}
    for path in (Path(__file__).parent / ".env", Path(__file__).resolve().parents[2] / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            key, separator, value = line.partition("=")
            key = key.strip()
            if separator and key in {"MUSE_API_KEY", "MUSE_BASE_URL", "MUSE_MODEL"} and value.strip():
                selected.setdefault(key, value.strip().strip('"\''))
    return {key: os.environ.get(key) or value for key, value in selected.items()}


class MuseClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        settings = _muse_settings()
        self.api_key = api_key if api_key is not None else settings.get("MUSE_API_KEY", os.environ.get("MUSE_API_KEY", ""))
        self.base_url = (base_url or settings.get("MUSE_BASE_URL") or os.environ.get("MUSE_BASE_URL", "https://api.meta.ai/v1")).rstrip("/")
        self.model = model or settings.get("MUSE_MODEL") or os.environ.get("MUSE_MODEL", "muse-spark-1.3")
        if self.model != "muse-spark-1.3":
            raise ValueError("The listening lab requires the Standard muse-spark-1.3 model")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def extract(self, template: dict, batch: list[dict], before: list[dict] | None = None,
                after: list[dict] | None = None, notes: str = "") -> tuple[list[dict], dict, dict]:
        if not self.configured:
            raise RuntimeError("MUSE_API_KEY is missing. No model request was made.")

        def line(message: dict) -> dict:
            return {"id": message["id"], "user_id": message["user_id"],
                    "name": NAMES[message["user_id"]], "text": message["text"]}

        # Compact state: empty fields are omitted so the prompt stays small.
        state = {key: value for key, value in template.items()
                 if key not in {"sources", "title", "initiator", "spoke", "category_image"} and value}
        where = template["where"]  # origins are device locations and never go to Muse
        state["where"] = {key: value for key, value in {
            "destination": (where["destination"] or {}).get("name"), "destination_hint": where["destination_hint"],
            "search_area": where["search_area"]}.items() if value}
        context = {
            "today_utc": datetime.now(UTC).date().isoformat(),
            "today_weekday": datetime.now(UTC).strftime("%A"),
            "topic": template["topic"],
            "template": state,
            "notes": notes,
            "chat_before": [line(m) for m in (before or [])[-BEFORE:]],
            "new_messages": [line(m) for m in batch],
            "chat_after": [line(m) for m in (after or [])[:AFTER]],
        }
        parsed, usage = self._chat(PROMPT, context, 1500)
        notes_ops = {"append": parsed.get("notes_append"), "replace": parsed.get("notes_replace")}
        return parsed.get("updates", []), usage, notes_ops

    def predict(self, template: dict, notes: str, recent: list[dict], empty: list[str]) -> tuple[list[dict], dict]:
        """Final pass: infer empty topic fields from notes and context, only when the answer is clear."""
        if not self.configured:
            raise RuntimeError("MUSE_API_KEY is missing. No model request was made.")
        where = template["where"]
        context = {
            "today_utc": datetime.now(UTC).date().isoformat(),
            "topic": template["topic"], "category_label": template.get("custom_label"), "group_size": len(NAMES),
            "location": (where["destination"] or {}).get("address") or where["search_area"],
            "destination_hint": where["destination_hint"],
            "group_home": template.get("base_location"),
            "template": {k: v for k, v in template.items()
                         if k in {"when", "preferences", "hard_constraints", "budget", "attendance", "cluster"} and v},
            "notes": notes,
            "recent_chat": [{"name": NAMES[x["user_id"]], "text": x["text"]} for x in recent[-12:]],
            "empty_fields": empty,
        }
        parsed, usage = self._chat(PREDICT_PROMPT, context, 800)
        return parsed.get("updates", []), usage

    def _chat(self, system: str, context: dict, max_tokens: int) -> tuple[dict, dict]:
        body = json.dumps({
            "model": self.model,
            "reasoning_effort": "minimal",
            "max_completion_tokens": max_tokens,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": json.dumps(context, ensure_ascii=False)}],
            "response_format": {"type": "json_object"},
        }).encode()
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body, method="POST",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Muse returned HTTP {exc.code}") from None
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Muse connection failed: {exc.reason}") from None
        parsed = json.loads(payload["choices"][0]["message"]["content"])
        if not isinstance(parsed, dict):
            raise ValueError("Muse response was not a JSON object")
        usage = payload.get("usage", {})
        return parsed, {"latency_ms": round((time.monotonic() - started) * 1000),
                        "prompt_tokens": usage.get("prompt_tokens"),
                        "completion_tokens": usage.get("completion_tokens"),
                        "reasoning_tokens": usage.get("completion_tokens_details", {}).get("reasoning_tokens")}
