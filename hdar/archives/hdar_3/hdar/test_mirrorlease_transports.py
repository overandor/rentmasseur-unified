#!/usr/bin/env python3

import base64
import hashlib
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from email.message import EmailMessage
from pathlib import Path

from crypto import HostKeyPair, OwnerKeyPair
from mirrorlease_protocol.email_adapter import process_email
from mirrorlease_protocol.engine import MirrorLeaseEngine, canonical
from mirrorlease_protocol.local_cli import create_invitation, engine_for
from mirrorlease_protocol.http_adapter import MirrorLeaseHandler
from http.server import ThreadingHTTPServer
from argparse import Namespace


class Fixture:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mirrorlease-transport-")
        self.root = Path(self.temp.name) / "MirrorLease"
        self.root.joinpath("leases").mkdir(parents=True)
        self.file = Path(self.temp.name) / "sample.txt"
        self.file.write_text("MirrorLease keeps the original file on the owner's laptop.\n")
        self.owner = OwnerKeyPair.generate()
        self.host = HostKeyPair.generate("test-guardian")
        now = time.time()
        self.invitation_id = "a" * 32
        self.mailbox_id = "mirror-test"
        self.token = "b" * 64
        self.challenge = "c" * 32
        self.citizen = "file-" + hashlib.sha256(self.file.read_bytes()).hexdigest()[:16]
        grants = {self.citizen: ["read", "summarize", "verify_hash"]}
        fingerprint = self.owner.fingerprint
        claims = {
            "invitation_id": self.invitation_id,
            "mailbox_id": self.mailbox_id,
            "token_hash": hashlib.sha256(self.token.encode()).hexdigest(),
            "task_description": "test",
            "recipient_id": "",
            "conversation_label": "",
            "challenge": self.challenge,
            "grants": grants,
            "created_at": now,
            "expires_at": now + 3600,
            "issuer_fingerprint": fingerprint,
        }
        signature = self.owner.sign_bytes(canonical(claims))
        public = {
            "invitation_id": self.invitation_id,
            "mailbox_id": self.mailbox_id,
            "token": self.token,
            "task": "test",
            "recipient_id": "",
            "conversation_label": "",
            "challenge": self.challenge,
            "grants": grants,
            "created_at": now,
            "expires_at": now + 3600,
            "issuer_public_key": self.owner.public_key_hex,
            "issuer_fingerprint": fingerprint,
            "lease_signature": signature,
        }
        encoded = base64.urlsafe_b64encode(canonical(public)).decode().rstrip("=")
        self.invitation = "mirrorlease:v1:" + encoded
        private = {
            "version": 1, "invitation_id": self.invitation_id, "mailbox_id": self.mailbox_id,
            "state": "waiting", "created_at": now, "expires_at": now + 3600,
            "token_hash": claims["token_hash"], "challenge": self.challenge, "grants": grants,
            "issuer_public_key": self.owner.public_key_hex, "issuer_fingerprint": fingerprint,
            "lease_signature": signature,
            "private_files": [{"citizen_id": self.citizen, "local_path": str(self.file),
                               "content_hash": hashlib.sha256(self.file.read_bytes()).hexdigest(),
                               "size": self.file.stat().st_size}],
        }
        self.root.joinpath("leases", self.invitation_id + ".json").write_text(json.dumps(private))

        def signer(data):
            return {"signature": self.host.sign_bytes(data), "issuer_public_key": self.host.public_key_hex,
                    "issuer_fingerprint": self.host.fingerprint}
        self.engine = MirrorLeaseEngine(self.root, signer=signer, approver=lambda _r: True)

    def close(self):
        self.temp.cleanup()


