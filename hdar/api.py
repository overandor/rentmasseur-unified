"""REST API for the HDAR Continuity SDK.

Provides HTTP endpoints for:
  - POST /seal — seal a capsule
  - POST /restore — restore a capsule
  - POST /verify — verify a chain
  - GET /metrics — get metrics
  - GET /events — get events
  - POST /secrets — store a secret
  - GET /secrets/log — get secret access log
  - POST /keys/rotate — rotate owner key
  - GET /health — health check

Uses only the Python standard library (http.server) — no external deps.
For production, wrap with gunicorn/uvicorn behind a reverse proxy.
"""
from __future__ import annotations

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse, parse_qs

HERE = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(HERE))

from sdk import ContinuityClient
from crypto import PublicKey
from capsule.identity import LineageEpoch
from capsule.capabilities import Capability
from continuity import ContinuityCapsule


class ContinuityAPIHandler(BaseHTTPRequestHandler):
    """HTTP handler for the continuity REST API."""

    server_version = "HDAR-Continuity/1.0"

    def _send_json(self, code: int, data: dict):
        body = json.dumps(data, indent=2, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    @property
    def client(self) -> ContinuityClient:
        return self.server.client  # type: ignore

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/health":
            self._send_json(200, {"status": "ok", "version": "1.0"})
        elif path == "/metrics":
            self._send_json(200, self.client.get_metrics())
        elif path == "/events":
            qs = parse_qs(parsed.query)
            since = float(qs.get("since", ["0"])[0])
            self._send_json(200, {"events": self.client.get_events(since)})
        elif path == "/secrets/log":
            self._send_json(200, {"log": self.client.get_secret_access_log()})
        elif path == "/owner/fingerprint":
            self._send_json(200, {"fingerprint": self.client.owner_fingerprint})
        elif path == "/owner/public-key":
            self._send_json(200, {"public_key": self.client.owner_public_key.hex})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            body = self._read_body()

            if path == "/seal":
                caps = []
                for c in body.get("capabilities", []):
                    caps.append(Capability(c["name"], c.get("scope", "")))
                epoch = LineageEpoch.genesis(body["agent_id"])
                if body.get("epoch_sequence") is not None:
                    epoch = LineageEpoch(
                        epoch_id=body.get("epoch_id", ""),
                        agent_id=body["agent_id"],
                        sequence=body["epoch_sequence"],
                        parent_epoch=body.get("parent_epoch"),
                    )
                capsule = self.client.seal(
                    workspace_dir=body["workspace_dir"],
                    agent_id=body["agent_id"],
                    agent_name=body.get("agent_name", ""),
                    objective=body.get("objective", ""),
                    continuation_point=body.get("continuation_point", ""),
                    capabilities=caps,
                    epoch=epoch,
                )
                self._send_json(200, capsule.to_dict())

            elif path == "/restore":
                capsule = ContinuityCapsule.from_dict(body["capsule"])
                result = self.client.restore(
                    capsule, body["workspace_dir"],
                    holder_id=body.get("holder_id", "api"),
                )
                self._send_json(200, result)

            elif path == "/verify":
                capsules = [ContinuityCapsule.from_dict(c) for c in body.get("capsules", [])]
                result = self.client.verify_chain(capsules)
                self._send_json(200, result)

            elif path == "/secrets":
                self.client.store_secret(
                    body["name"],
                    body["value"].encode(),
                )
                self._send_json(200, {"stored": True})

            elif path == "/keys/rotate":
                result = self.client.rotate_key(body.get("reason", "api"))
                self._send_json(200, result)

            elif path == "/recover":
                result = self.client.recover()
                self._send_json(200, result)

            else:
                self._send_json(404, {"error": "not found"})

        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def log_message(self, format, *args):
        # Suppress default logging
        pass


class ContinuityServer(HTTPServer):
    """HTTP server with a ContinuityClient instance."""

    def __init__(self, addr: str, port: int, state_dir: str):
        super().__init__((addr, port), ContinuityAPIHandler)
        self.client = ContinuityClient(state_dir)


def serve(addr: str = "127.0.0.1", port: int = 8390, state_dir: str = "/tmp/hdar-api"):
    """Start the REST API server."""
    server = ContinuityServer(addr, port, state_dir)
    print(f"HDAR Continuity API on http://{addr}:{port}")
    print(f"State: {state_dir}")
    print(f"Owner fingerprint: {server.client.owner_fingerprint}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.client.mark_clean_shutdown()
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="HDAR Continuity REST API")
    ap.add_argument("--addr", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8390)
    ap.add_argument("--state", default="/tmp/hdar-api")
    args = ap.parse_args()
    serve(args.addr, args.port, args.state)
