"""Run every scenario against live Muse and write a digest per scenario.

    .venv/bin/python -m scripts.listening_lab.sims.run [D01 T05 ...]
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..engine import ListeningEngine
from .scenarios_dining import SCENARIOS as DINING
from .scenarios_entertainment import SCENARIOS as ENTERTAINMENT
from .scenarios_travel import SCENARIOS as TRAVEL

OUT = Path(__file__).parent / "results"
NAMES = {"u1": "Jordan", "u2": "Maya", "u3": "Alex", "u4": "Sam"}


def idle(engine: ListeningEngine, timeout: float = 150) -> None:
    end = time.time() + timeout
    while time.time() < end:
        s = engine.snapshot()
        if not s["processing"] and not s["queued"]:
            return
        time.sleep(0.15)


def compact(template: dict) -> dict:
    where = template["where"]
    return {"when": template["when"]["flexibility"], "place": {"dest": (where["destination"] or {}).get("name"),
            "hint": where["destination_hint"], "area": where["search_area"]},
            "budget": template["budget"], "prefs": template["preferences"],
            "must": template["hard_constraints"], "cluster": template["cluster"]}


def run(sc: dict) -> dict:
    engine = ListeningEngine(debounce_seconds=0.3)
    started = time.time()
    kind = "destination" if sc.get("place_id") else "search_area"
    engine.start(sc["title"], sc["topic"], sc["location"], kind, sc.get("place_id", ""), "u1")
    sent, send_errors, timeline = [], [], []
    for item in sc["msgs"]:
        user, text = item[0], item[1]
        burst = len(item) > 2
        before = len(engine.snapshot()["messages"])
        try:
            engine.add_message(user, text)
            sent.append((user, text))
        except ValueError as exc:
            send_errors.append({"n": len(sent) + len(send_errors) + 1, "user": user, "text": text[:80], "error": str(exc)})
            continue
        if not burst:
            idle(engine)
            snap = engine.snapshot()
            if snap["error"]:
                engine.retry()
                idle(engine)
            timeline.append((len(engine.snapshot()["messages"]), compact(engine.snapshot()["template"])))
    idle(engine)
    snap = engine.snapshot()
    if snap["error"]:
        engine.retry()
        idle(engine)
        snap = engine.snapshot()
    timeline.append((len(snap["messages"]), compact(snap["template"])))
    final = snap
    # Voting: two yes votes (threshold 50% of 4) if the poll is open.
    votes = {"poll_open": final["poll"]["open"], "missing": final["missing"]}
    if final["poll"]["open"]:
        engine.vote("u1", True)
        votes["after_one"] = engine.snapshot()["confirmed"]
        engine.vote("u2", True)
        votes["confirmed"] = engine.snapshot()["confirmed"]
    post_confirm = None
    if engine.snapshot()["confirmed"]:
        try:
            engine.add_message("u3", "wait can we change the time")
        except ValueError as exc:
            post_confirm = str(exc)
    msg_index = {m["id"]: i + 1 for i, m in enumerate(final["messages"])}
    decisions = [{"n": msg_index.get(d.get("source_message_id"), d.get("source_message_id")), **{k: d[k] for k in ("accepted", "field", "user_id", "value", "reason")}}
                 for d in final["decisions"]]
    return {"sc": sc, "final": final, "decisions": decisions, "timeline": timeline, "votes": votes,
            "post_confirm": post_confirm, "send_errors": send_errors, "elapsed": round(time.time() - started, 1),
            "msg_index": msg_index}


def digest(r: dict) -> str:
    sc, f = r["sc"], r["final"]
    t = f["template"]
    lines = [f"## {sc['id']} · {sc['title']} ({sc['topic']})", f"*Edge focus:* {sc['edge']}", ""]
    lines.append("### Chat (n · speaker · text · muse status)")
    status = {m["id"]: m["status"] for m in f["messages"]}
    for i, m in enumerate(f["messages"], 1):
        lines.append(f"{i}. **{NAMES[m['user_id']]}**: {m['text'][:150].replace(chr(10), ' ')} _[{status[m['id']]}]_")
    if r["send_errors"]:
        lines += ["", "### Messages rejected at send", *[f"- #{e['n']} {NAMES[e['user']]} `{e['text']}` → {e['error']}" for e in r["send_errors"]]]
    lines += ["", "### Final template", "```json", json.dumps(compact(t), ensure_ascii=False), "```",
              f"Sources: `{json.dumps(t['sources'])}`" if t["sources"] else ""]
    lines += ["", f"**Missing:** {f['missing'] or 'nothing'} · **Poll open:** {f['poll']['open']} · **Votes:** {r['votes']} · **After confirm:** {r['post_confirm']}"]
    lines += ["", "### Muse notes", "```", f["notes"] or "(empty)", "```"]
    lines += ["", "### Decisions (n = source message)"]
    for d in r["decisions"]:
        mark = "✓" if d["accepted"] else "✗"
        lines.append(f"- {mark} #{d['n']} `{d['field']}` {NAMES.get(d['user_id'], 'group')} = {json.dumps(d['value'], ensure_ascii=False)[:110]}" + ("" if d["accepted"] else f" — **{d['reason']}**"))
    m = f["metrics"]
    lines += ["", f"### Metrics: {m['calls']} calls · {m['batches']} batches · {m['prompt_tokens']} in / {m['completion_tokens']} out ({m['reasoning_tokens']} reasoning) tokens · {r['elapsed']}s · error: {f['error']}"]
    lines += ["", "### Template timeline (message count → change)"]
    last = None
    for n, snap in r["timeline"]:
        diff = {k: v for k, v in snap.items() if not last or last.get(k) != v}
        if diff:
            lines.append(f"- after {n}: `{json.dumps(diff, ensure_ascii=False)[:400]}`")
        last = snap
    return "\n".join(lines) + "\n"


def main() -> None:
    wanted = set(sys.argv[1:])
    scenarios = [s for s in DINING + TRAVEL + ENTERTAINMENT if not wanted or s["id"] in wanted]
    OUT.mkdir(exist_ok=True)
    with ThreadPoolExecutor(6) as pool:
        for r in pool.map(run, scenarios):
            (OUT / f"{r['sc']['id']}.md").write_text(digest(r))
            print(r["sc"]["id"], "done", r["elapsed"], "s", "error" if r["final"]["error"] else "")


if __name__ == "__main__":
    main()
