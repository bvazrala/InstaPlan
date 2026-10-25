"""Local-only dashboard server. Run: python -m scripts.listening_lab.server"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import places
from .engine import ListeningEngine

STATIC = Path(__file__).parent / "static"
ENGINE = ListeningEngine()
MIME = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8"}


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/state":
            self._json(200, ENGINE.snapshot())
            return
        if path == "/api/places":
            query = parse_qs(urlsplit(self.path).query)
            try:
                self._json(200, {"results": places.autocomplete(query.get("q", [""])[0], query.get("token", [""])[0])})
            except RuntimeError as exc:
                self._json(502, {"error": str(exc)})
            return
        files = {"/": "index.html", "/index.html": "index.html",
                 "/app.js": "app.js", "/style.css": "style.css"}
        name = files.get(path)
        if name is None:
            self._json(404, {"error": "Not found"})
            return
        target = STATIC / name
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MIME[target.suffix])
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 8192:
                raise ValueError("Invalid request size")
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError("Expected a JSON object")
            if path == "/api/session":
                result = ENGINE.start(body.get("title", ""), body.get("topic", ""),
                                      body.get("location", ""), body.get("location_kind", "search_area"),
                                      body.get("place_id", ""), body.get("user_id", "u1"))
            elif path == "/api/messages":
                result = ENGINE.add_message(body.get("user_id", ""), body.get("text", ""))
            elif path == "/api/retry":
                result = ENGINE.retry()
            elif path == "/api/destination":
                result = ENGINE.set_destination(str(body.get("place_id", "")))
            elif path == "/api/origin":
                result = ENGINE.set_origin(body.get("user_id", ""), float(body.get("lat")), float(body.get("lng")))
            elif path == "/api/vote":
                result = ENGINE.vote(body.get("user_id", ""), bool(body.get("approve")))
            elif path == "/api/threshold":
                result = ENGINE.set_threshold(float(body.get("value")))
            else:
                self._json(404, {"error": "Not found"})
                return
            self._json(200, result)
        except (ValueError, TypeError, RuntimeError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})

    def log_message(self, format: str, *args: object) -> None:
        # Do not log message bodies, URLs with queries, or model output.
        pass


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Standalone four-user Muse listening dashboard")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Listening lab: http://127.0.0.1:{args.port}")
    print("Muse configured" if ENGINE.muse.configured else "MUSE_API_KEY missing: chat is available; extraction will show an error")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
