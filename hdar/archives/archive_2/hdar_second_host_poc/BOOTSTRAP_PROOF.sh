#!/bin/bash
set -e
mkdir -p /tmp/hdar-deploy && cd /tmp/hdar-deploy
pip install cryptography -q 2>&1 | tail -1

# Files will be appended as base64 chunks below
python3 -c "
import base64, json, sys
files = json.load(open("/tmp/hdar-deploy/files.json"))
for name, info in files.items():
    with open(name, "wb") as f:
        f.write(base64.b64decode(info["b64"]))
    print(f"  {name}: {info["size"]} bytes")
"

echo "Files extracted. Running proof..."
RUNNER_SHA="$(python3 -c "import json; print(json.load(open("host_a_build_report.json"))["transport_bundle"]["sha256"])")"
OWNER_KEY="$(cat owner_public_key.txt)"
HOST_A_PLATFORM="$(python3 -c "import json; print(json.load(open("host_a_build_report.json"))["host_a_platform"])")"
echo "Runner SHA-256: $RUNNER_SHA"
echo "Verifying..."
echo "$RUNNER_SHA  run_on_host_b.py" | sha256sum -c -
echo
echo "=== HOST B EXECUTION ==="
python3 run_on_host_b.py --out /tmp/hdar-output --host-label "codespace-independent" --host-a-report host_a_build_report.json --verify-runner-hash "$RUNNER_SHA" --owner-public-key "$OWNER_KEY" --operator-identity "github-codespace" --network-source "codespace-api" > /tmp/host_b_stdout.json 2>/tmp/host_b_stderr.txt; EXIT=$?
if [ $EXIT -ne 0 ]; then echo "FAILED (exit $EXIT)"; cat /tmp/host_b_stderr.txt; exit 1; fi
echo
echo "=== HOST B REPORT ==="
python3 -c "import json; r=json.load(open("/tmp/host_b_stdout.json")); print(f"Platform: {r[\"host_b_platform\"]}"); print(f"Restore: {r[\"restore\"][\"exact\"]}"); tc=r.get(\"task_continuation\",{}); print(f"Task: {tc.get(\"task\",\"N/A\")}"); print(f"Stages: {tc.get(\"stages_completed\",\"N/A\")}"); print(f"Hash match: {tc.get(\"passed\",\"N/A\")}")"
echo
tar xzf transport_capsule_epoch_1_signed.tar.gz
echo "=== VERIFIER ==="
python3 third_party_verifier.py --capsule-e1 capsule_epoch_1 --capsule-e2 /tmp/hdar-output/capsule_epoch_2 --host-b-report /tmp/hdar-output/host_b_report.json --evidence-packet /tmp/hdar-output/host_b_evidence_packet.json --owner-public-key "$OWNER_KEY" --host-a-platform "$HOST_A_PLATFORM" 2>/dev/null
