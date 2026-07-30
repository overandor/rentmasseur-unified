#!/usr/bin/env python3
"""Trigger 33 workflow runs and monitor results."""
import subprocess, time, json

RUNS = 33
triggered = []

print(f"Triggering {RUNS} workflow runs...")
for i in range(RUNS):
    result = subprocess.run(
        ["gh", "workflow", "run", "availability-keeper.yml"],
        capture_output=True, text=True,
        cwd="/Users/alep/Downloads/MEMBRA::SURFACE=BUILD@LIVE/02_AI_Agents/rentmasseur-extension"
    )
    if result.returncode == 0:
        # Extract run ID from output
        url_line = [l for l in result.stdout.split('\n') if 'actions/runs' in l]
        if url_line:
            run_id = url_line[0].strip().split('/')[-1]
            triggered.append(run_id)
        print(f"  [{i+1}/{RUNS}] Triggered")
    else:
        print(f"  [{i+1}/{RUNS}] FAILED: {result.stderr.strip()}")
    time.sleep(2)  # Small delay to avoid rate limiting

print(f"\nTriggered {len(triggered)} runs")
print("Run IDs:", triggered)

# Save for monitoring
with open("/Users/alep/Downloads/rentmasseur-optimizer/_workflow_runs.json", "w") as f:
    json.dump(triggered, f)

print("\nWaiting 5 min for runs to progress...")
time.sleep(300)

# Check status of all runs
print("\n=== STATUS CHECK ===")
for rid in triggered:
    result = subprocess.run(
        ["gh", "run", "view", rid, "--json", "status,conclusion,jobs"],
        capture_output=True, text=True,
        cwd="/Users/alep/Downloads/MEMBRA::SURFACE=BUILD@LIVE/02_AI_Agents/rentmasseur-extension"
    )
    if result.returncode == 0:
        data = json.loads(result.stdout)
        status = data.get("status", "?")
        conclusion = data.get("conclusion", "?")
        jobs = data.get("jobs", [])
        job_status = jobs[0].get("status", "?") if jobs else "?"
        steps = jobs[0].get("steps", []) if jobs else []
        avail_step = [s for s in steps if "availability" in s.get("name","").lower() or "Keep" in s.get("name","")]
        avail_status = avail_step[0].get("conclusion", avail_step[0].get("status", "?")) if avail_step else "?"
        visit_step = [s for s in steps if "visit" in s.get("name","").lower()]
        visit_status = visit_step[0].get("conclusion", visit_step[0].get("status", "?")) if visit_step else "?"
        print(f"  {rid}: status={status} conclusion={conclusion} avail={avail_status} visit={visit_status}")
    else:
        print(f"  {rid}: error checking")

print("\nDone.")
