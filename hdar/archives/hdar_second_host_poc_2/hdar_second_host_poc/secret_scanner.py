#!/usr/bin/env python3
"""HDAR Secret Detection Scanner — Security boundary #4.

Scans capsule workspaces for credentials, private keys, tokens, and
machine-specific secrets before transport. Blocks capsule sealing if
high-confidence secrets are detected.

Usage:
    python3 secret_scanner.py --workspace <path>
    python3 secret_scanner.py --workspace <path> --json
    python3 secret_scanner.py --workspace <path> --block-on-secrets
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

CHUNK_SIZE = 1024 * 1024

# High-confidence secret patterns (block sealing)
HIGH_CONFIDENCE_PATTERNS = [
    (r"sk-[a-zA-Z0-9]{20,}", "OpenAI API key"),
    (r"sk-or-[a-zA-Z0-9-]{20,}", "OpenRouter API key"),
    (r"AIza[a-zA-Z0-9_-]{35}", "Google API key"),
    (r"hf_[a-zA-Z0-9]{20,}", "Hugging Face token"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub personal access token"),
    (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth token"),
    (r"ghs_[a-zA-Z0-9]{36}", "GitHub server-to-server token"),
    (r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----", "Private key file"),
    (r"xox[baprs]-[a-zA-Z0-9-]{10,}", "Slack token"),
    (r"AKIA[0-9A-Z]{16}", "AWS access key ID"),
    (r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*", "JWT token"),
]

# Medium-confidence patterns (warn but don't block)
MEDIUM_CONFIDENCE_PATTERNS = [
    (r"(?:password|passwd|pwd)\s*[=:]\s*\S+", "Password assignment"),
    (r"(?:secret|api_key|apikey|access_key)\s*[=:]\s*\S+", "API key assignment"),
    (r"(?:token|bearer)\s*[=:]\s*\S+", "Token assignment"),
    (r"postgres(?:ql)?://[^\s]+", "PostgreSQL connection string"),
    (r"mongodb(?:\+srv)?://[^\s]+", "MongoDB connection string"),
    (r"redis://[^\s]+", "Redis connection string"),
    (r"https?://[^/\s]+:[^@/\s]+@", "URL with embedded credentials"),
]

# Mac-specific path patterns (information leakage)
PATH_PATTERNS = [
    (r"/Users/[^/\s]+/", "Absolute macOS user path"),
    (r"/private/tmp/", "macOS private temp path"),
    (r"/var/folders/[a-f0-9/]+", "macOS var folders path"),
]


def scan_file(path: Path) -> list[dict]:
    """Scan a single file for secret patterns."""
    findings = []
    try:
        content = path.read_text(errors="replace")
    except Exception:
        return findings

    for line_num, line in enumerate(content.splitlines(), 1):
        for pattern, description in HIGH_CONFIDENCE_PATTERNS:
            for match in re.finditer(pattern, line):
                findings.append({
                    "severity": "high",
                    "description": description,
                    "file": str(path),
                    "line": line_num,
                    "match_prefix": match.group()[:20] + "...",
                    "action": "block",
                })
        for pattern, description in MEDIUM_CONFIDENCE_PATTERNS:
            for match in re.finditer(pattern, line, re.IGNORECASE):
                findings.append({
                    "severity": "medium",
                    "description": description,
                    "file": str(path),
                    "line": line_num,
                    "match_prefix": match.group()[:20] + "...",
                    "action": "warn",
                })
        for pattern, description in PATH_PATTERNS:
            for match in re.finditer(pattern, line):
                findings.append({
                    "severity": "info",
                    "description": description,
                    "file": str(path),
                    "line": line_num,
                    "match_prefix": match.group()[:30] + "...",
                    "action": "log",
                })
    return findings


def scan_workspace(workspace: Path) -> dict:
    """Scan all files in a workspace for secrets and sensitive patterns."""
    all_findings = []
    files_scanned = 0

    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        # Skip binary files
        try:
            path.read_text(errors="strict")
        except (UnicodeDecodeError, ValueError):
            continue
        except Exception:
            continue
        files_scanned += 1
        findings = scan_file(path)
        all_findings.extend(findings)

    high_count = sum(1 for f in all_findings if f["severity"] == "high")
    medium_count = sum(1 for f in all_findings if f["severity"] == "medium")
    info_count = sum(1 for f in all_findings if f["severity"] == "info")

    return {
        "schema": "hdar.secret-scan/v0.1",
        "workspace": str(workspace),
        "files_scanned": files_scanned,
        "total_findings": len(all_findings),
        "high_severity": high_count,
        "medium_severity": medium_count,
        "info_severity": info_count,
        "block_sealing": high_count > 0,
        "findings": all_findings,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="HDAR Secret Detection Scanner")
    ap.add_argument("--workspace", required=True, help="Path to workspace to scan")
    ap.add_argument("--json", action="store_true", help="Output as JSON")
    ap.add_argument("--block-on-secrets", action="store_true", help="Exit 1 if high-severity secrets found")
    args = ap.parse_args()

    result = scan_workspace(Path(args.workspace))

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"Workspace: {result['workspace']}")
        print(f"Files scanned: {result['files_scanned']}")
        print(f"High severity: {result['high_severity']}")
        print(f"Medium severity: {result['medium_severity']}")
        print(f"Info (paths): {result['info_severity']}")
        print(f"Block sealing: {result['block_sealing']}")
        if result["findings"]:
            print("\nFindings:")
            for f in result["findings"]:
                print(f"  [{f['severity'].upper()}] {f['description']}: {f['file']}:{f['line']} -> {f['match_prefix']}")

    if args.block_on_secrets and result["block_sealing"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
