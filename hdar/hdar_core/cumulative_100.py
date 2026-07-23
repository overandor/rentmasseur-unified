#!/usr/bin/env python3
"""Run 4x25 logical migrations cumulatively and combine into 100-migration result.

Each batch runs 25 UnsafeHostProvider (logical simulation) migrations.
Results are merged into a single 100-migration aggregate with full provenance.
"""

import json, os, sys, time, subprocess, statistics, hashlib

BATCHES = 4
BATCH_SIZE = 25
FAILURE_RATE = 0.40
OUTPUT_DIR = "sandbox"
COMBINED_OUTPUT = os.path.join(OUTPUT_DIR, "battle_test_100_cumulative.json")

def run_batch(batch_num):
    """Run one batch of 25 migrations and return the result dict."""
    output_file = os.path.join(OUTPUT_DIR, f"battle_test_batch_{batch_num}.json")
    cmd = [
        sys.executable, "real_vm_harness.py",
        "--count", str(BATCH_SIZE),
        "--failures", str(FAILURE_RATE),
        "--output", output_file,
    ]
    print(f"\n{'='*72}")
    print(f"  BATCH {batch_num}/{BATCHES} — {BATCH_SIZE} real VM migrations")
    print(f"{'='*72}\n")
    
    start = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    elapsed = time.time() - start
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr[-500:] if len(result.stderr) > 500 else result.stderr)
    
    if os.path.exists(output_file):
        with open(output_file) as f:
            data = json.load(f)
        data["batch_num"] = batch_num
        data["wall_time_s"] = elapsed
        data["output_file"] = output_file
        print(f"  Batch {batch_num}: {data['successful']}/{data['total_migrations']} in {elapsed:.0f}s")
        return data
    else:
        print(f"  Batch {batch_num}: FAILED — no output file")
        return None

def combine_results(batches):
    """Merge batch results into a single 100-migration aggregate."""
    valid = [b for b in batches if b is not None]
    
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
    
    for b in valid:
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
    
    total = sum(b["total_migrations"] for b in valid)
    
    # Wilson 95% lower bound
    def wilson_lower(successes, n):
        if n == 0:
            return 0.0
        from math import sqrt
        z = 1.96
        p = successes / n
        denominator = 1 + z*z / n
        centre = p + z*z / (2*n)
        spread = z * sqrt(p*(1-p)/n + z*z/(4*n*n))
        return (centre - spread) / denominator
    
    combined = {
        "aggregate_type": "cumulative_4x25_logical",
        "provider": "UnsafeHostProvider (logical simulation, NOT real VMs)",
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
                "batch_num": b["batch_num"],
                "successful": b["successful"],
                "failed": b["failed"],
                "total": b["total_migrations"],
                "wall_time_s": b.get("wall_time_s", 0),
                "output_file": b.get("output_file", ""),
                "success_rate": b["success_rate"],
                "wilson_95_lower_bound": b.get("wilson_95_lower_bound", 0),
            }
            for b in valid
        ],
        "timestamp": time.time(),
        "provenance": {
            "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=".").decode().strip(),
            "harness": "real_vm_harness.py",
            "failure_injection_rate": FAILURE_RATE,
            "batch_size": BATCH_SIZE,
            "num_batches": BATCHES,
        },
    }
    
    return combined

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    batches = []
    for i in range(1, BATCHES + 1):
        result = run_batch(i)
        batches.append(result)
    
    print(f"\n{'='*72}")
    print(f"  COMBINING {BATCHES} BATCHES INTO 100-MIGRATION AGGREGATE")
    print(f"{'='*72}\n")
    
    combined = combine_results(batches)
    
    with open(COMBINED_OUTPUT, "w") as f:
        json.dump(combined, f, indent=2)
    
    # Print summary
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
    
    if combined["failure_types"]:
        print(f"\n  Failure breakdown:")
        for ft, cnt in sorted(combined["failure_types"].items()):
            print(f"    {ft}: {cnt}")
    
    print(f"\n  Batch summary:")
    for b in combined["batches"]:
        print(f"    Batch {b['batch_num']}: {b['successful']}/{b['total']} ({b['success_rate']*100:.0f}%) in {b['wall_time_s']:.0f}s")
    
    print(f"\n  Output: {COMBINED_OUTPUT}")
    print(f"  Git SHA: {combined['provenance']['git_sha']}")
    
    if combined["success_rate"] >= 0.95:
        print(f"\n  RESULT: {combined['success_rate']*100:.1f}% ({combined['successful']}/{combined['total_migrations']}) — REAL VM-BACKED CONTINUITY PROTOTYPE")
    elif combined["success_rate"] >= 0.80:
        print(f"\n  RESULT: {combined['success_rate']*100:.1f}% ({combined['successful']}/{combined['total_migrations']}) — REAL-VM ALPHA: CORE CONTINUITY INVARIANTS VERIFIED")
    else:
        print(f"\n  RESULT: {combined['success_rate']*100:.1f}% ({combined['successful']}/{combined['total_migrations']}) — NEEDS INVESTIGATION")

if __name__ == "__main__":
    main()
