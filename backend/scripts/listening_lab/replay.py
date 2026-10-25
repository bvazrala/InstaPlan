"""Optional CLI replay of a fixture through the same controller and live Muse client."""

import argparse
import json
import time
from pathlib import Path

from .engine import ListeningEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay a public group chat through Muse")
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.fixture.read_text().splitlines() if line.strip()]
    engine = ListeningEngine()
    engine.start(**rows[0]["session"])
    for row in rows[1:]:
        engine.add_message(row["user_id"], row["text"])
    while True:
        state = engine.snapshot()
        if not state["processing"] and not state["queued"]:
            break
        time.sleep(0.1)
    print(json.dumps({key: state[key] for key in ("template", "missing", "ready", "error", "decisions", "metrics")},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
