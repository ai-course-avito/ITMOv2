"""A tiny OpenAI-compatible server for the tests: a model that answers without a provider.

  POST /v1/chat/completions    the answer depends on the model name:
      fake/pong*   "pong"
      fake/echo*   "echo: " and the last thing the user said
      fake/slow*   forty words, one every FAKE_DELAY seconds (0.25): a stream that can be interrupted
  GET  /log?model=<name>       every request this model got: path, whether it was a stream, the Authorization header, the last user text and the whole conversation it was given as [role, text] pairs
  GET  /health

Streams and plain answers both work, with usage; nothing else is implemented.
"""

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

DELAY = float(os.getenv("FAKE_DELAY", "0.25"))
LOG: list = []


def last_user_text(messages: list) -> str:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict))
    return ""


def words_for(model: str, messages: list) -> list:
    if model.startswith("fake/slow"):
        return [f"word{i}" for i in range(40)]
    if model.startswith("fake/echo"):
        return ("echo: " + last_user_text(messages)).split(" ")
    return ["pong"]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # quiet
        pass

    def _json(self, status: int, payload) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/health":
            return self._json(200, {"status": "ok"})
        if url.path == "/log":
            model = parse_qs(url.query).get("model", [None])[0]
            return self._json(200, [e for e in LOG if model is None or e["model"] == model])
        self._json(404, {"detail": "not found"})

    def do_POST(self):
        url = urlparse(self.path)
        if not url.path.endswith("/chat/completions"):
            return self._json(404, {"detail": "not found"})
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        model = body.get("model", "")
        messages = body.get("messages", [])
        stream = bool(body.get("stream"))
        LOG.append(
            {
                "path": url.path,
                "model": model,
                "stream": stream,
                "authorization": self.headers.get("Authorization"),
                "last_user": last_user_text(messages),
                "messages": [[m.get("role"), m.get("content") if isinstance(m.get("content"), str) else last_user_text([m])] for m in messages],
                "keys": sorted(body),
            }
        )
        words = words_for(model, messages)
        usage = {"prompt_tokens": 7, "completion_tokens": len(words), "total_tokens": 7 + len(words)}
        base = {"id": "fake-1", "created": int(time.time()), "model": model}

        if not stream:
            return self._json(
                200,
                {
                    **base,
                    "object": "chat.completion",
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": " ".join(words)}, "finish_reason": "stop"}],
                    "usage": usage,
                },
            )

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        def send(chunk: dict) -> None:
            data = f"data: {json.dumps(chunk)}\n\n".encode()
            self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
            self.wfile.flush()

        chunk = {**base, "object": "chat.completion.chunk"}
        try:
            send({**chunk, "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}]})
            for i, word in enumerate(words):
                time.sleep(DELAY if len(words) > 1 else 0)
                send({**chunk, "choices": [{"index": 0, "delta": {"content": ("" if i == 0 else " ") + word}, "finish_reason": None}]})
            send({**chunk, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
            send({**chunk, "choices": [], "usage": usage})
            done = b"data: [DONE]\n\n"
            self.wfile.write(f"{len(done):x}\r\n".encode() + done + b"\r\n0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # the client went away (an interrupt): nothing to finish


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
