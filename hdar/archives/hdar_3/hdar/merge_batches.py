#!/usr/bin/env python3
"""Merge 4 batch result files into final 100-migration aggregate."""
import json, os, statistics, subprocess, time, hashlib

BATCH_FILES = [
    "sandbox/battle_test_batch_1.json",
    "sandbox/battle_test_batch_2.json",
    "sandbox/battle_test_batch_3.json",
    "sandbox/battle_test_batch_4.json",
]
OUTPUT = "sandbox/battle_test_100_cumulative.json"

def wilson_lower(successes, n):
    if n == 0: return 0.0
    from math import sqrt
    z = 1.96
    p = successes / n
    denom = 1 + z*z / n
    centre = p + z*z / (2*n)
    spread = z * sqrt(p*(1-p)/n + z*z/(4*n*n))
    return (centre - spread) / denom

batches = []
for f in BATCH_FILES:
    if os.path.exists(f):
        with open(f) as fh:
            batches.append(json.load(fh))

all_durations = []
total_success = 0
total_failed = 0
total_checks_passed = 0
total_checks_failed = 0
total_injected = 0
total_assertion_failures = 0
total_infra_exceptions = 0
total_expected_rejections = 0
actual_inject_rejections = 0
total_leaked = 0
all_vm_a_absent = True
all_vm_b_absent = True
failure_types = {}

for b in batches:
    total_success += b["successful"]
    total_failed += b["failed"]
    total_checks_passed += b["total_checks_passed"]
    total_checks_failed += b["total_checks_failed"]
    total_injected += b["failures_injected"]
    total_assertion_failures += b["assertion_failures"]
    total_infra_exceptions += b["infrastructure_exceptions"]
    total_expected_rejections += b["expected_injected_rejections"]
    total_leaked += b["leaked_runtimes"]
    all_vm_a_absent = all_vm_a_absent and b["all_vm_a_absent"]
    all_vm_b_absent = all_vm_b_absent and b["all_vm_b_absent"]
    
    # Fix: batch files use "results" key, not "migrations"
    per_run = b.get("results") or b.get("migrations") or []
    for m in per_run:
        if "duration_ms" in m:
            all_durations.append(m["duration_ms"])
        # Fix: track actual inject_rejected outcomes
        if m.get("inject_failure") and m.get("inject_rejected"):
            actual_inject_rejections += 1
    
    for ft, cnt in b.get("failure_types", {}).items():
        failure_types[ft] = failure_types.get(ft, 0) + cnt

total = sum(b["total_migrations"] for b in batches)

combined = {
    "aggregate_type": "cumulative_4x25_logical",
    "provider": "UnsafeHostProvider (logical simulation — NOT real VMs)",
    "scope": "single host, logical provider, no real VM lifecycle",
    "total_migrations": total,
    "successful": total_success,
    "failed": total_failed,
    "success_rate": total_success / total if total > 0 else 0,
    "wilson_95_lower_bound": wilson_lower(total_success, total),
    "failures_injected": total_injected,
    "failure_types": failure_types,
    "assertion_failures": total_assertion_failures,
    "infrastructure_exceptions": total_infra_exceptions,
    "expected_injected_rejections": total_expected_rejections,
    "actual_inject_rejections": actual_inject_rejections,
    "inject_rejection_discrepancy": total_expected_rejections - actual_inject_rejections,
    "leaked_runtimes": total_leaked,
    "all_vm_a_absent": all_vm_a_absent,
    "all_vm_b_absent": all_vm_b_absent,
    "total_checks_passed": total_checks_passed,
    "total_checks_failed": total_checks_failed,
    "duration_ms": {
        "mean": statistics.mean(all_durations) if all_durations else 0,
        "median": statistics.median(all_durations) if all_durations else 0,
        "stdev": statistics.stdev(all_durations) if len(all_durations) > 1 else 0,
        "min": min(all_durations) if all_durations else 0,
        "max": max(all_durations) if all_durations else 0,
        "p95": sorted(all_durations)[int(len(all_durations) * 0.95)] if all_durations else 0,
    },
    "batches": [
        {
            "batch_num": i+1,
            "successful": b["successful"],
            "failed": b["failed"],
            "total": b["total_migrations"],
            "success_rate": b["success_rate"],
            "wilson_95_lower_bound": b.get("wilson_95_lower_bound", 0),
            "output_file": BATCH_FILES[i],
            "run_id": b.get("run_id", ""),
        }
        for i, b in enumerate(batches)
    ],
    "timestamp": time.time(),
    "provenance": {
        "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=".").decode().strip(),
        "harness": "real_vm_harness.py",
        "failure_injection_rate": 0.40,
        "batch_size": 25,
        "num_batches": 4,
    },
}

with open(OUTPUT, "w") as f:
    json.dump(combined, f, indent=2)

print(f"  Total migrations:     {combined['total_migrations']}")
print(f"  Successful:           {combined['successful']}")
print(f"  Failed:               {combined['failed']}")
print(f"  Success rate:         {combined['success_rate']*100:.1f}%")
print(f"  Wilson 95% LB:        {combined['wilson_95_lower_bound']:.4f}")
print(f"  Failures injected:    {combined['failures_injected']}")
print(f"  Checks passed:        {combined['total_checks_passed']}")
print(f"  Checks failed:        {combined['total_checks_failed']}")
print(f"  Assertion failures:   {combined['assertion_failures']}")
print(f"  Infra exceptions:     {combined['infrastructure_exceptions']}")
print(f"  Expected rejections:  {combined['expected_injected_rejections']}")
print(f"  Leaked runtimes:      {combined['leaked_runtimes']}")
print(f"  All VM A absent:      {combined['all_vm_a_absent']}")
print(f"  All VM B absent:      {combined['all_vm_b_absent']}")
print(f"  Duration mean:        {combined['duration_ms']['mean']/1000:.1f}s")
print(f"  Duration P95:         {combined['duration_ms']['p95']/1000:.1f}s")
print(f"\n  Batch summary:")
for b in combined["batches"]:
    print(f"    Batch {b['batch_num']}: {b['successful']}/{b['total']} ({b['success_rate']*100:.0f}%) Wilson LB={b['wilson_95_lower_bound']:.4f}")
print(f"\n  Output: {OUTPUT}")
print(f"  Git SHA: {combined['provenance']['git_sha']}")
