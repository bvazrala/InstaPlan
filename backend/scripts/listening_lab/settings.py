"""Read single named settings from the environment, the lab's .env, or backend/.env. Keys never go to the browser."""

import os
from pathlib import Path

_FILES = (Path(__file__).parent / ".env", Path(__file__).resolve().parents[2] / ".env")


def env(name: str) -> str:
    if os.environ.get(name):
        return os.environ[name]
    for path in _FILES:
        if path.is_file():
            for line in path.read_text().splitlines():
                key, _, value = line.partition("=")
                if key.strip() == name and value.strip():
                    return value.strip().strip("\"'")
    return ""
