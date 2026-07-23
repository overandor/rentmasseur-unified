"""Guarded HTTPS, GPT Action, and Streamable HTTP MCP adapter."""

from __future__ import annotations

import argparse
import json
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .engine import MirrorLeaseEngine, ProtocolError, parse_invitation


MAX_BODY = 1024 * 1024


class MirrorLeaseHandler(BaseHTTPRequestHandler):
    server_version = "MirrorLease/1"

    def log_message(self, _format, *_args):
        return

    @property
    def engine(self) -> MirrorLeaseEngine:
        return self.server.engine  # type: ignore[attr-defined]

    def _json(self, status: int, body: dict) -> None:
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'")
        self.end_headers()
        self.wfile.write(raw)

    def _body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ProtocolError("invalid_length", "Content-Length is invalid.") from exc
        if length <= 0 or length > MAX_BODY:
            raise ProtocolError("invalid_length", "Request body must be between 1 byte and 1 MiB.", 413)
        try:
            body = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as exc:
            raise ProtocolError("invalid_json", "Request body must be JSON.") from exc
        if not isinstance(body, dict):
            raise ProtocolError("invalid_json", "Request body must be a JSON object.")
        return body

    def _bearer(self) -> str:
        value = self.headers.get("Authorization", "")
        return value[7:] if value.startswith("Bearer ") else ""

    def do_GET(self):
        if urlparse(self.path).path == "/health":
            self._json(200, {"ok": True, "service": "mirrorlease-guardian", "protocol": "mirrorlease/v1"})
            return
        self._json(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        try:
            path = urlparse(self.path).path
            body = self._body()
            if path == "/v1/knocks":
                result = self.engine.knock(body, self.headers.get("X-MirrorLease-Transport", "https"))
            elif path == "/v1/requests":
                body["token"] = self._bearer()
                result = self.engine.request(body, self.headers.get("X-MirrorLease-Transport", "https"))
            elif path == "/mcp":
                result = self._mcp(body)
            else:
                raise ProtocolError("not_found", "Endpoint not found.", 404)
            self._json(200, result)
        except ProtocolError as exc:
            self._json(exc.status, exc.to_dict())
        except Exception:
            self._json(500, {"ok": False, "error": "internal_error", "message": "Request failed safely."})

    def _mcp(self, body: dict) -> dict:
        request_id = body.get("id")
        method = body.get("method")
        if method == "initialize":
            value = {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mirrorlease", "version": "1.0.0"},
            }
        elif method == "tools/list":
            value = {"tools": mcp_tools()}
        elif method == "tools/call":
            params = body.get("params") or {}
            args = dict(params.get("arguments") or {})
            name = params.get("name")
            if name == "mirrorlease_knock":
                out = self.engine.knock(args, "mcp")
            elif name == "mirrorlease_request":
                args["token"] = self._bearer()
                out = self.engine.request(args, "mcp")
            else:
                raise ProtocolError("unknown_tool", "MCP tool is not registered.", 404)
            value = {"content": [{"type": "text", "text": json.dumps(out, sort_keys=True)}], "structuredContent": out}
        else:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}
        return {"jsonrpc": "2.0", "id": request_id, "result": value}


def mcp_tools() -> list:
    return [
        {
            "name": "mirrorlease_knock",
            "description": "Present a signed MirrorLease invitation and receive public file metadata.",
            "inputSchema": {
                "type": "object", "required": ["invitation"],
                "properties": {"invitation": {"type": "string"}, "agent_id": {"type": "string"}, "conversation_label": {"type": "string"}},
            },
        },
        {
            "name": "mirrorlease_request",
            "description": "Request one operation allowed by the lease. Bearer auth must be the lease token.",
            "inputSchema": {
                "type": "object", "required": ["invitation_id", "citizen_id", "operation"],
                "properties": {
                    "invitation_id": {"type": "string"}, "citizen_id": {"type": "string"},
                    "operation": {"type": "string", "enum": ["read", "summarize", "verify_hash"]},
                    "agent_id": {"type": "string"}, "conversation_label": {"type": "string"},
                },
            },
        },
    ]


def serve(host: str, port: int, cert: str, key: str, root=None) -> None:
    if not cert or not key:
        raise SystemExit("MirrorLease refuses to start without an explicit TLS certificate and key.")
    server = ThreadingHTTPServer((host, port), MirrorLeaseHandler)
    server.engine = MirrorLeaseEngine(root=root)  # type: ignore[attr-defined]
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="MirrorLease guarded HTTPS and MCP gateway")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9443)
    parser.add_argument("--cert", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--root")
    args = parser.parse_args()
    serve(args.host, args.port, args.cert, args.key, args.root)


if __name__ == "__main__":
    main()
