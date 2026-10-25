"""Engine-level probes that need no live Muse: voting, races, limits, note growth, HTTP edge cases."""

import json
import threading
import time
import urllib.error
import urllib.request

from ..engine import ListeningEngine, merge_notes

RESULTS = []


def probe(name):
    def wrap(fn):
        try:
            RESULTS.append((name, "ok", fn()))
        except Exception as exc:  # noqa: BLE001 - a probe crashing is itself a finding
            RESULTS.append((name, "EXC", f"{type(exc).__name__}: {exc}"))
        return fn
    return wrap


class Fake:
    configured = True

    def __init__(self, delay=0.0, updates=None):
        self.delay, self.updates = delay, updates

    def extract(self, template, batch, before=None, after=None, notes=""):
        time.sleep(self.delay)
        ups = self.updates(batch) if self.updates else [
            {"field": "when.flexibility", "user_id": m["user_id"], "value": None, "source_message_id": m["id"]} for m in batch]
        return ups, {}, {}

    def predict(self, template, notes, recent, empty):
        return [], {}


def idle(e):
    for _ in range(300):
        s = e.snapshot()
        if not s["processing"] and not s["queued"]:
            return s
        time.sleep(0.02)


def ready_engine(**kw):
    e = ListeningEngine(muse=Fake(**kw), debounce_seconds=0.02)
    e.start("Plan", "Dining", "Austin")
    for u in ("u1", "u2", "u3", "u4"):
        e.add_message(u, "flexible")
    idle(e)
    return e


@probe("vote: 2 yes + 2 no confirms at 50%")
def _():
    e = ready_engine()
    e.vote("u1", True); e.vote("u3", False); e.vote("u4", False)
    s = e.vote("u2", True)
    return {"confirmed": s["confirmed"], "poll": {k: s["poll"][k] for k in ("yes", "no", "needed")}}


@probe("vote: thresholds 40/50/60 → votes needed of 4")
def _():
    out = {}
    for th in (0.4, 0.5, 0.6):
        e = ready_engine(); e.set_threshold(th); out[th] = e.snapshot()["poll"]["needed"]
    return out


@probe("vote: changing threshold after votes confirms/unconfirms?")
def _():
    e = ready_engine(); e.set_threshold(0.6); e.vote("u1", True); e.vote("u2", True)
    before = e.snapshot()["confirmed"]; e.set_threshold(0.4); s = e.snapshot()
    return {"confirmed_before": before, "after_lowering": s["confirmed"], "yes": s["poll"]["yes"], "needed": s["poll"]["needed"]}


@probe("vote: user can flip vote; confirmed plan can't be voted again")
def _():
    e = ready_engine(); e.vote("u1", False); e.vote("u1", True); e.vote("u2", True)
    try:
        e.vote("u3", False); return "vote after confirm accepted"
    except ValueError as exc:
        return f"rejected: {exc}"


@probe("vote: new message while poll open resets votes?")
def _():
    e = ready_engine(); e.vote("u1", True)
    e.add_message("u2", "actually wait"); s = idle(e)
    return {"votes_after_message": s["poll"]["votes"], "note": "fake muse returns flexible again, plan unchanged"}


@probe("vote: late 'no' cannot block, silent members can't be skipped")
def _():
    e = ListeningEngine(muse=Fake(), debounce_seconds=0.02); e.start("Plan", "Dining", "Austin")
    for u in ("u1", "u2", "u3"):
        e.add_message(u, "flexible")
    s = idle(e)
    return {"poll_open_with_three_of_four_availabilities": s["poll"]["open"], "missing": s["missing"]}


@probe("race: destination picked while Muse is mid-call survives")
def _():
    e = ListeningEngine(muse=Fake(delay=0.5), debounce_seconds=0.02); e.start("Plan", "Dining", "Austin")
    e.add_message("u1", "hi"); time.sleep(0.2)
    e.template["where"]["destination"] = {"name": "X", "place_id": "p", "address": "a", "lat": 0, "lng": 0}  # same effect as set_destination
    idle(e)
    return {"destination_kept": e.snapshot()["template"]["where"]["destination"] is not None}


@probe("race: starting a new plan while a batch is in flight")
def _():
    e = ListeningEngine(muse=Fake(delay=0.5), debounce_seconds=0.02); e.start("Old", "Dining", "Austin")
    e.add_message("u1", "hi"); time.sleep(0.2); e.start("New", "Travel", "Dallas"); time.sleep(0.8)
    s = e.snapshot()
    return {"title": s["template"]["title"], "flex": s["template"]["when"]["flexibility"], "messages": len(s["messages"])}


@probe("limits: 2000 vs 2001 chars, whitespace, emoji")
def _():
    e = ListeningEngine(muse=Fake(), debounce_seconds=0.02); e.start("Plan", "Dining", "Austin")
    res = {}
    for label, text in {"2000": "a" * 2000, "2001": "a" * 2001, "blank": "   ", "emoji2000": "😂" * 2000}.items():
        try:
            e.add_message("u1", text); res[label] = "accepted"
        except ValueError as exc:
            res[label] = str(exc)
    return res


@probe("notes: left-truncation at 3000 chars cuts the oldest facts mid-line")
def _():
    notes = ""
    for i in range(120):
        notes = merge_notes(notes, {"append": [f"fact {i}: maya prefers option {i}"]})
    return {"len": len(notes), "starts_with": notes[:40], "first_fact_kept": "fact 0:" in notes}


