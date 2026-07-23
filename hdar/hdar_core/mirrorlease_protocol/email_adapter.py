"""Optional disposable-email spool adapter.

It does not configure or send through a mail provider. A provider drops an
RFC 822 message into the private inbox directory; this adapter emits an RFC
822 response into the outbox after routing through the same engine.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

from .engine import MirrorLeaseEngine, ProtocolError


def extract_json(message) -> dict:
    candidates = []
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() in {"application/json", "text/plain"}:
                candidates.append(part.get_content())
    else:
        candidates.append(message.get_content())
    for value in candidates:
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, TypeError, json.JSONDecodeError):
            continue
    raise ProtocolError("invalid_email", "Email must contain one JSON object.")


def process_email(path: Path, engine: MirrorLeaseEngine) -> EmailMessage:
    incoming = BytesParser(policy=default).parsebytes(path.read_bytes())
    body = extract_json(incoming)
    kind = body.pop("kind", "knock")
    try:
        result = engine.knock(body, "email") if kind == "knock" else engine.request(body, "email")
        status = "accepted"
    except ProtocolError as exc:
        result = exc.to_dict()
        status = "rejected"
    response = EmailMessage()
    response["From"] = "mirrorlease@localhost"
    response["To"] = incoming.get("Reply-To") or incoming.get("From") or "undisclosed@localhost"
    response["Subject"] = f"MirrorLease {status}: {incoming.get('Subject', 'request')}"
    if incoming.get("Message-ID"):
        response["In-Reply-To"] = incoming["Message-ID"]
    response.set_content(json.dumps(result, sort_keys=True, indent=2))
    return response


def drain(inbox: Path, outbox: Path, root=None) -> int:
    inbox.mkdir(parents=True, exist_ok=True, mode=0o700)
    outbox.mkdir(parents=True, exist_ok=True, mode=0o700)
    engine = MirrorLeaseEngine(root=root)
    count = 0
    for source in sorted(inbox.glob("*.eml")):
        response = process_email(source, engine)
        destination = outbox / f"{source.stem}.response.eml"
        destination.write_bytes(response.as_bytes())
        os.chmod(destination, 0o600)
        source.rename(source.with_suffix(".processed"))
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="MirrorLease disposable email spool")
    parser.add_argument("--inbox", required=True)
    parser.add_argument("--outbox", required=True)
    parser.add_argument("--root")
    args = parser.parse_args()
    print(json.dumps({"processed": drain(Path(args.inbox), Path(args.outbox), args.root)}))


if __name__ == "__main__":
    main()