class TransportParityTests(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture()

    def tearDown(self):
        self.fx.close()

    def test_all_knocks_share_schema_and_signed_receipts(self):
        outputs = [self.fx.engine.knock({"invitation": self.fx.invitation}, name)
                   for name in ("finder", "https", "gpt_action", "mcp", "email")]
        for name, output in zip(("finder", "https", "gpt_action", "mcp", "email"), outputs):
            self.assertTrue(output["ok"])
            self.assertEqual(output["protocol"], "mirrorlease/v1")
            self.assertEqual(output["lease"]["grants"], outputs[0]["lease"]["grants"])
            receipt = output["receipt"]
            self.assertEqual(receipt["event"]["transport"], name)
            self.assertTrue(receipt["host_signature"])
            self.assertTrue(receipt["receipt_hash"])
        lines = self.fx.root.joinpath("audit.jsonl").read_text().splitlines()
        self.assertEqual(len(lines), 5)
        for previous, current in zip(lines, lines[1:]):
            self.assertEqual(json.loads(current)["previous_receipt_hash"], json.loads(previous)["receipt_hash"])

    def test_request_requires_token_scope_approval_and_current_file(self):
        result = self.fx.engine.request({
            "invitation_id": self.fx.invitation_id, "token": self.fx.token,
            "citizen_id": self.fx.citizen, "operation": "read", "agent_id": "test-agent",
        }, "https")
        self.assertTrue(result["ok"])
        self.assertIn("original file", result["result"]["data"])
        self.assertEqual(result["lease_state"], "used")

    def test_http_gpt_action_and_mcp_route_to_same_engine(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), MirrorLeaseHandler)
        server.engine = self.fx.engine
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            req = urllib.request.Request(base + "/v1/knocks", method="POST",
                data=json.dumps({"invitation": self.fx.invitation}).encode(),
                headers={"Content-Type": "application/json", "X-MirrorLease-Transport": "gpt_action"})
            action = json.loads(urllib.request.urlopen(req).read())
            self.assertEqual(action["receipt"]["event"]["transport"], "gpt_action")
            mcp_body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                "name": "mirrorlease_knock", "arguments": {"invitation": self.fx.invitation}}}
            req = urllib.request.Request(base + "/mcp", method="POST", data=json.dumps(mcp_body).encode(),
                                         headers={"Content-Type": "application/json"})
            mcp = json.loads(urllib.request.urlopen(req).read())
            self.assertEqual(mcp["result"]["structuredContent"]["receipt"]["event"]["transport"], "mcp")
        finally:
            server.shutdown()
            server.server_close()

    def test_email_is_only_a_delivery_adapter(self):
        source = Path(self.fx.temp.name) / "knock.eml"
        message = EmailMessage()
        message["From"] = "agent@example.test"
        message["Subject"] = "knock"
        message.set_content(json.dumps({"kind": "knock", "invitation": self.fx.invitation}))
        source.write_bytes(message.as_bytes())
        response = process_email(source, self.fx.engine)
        payload = json.loads(response.get_content())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["receipt"]["event"]["transport"], "email")

    def test_local_cli_creates_usable_private_lease_and_public_invitation(self):
        root = Path(self.fx.temp.name) / "LocalMirrorLease"
        source = Path(self.fx.temp.name) / "cli-file.txt"
        source.write_text("created from the right-click compatible CLI\n")
        created = create_invitation(Namespace(
            root=str(root), files=[str(source)], hours=1,
            grant=["read", "summarize", "verify_hash"],
            task="CLI smoke", recipient_id="", conversation_label="test-chat",
            clipboard=False,
        ))
        self.assertTrue(created["ok"])
        self.assertTrue(Path(created["private_record"]).exists())
        engine = engine_for(root, yes=True)
        knock = engine.knock({"invitation": created["invitation"], "agent_id": "test"}, "finder")
        citizen_id = knock["files"][0]["citizen_id"]
        encoded = created["invitation"].split(":", 2)[2]
        public = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        request = engine.request({
            "invitation_id": created["invitation_id"],
            "token": public["token"],
            "citizen_id": citizen_id,
            "operation": "read",
            "agent_id": "test",
        }, "https")
        self.assertTrue(request["ok"])
        self.assertIn("right-click compatible", request["result"]["data"])


if __name__ == "__main__":
    unittest.main()
