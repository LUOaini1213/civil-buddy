"""A stand-in for the model API so the UI end-to-end run needs no key and no network.

POST /v1/chat/completions: streams OpenAI-style delta frames, one token every 50 ms
(300 ms when the last user message contains 慢, 40 tokens when it contains 长), then [DONE].
Non-stream requests get one completion. Prints "READY <port>" once listening.
"""
from __future__ import annotations

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):  # quiet
        pass

    def do_POST(self):
        length = int(self.headers.get("content-length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        last = ""
        for m in body.get("messages") or []:
            if m.get("role") == "user":
                last = str(m.get("content") or "")
        n = 40 if "长" in last else 12
        dt = 0.3 if "慢" in last else 0.05
        pieces = [f"片段{i} " for i in range(n)]
        if not body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"id": "fake", "choices": [{"index": 0, "message": {"role": "assistant", "content": "".join(pieces)}, "finish_reason": "stop"}]}).encode())
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            for piece in pieces:
                frame = {"id": "fake", "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}]}
                self.wfile.write(f"data: {json.dumps(frame, ensure_ascii=False)}\n\n".encode())
                self.wfile.flush()
                time.sleep(dt)
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"READY {server.server_port}", flush=True)
    server.serve_forever()
