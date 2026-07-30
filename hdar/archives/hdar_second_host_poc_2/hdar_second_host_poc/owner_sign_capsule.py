#!/usr/bin/env python3
"""HDAR Owner Signing Tool — Step 1 of the tightened seed criterion.

Host A generates an Ed25519 owner keypair, signs the capsule manifest,
and embeds the signature + public key into the manifest.

Usage:
    # Generate a new owner keypair and sign an existing capsule
    python3 owner_sign_capsule.py sign \
        --capsule-dir capsule_epoch_1 \
        --owner-key-file owner_keypair.json

    # Verify an owner signature on a capsule (used by Host B or third party)
    python3 owner_sign_capsule.py verify \
        --capsule-dir capsule_epoch_1 \
        --owner-public-key <hex>

If --owner-key-file does not exist, a new Ed25519 keypair is generated
and written to that path. If it exists, the existing key is reused.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

CHUNK_SIZE = 1024 * 1024


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def generate_owner_keypair() -> dict:
    """Generate an Ed25519 keypair for the owner (Host A)."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        priv_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return {
            "algorithm": "ed25519",
            "private_key_hex": priv_bytes.hex(),
            "public_key_hex": pub_bytes.hex(),
            "production_grade": True,
        }
    except ImportError:
        print("ERROR: cryptography package is required for Ed25519 signing.", file=sys.stderr)
        print("Install with: pip install cryptography", file=sys.stderr)
        raise SystemExit(1)


def load_or_generate_keypair(key_file: Path) -> dict:
    if key_file.exists():
        return json.loads(key_file.read_text())
    keypair = generate_owner_keypair()
    key_file.write_text(json.dumps(keypair, indent=2, sort_keys=True) + "\n")
    print(f"Generated new owner Ed25519 keypair: {key_file}", file=sys.stderr)
    return keypair


def sign_manifest(manifest: dict, keypair: dict) -> dict:
    """Sign the manifest content (excluding signature fields) with the owner key."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(keypair["private_key_hex"]))
    # Sign the canonical JSON of the manifest without signature fields
    signing_content = {k: v for k, v in manifest.items() if k not in ("owner_signature", "owner_public_key", "manifest_hash")}
    signature = private_key.sign(canonical_json(signing_content))
    return {
        "owner_signature": signature.hex(),
        "owner_public_key": keypair["public_key_hex"],
        "owner_signature_algorithm": "ed25519",
    }


def verify_owner_signature(manifest: dict, public_key_hex: str | None = None) -> dict:
    """Verify the owner signature on a manifest.

    Returns dict with ok, reason, and details.
    """
    problems = []
    pub_hex = public_key_hex or manifest.get("owner_public_key")
    sig_hex = manifest.get("owner_signature")

    if not pub_hex:
        return {"ok": False, "reason": "no owner_public_key in manifest and none provided"}
    if not sig_hex:
        return {"ok": False, "reason": "no owner_signature in manifest"}
    if manifest.get("owner_signature_algorithm") != "ed25519":
        return {"ok": False, "reason": f"unsupported signature algorithm: {manifest.get('owner_signature_algorithm')}"}

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))
        signing_content = {k: v for k, v in manifest.items() if k not in ("owner_signature", "owner_public_key", "manifest_hash")}
        public_key.verify(bytes.fromhex(sig_hex), canonical_json(signing_content))
        return {
            "ok": True,
            "reason": "owner signature verified",
            "owner_public_key": pub_hex,
            "algorithm": "ed25519",
        }
    except InvalidSignature:
        return {"ok": False, "reason": "owner signature INVALID — content does not match signature", "owner_public_key": pub_hex}
    except ImportError:
        return {"ok": False, "reason": "cryptography package not available — cannot verify Ed25519"}
    except Exception as e:
        return {"ok": False, "reason": f"verification error: {e}"}


def cmd_sign(args) -> int:
    capsule_dir = Path(args.capsule_dir)
    manifest_path = capsule_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: manifest not found: {manifest_path}", file=sys.stderr)
        return 1

    manifest = json.loads(manifest_path.read_text())
    keypair = load_or_generate_keypair(Path(args.owner_key_file))

    # Set signature metadata BEFORE signing so it's included in signed content
    manifest["owner_signature_algorithm"] = "ed25519"
    manifest["signature_mode"] = "ed25519-owner-signed"
    sig_fields = sign_manifest(manifest, keypair)
    manifest["owner_signature"] = sig_fields["owner_signature"]
    manifest["owner_public_key"] = sig_fields["owner_public_key"]

    # Recompute manifest_hash with signature fields excluded
    manifest["manifest_hash"] = sha256_bytes(canonical_json(
        {k: v for k, v in manifest.items() if k not in ("manifest_hash", "owner_signature", "owner_public_key", "owner_signature_algorithm", "host_signature", "host_public_key", "host_signature_algorithm")}
    ))

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"Owner signature embedded in {manifest_path}", file=sys.stderr)
    print(f"  owner_public_key: {sig_fields['owner_public_key']}", file=sys.stderr)
    print(f"  manifest_hash: {manifest['manifest_hash']}", file=sys.stderr)

    # Also update the receipt to reference the new manifest_hash
    receipt_path = capsule_dir / "receipt.json"
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        receipt["manifest_hash"] = manifest["manifest_hash"]
        receipt["owner_signed"] = True
        receipt["owner_public_key"] = sig_fields["owner_public_key"]
        receipt["receipt_hash"] = sha256_bytes(canonical_json(
            {k: v for k, v in receipt.items() if k not in ("receipt_hash", "host_signature", "host_public_key", "host_signature_algorithm")}
        ))
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        print(f"Receipt updated: {receipt_path}", file=sys.stderr)

    # Output summary as JSON on stdout
    summary = {
        "action": "owner_sign",
        "capsule_dir": str(capsule_dir),
        "manifest_hash": manifest["manifest_hash"],
        "owner_public_key": sig_fields["owner_public_key"],
        "signature_algorithm": "ed25519",
        "signature_mode": "ed25519-owner-signed",
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def cmd_verify(args) -> int:
    capsule_dir = Path(args.capsule_dir)
    manifest_path = capsule_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: manifest not found: {manifest_path}", file=sys.stderr)
        return 1

    manifest = json.loads(manifest_path.read_text())
    result = verify_owner_signature(manifest, args.owner_public_key)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="HDAR Owner Capsule Signing Tool")
    sub = ap.add_subparsers(dest="command", required=True)

    sign_ap = sub.add_parser("sign", help="Sign a capsule manifest with an Ed25519 owner key")
    sign_ap.add_argument("--capsule-dir", required=True, help="Path to capsule directory containing manifest.json")
    sign_ap.add_argument("--owner-key-file", default="owner_keypair.json", help="Path to owner keypair JSON (created if missing)")

    verify_ap = sub.add_parser("verify", help="Verify owner signature on a capsule manifest")
    verify_ap.add_argument("--capsule-dir", required=True, help="Path to capsule directory containing manifest.json")
    verify_ap.add_argument("--owner-public-key", default="", help="Expected owner public key hex (optional, uses manifest if omitted)")

    args = ap.parse_args()
    if args.command == "sign":
        return cmd_sign(args)
    elif args.command == "verify":
        return cmd_verify(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
