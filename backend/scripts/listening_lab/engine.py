"""In-memory controller: chat queue, efficient Muse batches, validated template, confirmation."""

import json
from copy import deepcopy
from math import ceil
from datetime import UTC, datetime
from threading import RLock, Thread, Timer
from uuid import uuid4

from .contracts import (CLUSTER_FIELDS, USER_IDS, USERS, apply_updates, attending, effective_attendance,
                        missing_fields, new_template)
from . import nessie, places, serp
from .muse import MuseClient


NOTES_LIMIT = 3000


def merge_notes(notes: str, ops: dict) -> str:
    """The model's running markdown vault: optional full rewrite, then appended bullet lines."""
    replace, append = ops.get("replace"), ops.get("append")
    if isinstance(replace, str):
        notes = replace.strip()
    if isinstance(append, list):
        lines = [f"- {line.strip().lstrip('-* ').strip()}" for line in append if isinstance(line, str) and line.strip()]
        notes = "\n".join(filter(None, [notes, *lines]))
    return notes[-NOTES_LIMIT:]


class ListeningEngine:
    def __init__(self, muse: MuseClient | None = None, debounce_seconds: float = 0.9):
        self.muse = muse or MuseClient()
        self.debounce_seconds = debounce_seconds
        self.lock = RLock()
        self.timer: Timer | None = None
        self.generation = 0
        self.template: dict | None = None
        self.notes = ""
        self.votes: dict[str, bool] = {}
        self.vote_threshold = 0.5
        self.predicted_sig = ""
        self.messages: list[dict] = []
        self.pending: list[dict] = []
        self.failed_batch: list[dict] = []
        self.processing = False
        self.confirmed = False
        self.split: dict | None = None  # cost split after confirmation (Capital One Nessie)
        self.paying: set[str] = set()
        self.opening: dict[str, float] = {}  # Nessie balance when first shown; the sandbox doesn't move balances
        self.error: str | None = None
        self.decisions: list[dict] = []
        self.metrics = {"calls": 0, "batches": 0, "messages_processed": 0,
                        "prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "last_latency_ms": None}

    def start(self, title: str, topic: str, location: str = "", location_kind: str = "search_area",
              place_id: str = "", initiator: str = "u1", custom_label: str = "") -> dict:
        if initiator not in USER_IDS:
            raise ValueError("Unknown simulator user")
        place = places.details(place_id) if location_kind == "destination" and place_id else None
        if location_kind == "destination" and place is None and location.strip():
            raise ValueError("Pick the exact destination from the Google Maps results")
        query = serp.custom_query(custom_label.strip()) if topic == "Custom" else serp.PRESET_QUERIES.get(topic, "")
        image = serp.category_image(query) if query and (topic != "Custom" or len(custom_label.strip()) >= 2) else None
        template = new_template(title, topic, location, location_kind, place, initiator, custom_label, image)
        with self.lock:
            if self.timer:
                self.timer.cancel()
                self.timer = None
            self.generation += 1
            self.template = template
            self.notes = ""
            self.votes = {}
            self.predicted_sig = ""
            self.messages = []
            self.pending = []
            self.failed_batch = []
            self.processing = False
            self.confirmed = False
            self.split = None
            self.paying = set()
            self.opening = {}
            self.error = None
            self.decisions = []
            self.metrics = {"calls": 0, "batches": 0, "messages_processed": 0,
                            "prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "last_latency_ms": None}
            return self.snapshot()

    def add_message(self, user_id: str, text: str) -> dict:
        text = text.strip()
        if user_id not in USER_IDS:
            raise ValueError("Unknown simulator user")
        if not 1 <= len(text) <= 2000:
            raise ValueError("Message must be 1–2000 characters")
        with self.lock:
            if self.template is None:
                raise ValueError("Start a planning session first")
            if self.confirmed:
                raise ValueError("This template is confirmed. Start a new session to keep testing")
            message = {"id": uuid4().hex, "user_id": user_id, "text": text,
                       "sent_at": datetime.now(UTC).isoformat(), "status": "queued"}
            self.messages.append(message)
            if user_id not in self.template["spoke"]:
                self.template["spoke"].append(user_id)
            self.pending.append(message)
            self.error = None
            self._schedule_locked(immediate=len(self.pending) >= 6)
            return self.snapshot()

    def _schedule_locked(self, immediate: bool = False) -> None:
        if self.timer:
            self.timer.cancel()
        self.timer = Timer(0 if immediate else self.debounce_seconds, self._launch)
        self.timer.daemon = True
        self.timer.start()

    def _launch(self) -> None:
        with self.lock:
            self.timer = None
            if self.processing or not self.pending or self.template is None:
                return
            batch, self.pending = self.pending[:6], self.pending[6:]
            template = deepcopy(self.template)
            notes = self.notes
            first = self.messages.index(batch[0])
            before = [m for m in self.messages[:first] if m["status"] == "processed"]
            after = list(self.pending)
            generation = self.generation
            self.processing = True
            for message in batch:
                message["status"] = "listening"
        Thread(target=self._process, args=(generation, template, batch, notes, before, after), daemon=True).start()

    def _process(self, generation: int, template: dict, batch: list[dict],
                 notes: str, before: list[dict], after: list[dict]) -> None:
        try:
            updates, usage, notes_ops = self.muse.extract(template, batch, before, after, notes)
            failure = None
        except (ValueError, RuntimeError, KeyError, IndexError, TypeError) as exc:
            updates, usage, notes_ops, failure = [], {}, {}, str(exc)
        with self.lock:
            if generation != self.generation:
                return
            self.processing = False
            self.metrics["batches"] += 1
            self.metrics["calls"] += int(self.muse.configured)
            if failure:
                self.error = failure
                self.failed_batch = batch
                for message in batch:
                    message["status"] = "error"
            else:
                # Apply onto the live template so a destination or origin set meanwhile is kept.
                before_template = deepcopy(self.template)
                self.template, decisions = apply_updates(self.template, updates, batch)
                self.notes = merge_notes(self.notes, notes_ops)
                self._reset_votes_if_changed_locked(before_template)
                self.error = None
                self.failed_batch = []
                self.decisions.extend(decisions)
                self.metrics["messages_processed"] += len(batch)
                self._count_usage_locked(usage)
                for message in batch:
                    message["status"] = "processed"
            if self.pending:
                self._schedule_locked(immediate=True)
            elif not failure:
                self._maybe_predict_locked(generation)

    def _count_usage_locked(self, usage: dict) -> None:
        self.metrics["prompt_tokens"] += usage.get("prompt_tokens") or 0
        self.metrics["completion_tokens"] += usage.get("completion_tokens") or 0
        self.metrics["reasoning_tokens"] += usage.get("reasoning_tokens") or 0
        self.metrics["last_latency_ms"] = usage.get("latency_ms")

    def _empty_cluster_locked(self) -> list[str]:
        return [f for f in sorted(CLUSTER_FIELDS[self.template["topic"]]) if not self.template["cluster"].get(f)]

    def _maybe_predict_locked(self, generation: int) -> None:
        """Once everything but the topic fields is settled, let Muse infer the empty ones, if clear."""
        others = missing_fields(self.template)
        empty = self._empty_cluster_locked()
        if others or not empty or self._signature(self.template) == self.predicted_sig:
            return
        self.processing = True
        recent = [m for m in self.messages if m["status"] == "processed"]
        Thread(target=self._predict, args=(generation, deepcopy(self.template), self.notes, recent, empty),
               daemon=True).start()

    def _predict(self, generation: int, template: dict, notes: str, recent: list[dict], empty: list[str]) -> None:
        try:
            updates, usage = self.muse.predict(template, notes, recent, empty)
            failure = None
        except (ValueError, RuntimeError, KeyError, IndexError, TypeError) as exc:
            updates, usage, failure = [], {}, str(exc)
        with self.lock:
            if generation != self.generation:
                return
            self.processing = False
            self.metrics["calls"] += int(self.muse.configured)
            if failure:
                # A failed prediction is optional polish: log it, don't block the vote.
                self.decisions.append({"accepted": False, "field": "prediction", "reason": failure})
            else:
                still_empty = set(self._empty_cluster_locked())
                guessed = [dict(u, user_id=None, source_message_id="predicted") for u in updates
                           if isinstance(u, dict) and u.get("field") in still_empty]
                before_template = deepcopy(self.template)
                self.template, decisions = apply_updates(self.template, guessed, [{"id": "predicted", "user_id": None}])
                self._reset_votes_if_changed_locked(before_template)
                self.decisions.extend(decisions)
                self._count_usage_locked(usage)
            self.predicted_sig = self._signature(self.template)
            if self.pending:
                self._schedule_locked(immediate=True)

    def _signature(self, template: dict) -> str:
        # "spoke" only drives defaults; a member's first message must not wipe the votes by itself
        return json.dumps({k: v for k, v in template.items() if k not in {"sources", "spoke"}}, sort_keys=True)

    def _reset_votes_if_changed_locked(self, before: dict) -> None:
        """Votes belong to one version of the plan; any change means everyone votes again."""
        if self.votes and self._signature(before) != self._signature(self.template):
            self.votes = {}

    def set_destination(self, place_id: str) -> dict:
        place = places.details(place_id)
        with self.lock:
            if self.template is None or self.confirmed:
                raise ValueError("Start a planning session first")
            before = deepcopy(self.template)
            self.template["where"]["destination"] = place
            self.template["where"]["search_area"] = None
            self.template["sources"]["where.destination:group"] = None
            self._reset_votes_if_changed_locked(before)
            return self.snapshot()

    def set_origin(self, user_id: str, lat: float, lng: float) -> dict:
        if user_id not in USER_IDS:
            raise ValueError("Unknown simulator user")
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise ValueError("Invalid coordinates")
        label = places.reverse_label(lat, lng)
        with self.lock:
            if self.template is None or self.confirmed:
                raise ValueError("Start a planning session first")
            before = deepcopy(self.template)
            self.template["where"]["origins"][user_id] = {"lat": lat, "lng": lng, "label": label}
            self._reset_votes_if_changed_locked(before)
            return self.snapshot()

    def _poll_locked(self) -> dict:
        ready = bool(self.template is not None and not missing_fields(self.template) and not self.pending
                     and not self.processing and not self.error)
        voters = attending(self.template) if self.template else set(USER_IDS)  # people who declined don't vote
        needed = max(1, ceil(self.vote_threshold * len(voters)))
        votes = {uid: v for uid, v in self.votes.items() if uid in voters}
        yes = sum(1 for v in votes.values() if v)
        return {"open": ready and not self.confirmed, "votes": votes, "yes": yes,
                "no": len(votes) - yes, "needed": needed, "total": len(voters),
                "voters": sorted(voters), "threshold": self.vote_threshold}

    def vote(self, user_id: str, approve: bool) -> dict:
        if user_id not in USER_IDS:
            raise ValueError("Unknown simulator user")
        with self.lock:
            poll = self._poll_locked()
            if self.confirmed:
                raise ValueError("This plan is already confirmed")
            if not poll["open"]:
                raise ValueError("Voting opens once the template is complete and Muse has finished listening")
            if user_id not in poll["voters"]:
                raise ValueError("This member said they can't go, so they don't vote")
            self.votes[user_id] = bool(approve)
            poll = self._poll_locked()
            if poll["yes"] >= poll["needed"]:
                self.confirmed = True
            return self.snapshot()

    def set_threshold(self, value: float) -> dict:
        if value not in (0.4, 0.5, 0.6):
            raise ValueError("Threshold must be 40%, 50% or 60%")
        with self.lock:
            if self.confirmed:
                raise ValueError("The plan is already confirmed")
            self.vote_threshold = value
            return self.snapshot()

    def retry(self) -> dict:
        with self.lock:
            if not self.failed_batch or self.processing:
                raise ValueError("There is no failed batch to retry")
            for message in self.failed_batch:
                message["status"] = "queued"
            self.pending = self.failed_batch + self.pending
            self.failed_batch = []
            self.error = None
            self._schedule_locked(immediate=True)
            return self.snapshot()

    def confirm(self) -> dict:
        with self.lock:
            if self.template is None or missing_fields(self.template) or self.pending or self.processing or self.error:
                raise ValueError("Fill all required fields and finish listening before confirming")
            self.confirmed = True
            return self.snapshot()

    # ---- Paying for the confirmed plan (Capital One Nessie) ----

    def set_split(self, user_id: str, total: float) -> dict:
        """The person who started the plan enters the total; it is split evenly in whole dollars between them and
        every yes voter (Nessie stores whole dollars). The initiator absorbs any leftover dollars."""
        if user_id not in USER_IDS:
            raise ValueError("Unknown simulator user")
        if not 1 <= total <= 100_000:
            raise ValueError("Enter a total between $1 and $100,000")
        with self.lock:
            if self.template is None or not self.confirmed:
                raise ValueError("Confirm the plan before splitting the cost")
            payee = self.template["initiator"]
            if user_id != payee:
                raise ValueError("Only the person who started the plan adds the cost")
            if self.split and self.split["paid"]:
                raise ValueError("Payments have started, so the total can't change")
            people = sorted({payee} | {uid for uid, approve in self.votes.items() if approve})
            dollars = round(total)
            share = dollars // len(people)
            self.split = {"payee": payee, "total_cents": dollars * 100,
                          "shares": {uid: share * 100 for uid in people if uid != payee}, "paid": {}}
            return self.snapshot()

    def pay(self, user_id: str) -> dict:
        """Sends this member's share from their Nessie account to the payee's. The network call runs outside the lock."""
        with self.lock:
            split = deepcopy(self.split)
            if not split:
                raise ValueError("There is no cost to split yet")
            if user_id not in split["shares"]:
                raise ValueError("This member doesn't owe anything for this plan")
            if user_id in split["paid"] or user_id in self.paying:
                raise ValueError("This share is already paid")
            self.paying.add(user_id)
            title = self.template["title"] if self.template else "plan"
        try:
            ids = nessie.accounts(list(USERS))
            record = nessie.transfer(ids[user_id], ids[split["payee"]], split["shares"][user_id] / 100, f"InstaPlan: {title}")
        finally:
            with self.lock:
                self.paying.discard(user_id)
        with self.lock:
            if not self.split or self.split["payee"] != split["payee"]:
                raise ValueError("The plan changed while paying; check the transfer in Nessie")
            self.split["paid"][user_id] = record
            return self.snapshot()

    def balance(self, user_id: str) -> dict:
        """One member's own balance: their Nessie balance when first shown, plus this plan's payments.
        The browser only asks for the person whose view is active."""
        if user_id not in USER_IDS:
            raise ValueError("Unknown simulator user")
        with self.lock:
            opening = self.opening.get(user_id)
        if opening is None:
            opening = nessie.balance(nessie.accounts(list(USERS))[user_id])
            with self.lock:
                opening = self.opening.setdefault(user_id, opening)
        with self.lock:
            split = deepcopy(self.split) or {"paid": {}, "shares": {}, "payee": None}
        change = -split["shares"][user_id] if user_id in split["paid"] else 0
        if user_id == split["payee"]:
            change += sum(split["shares"][uid] for uid in split["paid"])
        return {"balance": opening + change / 100}

    def snapshot(self) -> dict:
        with self.lock:
            missing = missing_fields(self.template) if self.template else []
            return deepcopy({
                "users": USERS,
                "template": self.template,
                "notes": self.notes,
                "poll": self._poll_locked(),
                "attendance": effective_attendance(self.template) if self.template else {},
                "maps_configured": places.configured(),
                "messages": self.messages,
                "missing": missing,
                "ready": bool(self.template is not None and not missing and not self.pending
                              and not self.processing and not self.error),
                "confirmed": self.confirmed,
                "split": self.split,
                "nessie_configured": nessie.configured(),
                "processing": self.processing,
                "queued": len(self.pending),
                "error": self.error,
                "decisions": self.decisions[-30:],
                "metrics": self.metrics,
                "muse_configured": self.muse.configured,
            })