@probe("merge_notes: replace with non-string / append non-list")
def _():
    return [merge_notes("a", {"replace": 5, "append": "x"}), merge_notes("a", {"replace": None, "append": [1, None, "- - ok"]})]


@probe("updates: >30 updates silently truncated")
def _():
    ups = lambda batch: [{"field": "preferences", "user_id": "u1", "value": [f"p{i}"], "source_message_id": batch[0]["id"]} for i in range(40)]
    e = ListeningEngine(muse=Fake(updates=ups), debounce_seconds=0.02); e.start("Plan", "Dining", "Austin")
    e.add_message("u1", "hi"); s = idle(e)
    return {"decisions": len(s["decisions"])}


@probe("updates: two updates same field in one batch — last wins (even if an older message)")
def _():
    ups = lambda batch: [{"field": "meal_type", "user_id": None, "value": "lunch", "source_message_id": batch[1]["id"]},
                         {"field": "meal_type", "user_id": None, "value": "dinner", "source_message_id": batch[0]["id"]}]
    e = ListeningEngine(muse=Fake(updates=ups), debounce_seconds=0.5); e.start("Plan", "Dining", "Austin")
    e.add_message("u1", "dinner"); e.add_message("u2", "no lunch"); s = idle(e)
    return s["template"]["cluster"]


@probe("updates: Muse can write search_area over the initiator's chosen city")
def _():
    ups = lambda batch: [{"field": "where.search_area", "user_id": None, "value": "Japan", "source_message_id": batch[0]["id"]}]
    e = ListeningEngine(muse=Fake(updates=ups), debounce_seconds=0.02); e.start("Plan", "Dining", "Austin, TX")
    e.add_message("u1", "japan?"); s = idle(e)
    return {"search_area": s["template"]["where"]["search_area"], "base_location_kept": s["template"]["base_location"]}


@probe("updates: hint is accepted even when an exact destination exists; hint never cleared")
def _():
    ups = lambda batch: [{"field": "where.destination_hint", "user_id": None, "value": "Chipotle", "source_message_id": batch[0]["id"]}]
    e = ListeningEngine(muse=Fake(updates=ups), debounce_seconds=0.02); e.start("Plan", "Dining", "")
    e.template["where"]["destination"] = {"name": "Cabo Bob's", "place_id": "p", "address": "a", "lat": 0, "lng": 0}
    e.add_message("u1", "chipotle?"); s = idle(e)
    return s["template"]["where"]


@probe("updates: cluster value types (cuisine str, accommodation 'cabin', meal 'Brunch ')")
def _():
    from ..contracts import apply_updates, new_template
    t = new_template("t", "Travel", "x"); m = {"id": "m", "user_id": "u1"}
    out = apply_updates(t, [{"field": "accommodation", "value": "cabin", "source_message_id": "m"},
                            {"field": "accommodation", "value": "Airbnb ", "source_message_id": "m"},
                            {"field": "trip_type", "value": "road trip", "source_message_id": "m"},
                            {"field": "trip_type", "value": ["flight", "train"], "source_message_id": "m"}], [m])
    return [(d["field"], d["accepted"], d["reason"]) for d in out[1]]


@probe("updates: when.flexibility accepts any label; nothing normalises or dedups windows")
def _():
    from ..contracts import apply_updates, new_template
    t = new_template("t", "Dining", "x"); m = {"id": "m", "user_id": "u1"}
    r, d = apply_updates(t, [{"field": "when.flexibility", "user_id": "u1", "source_message_id": "m",
                              "value": [{"label": "friday"}, {"label": "Friday"}, {"label": "asdf"}, {"label": "never"}]}], [m])
    return r["when"]["flexibility"]


@probe("budget: bool/NaN/inf/huge/negative/str")
def _():
    from ..contracts import apply_updates, new_template
    t = new_template("t", "Dining", "x"); m = {"id": "m", "user_id": "u1"}
    vals = [True, float("nan"), float("inf"), 10**12, -5, "50", 49.99, 0]
    _, d = apply_updates(t, [{"field": "budget", "user_id": "u1", "value": v, "source_message_id": "m"} for v in vals], [m])
    return [(str(v), x["accepted"]) for v, x in zip(vals, d)]


@probe("http: cross-origin write + oversize body + non-JSON")
def _():
    import subprocess, sys
    from http.server import ThreadingHTTPServer
    from .. import server
    srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    out = {}
    def post(path, data, headers=None):
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method="POST", headers=headers or {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status
        except urllib.error.HTTPError as exc:
            return f"{exc.code} {exc.read()[:80]}"
    out["cross_origin_text_plain_session"] = post("/api/session", json.dumps({"title": "evil", "topic": "Dining"}).encode(), {"Content-Type": "text/plain", "Origin": "https://evil.example"})
    out["oversize_8k"] = post("/api/messages", json.dumps({"user_id": "u1", "text": "😂" * 2000}).encode())
    out["not_json"] = post("/api/messages", b"hello")
    out["bad_vote"] = post("/api/vote", json.dumps({"user_id": "u1", "approve": "no"}).encode())
    out["origin_any_user"] = post("/api/origin", json.dumps({"user_id": "u9", "lat": 1, "lng": 1}).encode())
    srv.shutdown()
    return out


def main() -> None:
    for name, status, result in RESULTS:
        print(f"### {name}\n- {status}: `{json.dumps(result, ensure_ascii=False, default=str)[:600]}`\n")


if __name__ == "__main__":
    main()
