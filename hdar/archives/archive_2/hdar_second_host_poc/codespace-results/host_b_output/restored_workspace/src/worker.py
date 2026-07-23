#!/usr/bin/env python3
"""Multi-stage analysis pipeline — Host B continuation task.

Stages:
  1. parse    — Parse JSONL input records
  2. filter   — Remove invalid/incomplete records
  3. aggregate — Group by category, compute statistics
  4. classify — Assign risk tiers based on thresholds
  5. report   — Generate final structured report

Each stage writes an intermediate artifact to output/stage_<name>.json
Each stage includes parent_hash linking to previous stage output (Merkle-like chain)
Final output: output/final_report.json
"""
import json
import sys
import hashlib
from pathlib import Path
from collections import defaultdict


def canonical_json(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stage_hash(result: dict) -> str:
    """Compute canonical hash of a stage result, excluding the hash field itself."""
    content = {k: v for k, v in result.items() if k != "stage_hash"}
    return sha256_bytes(canonical_json(content).encode())


def stage_parse(workspace: Path, parent_hash: str = None) -> dict:
    """Stage 1: Parse JSONL input records."""
    input_path = workspace / "data" / "input_records.jsonl"
    records = []
    for line in input_path.read_text().strip().split("\n"):
        if line.strip():
            records.append(json.loads(line))
    result = {
        "stage": "parse",
        "stage_index": 1,
        "parent_hash": parent_hash,
        "records_loaded": len(records),
        "first_id": records[0]["id"],
        "last_id": records[-1]["id"],
    }
    result["stage_hash"] = stage_hash(result)
    return result


def stage_filter(workspace: Path, records: list, parent_hash: str) -> dict:
    """Stage 2: Filter out invalid/incomplete records."""
    valid = []
    rejected = []
    for r in records:
        if not r.get("id") or not r.get("category") or "value" not in r:
            rejected.append({"id": r.get("id", "unknown"), "reason": "missing_fields"})
        elif not isinstance(r["value"], (int, float)) or r["value"] < 0:
            rejected.append({"id": r["id"], "reason": "invalid_value"})
        else:
            valid.append(r)
    result = {
        "stage": "filter",
        "stage_index": 2,
        "parent_hash": parent_hash,
        "input_count": len(records),
        "valid_count": len(valid),
        "rejected_count": len(rejected),
        "rejected": rejected,
    }
    result["stage_hash"] = stage_hash(result)
    return result


def stage_aggregate(workspace: Path, records: list, parent_hash: str) -> dict:
    """Stage 3: Aggregate by category with statistics."""
    by_category = defaultdict(list)
    for r in records:
        by_category[r["category"]].append(r["value"])
    stats = {}
    for cat, values in sorted(by_category.items()):
        stats[cat] = {
            "count": len(values),
            "sum": round(sum(values), 4),
            "mean": round(sum(values) / len(values), 4),
            "min": min(values),
            "max": max(values),
            "median": sorted(values)[len(values) // 2],
        }
    result = {
        "stage": "aggregate",
        "stage_index": 3,
        "parent_hash": parent_hash,
        "categories": list(sorted(by_category.keys())),
        "stats": stats,
    }
    result["stage_hash"] = stage_hash(result)
    return result


def stage_classify(workspace: Path, records: list, stats: dict, parent_hash: str) -> dict:
    """Stage 4: Classify records into risk tiers based on category mean."""
    tiers = {"critical": [], "high": [], "medium": [], "low": []}
    for r in records:
        cat_mean = stats[r["category"]]["mean"]
        ratio = r["value"] / cat_mean if cat_mean > 0 else 0
        if ratio >= 2.0:
            tiers["critical"].append(r["id"])
        elif ratio >= 1.5:
            tiers["high"].append(r["id"])
        elif ratio >= 0.5:
            tiers["medium"].append(r["id"])
        else:
            tiers["low"].append(r["id"])
    result = {
        "stage": "classify",
        "stage_index": 4,
        "parent_hash": parent_hash,
        "tier_counts": {k: len(v) for k, v in tiers.items()},
        "tier_members": tiers,
    }
    result["stage_hash"] = stage_hash(result)
    return result


def stage_report(
    workspace: Path,
    parse_result,
    filter_result,
    aggregate_result,
    classify_result,
    parent_hash: str,
) -> dict:
    """Stage 5: Generate final structured report."""
    result = {
        "stage": "report",
        "stage_index": 5,
        "parent_hash": parent_hash,
        "pipeline": "multi_stage_analysis_pipeline",
        "summary": {
            "total_input": parse_result["records_loaded"],
            "valid_records": filter_result["valid_count"],
            "rejected": filter_result["rejected_count"],
            "categories": aggregate_result["categories"],
            "tier_distribution": classify_result["tier_counts"],
        },
        "category_stats": aggregate_result["stats"],
        "tier_members": classify_result["tier_members"],
        "metadata": {
            "stages_completed": 5,
            "version": "1.1",
            "stage_chain": {
                "parse": parse_result["stage_hash"],
                "filter": filter_result["stage_hash"],
                "aggregate": aggregate_result["stage_hash"],
                "classify": classify_result["stage_hash"],
            },
        },
    }
    result["stage_hash"] = stage_hash(result)
    return result


def verify_chain(stages: list) -> bool:
    """Verify the internal Merkle-like stage chain."""
    prev_hash = None
    for s in stages:
        if s.get("parent_hash") != prev_hash:
            return False
        recomputed = stage_hash(s)
        if recomputed != s.get("stage_hash"):
            return False
        prev_hash = s["stage_hash"]
    return True


def main():
    workspace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    output_dir = workspace / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Stage 1: Parse
    parse_result = stage_parse(workspace, parent_hash=None)
    (output_dir / "stage_parse.json").write_text(
        json.dumps(parse_result, indent=2, sort_keys=True) + "\n"
    )
    print(f"Stage 1 (parse): {parse_result['records_loaded']} records loaded, hash={parse_result['stage_hash'][:16]}")

    # Re-load records for subsequent stages
    input_path = workspace / "data" / "input_records.jsonl"
    records = [
        json.loads(l)
        for l in input_path.read_text().strip().split("\n")
        if l.strip()
    ]

    # Stage 2: Filter
    filter_result = stage_filter(workspace, records, parent_hash=parse_result["stage_hash"])
    (output_dir / "stage_filter.json").write_text(
        json.dumps(filter_result, indent=2, sort_keys=True) + "\n"
    )
    print(
        f"Stage 2 (filter): {filter_result['valid_count']} valid, "
        f"{filter_result['rejected_count']} rejected, hash={filter_result['stage_hash'][:16]}"
    )

    valid_records = [
        r
        for r in records
        if r.get("id")
        and r.get("category")
        and isinstance(r.get("value"), (int, float))
        and r["value"] >= 0
    ]

    # Stage 3: Aggregate
    aggregate_result = stage_aggregate(workspace, valid_records, parent_hash=filter_result["stage_hash"])
    (output_dir / "stage_aggregate.json").write_text(
        json.dumps(aggregate_result, indent=2, sort_keys=True) + "\n"
    )
    print(f"Stage 3 (aggregate): {len(aggregate_result['categories'])} categories, hash={aggregate_result['stage_hash'][:16]}")

    # Stage 4: Classify
    classify_result = stage_classify(
        workspace, valid_records, aggregate_result["stats"], parent_hash=aggregate_result["stage_hash"]
    )
    (output_dir / "stage_classify.json").write_text(
        json.dumps(classify_result, indent=2, sort_keys=True) + "\n"
    )
    print(f"Stage 4 (classify): {classify_result['tier_counts']}, hash={classify_result['stage_hash'][:16]}")

    # Stage 5: Report
    report = stage_report(
        workspace,
        parse_result,
        filter_result,
        aggregate_result,
        classify_result,
        parent_hash=classify_result["stage_hash"],
    )
    (output_dir / "final_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    (output_dir / "stage_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    print(f"Stage 5 (report): final_report.json written, hash={report['stage_hash'][:16]}")

    # Verify internal chain
    all_stages = [parse_result, filter_result, aggregate_result, classify_result, report]
    chain_valid = verify_chain(all_stages)
    print(f"Stage chain verification: {'PASS' if chain_valid else 'FAIL'}")

    if not chain_valid:
        print("ERROR: Internal stage chain broken — parent_hash linkage failed")
        sys.exit(1)

    # Write chain proof
    chain_proof = {
        "pipeline": "multi_stage_analysis_pipeline",
        "stages": [
            {"stage": s["stage"], "index": s["stage_index"], "hash": s["stage_hash"], "parent_hash": s["parent_hash"]}
            for s in all_stages
        ],
        "chain_valid": chain_valid,
        "root_hash": report["stage_hash"],
    }
    (output_dir / "stage_chain_proof.json").write_text(
        json.dumps(chain_proof, indent=2, sort_keys=True) + "\n"
    )

    report_hash = sha256_bytes(canonical_json(report).encode())
    print(f"Final report canonical hash: {report_hash}")


if __name__ == "__main__":
    main()
