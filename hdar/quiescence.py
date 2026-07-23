#!/usr/bin/env python3
"""Semantic Quiescence Kernel — primitive #2.

A process can be frozen at any instruction. An agent CANNOT. If you seal while
a payment is in flight, restoring later either duplicates the charge or loses it.

This kernel tracks external effects through their real lifecycle:

    INTENDED -> COMMITTED | FAILED | UNKNOWN

An agent is QUIESCENT only when no effect is INTENDED-or-UNKNOWN. collapse()
must refuse to seal otherwise. On wake, UNKNOWN effects are RECONCILED against
the provider by idempotency key before the agent may act — never re-executed
blindly. That is what stops duplicate real-world effects across a migration.

  quiescence.py intend   <agent> <kind> <idem_key> [--detail ...]
  quiescence.py commit   <agent> <idem_key>
  quiescence.py unknown  <agent> <idem_key>
  quiescence.py check    <agent>
  quiescence.py reconcile <agent>
"""
import argparse, json, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "sandbox", "resolver")
LEDGER = os.path.join(STATE, "effects.jsonl")

BLOCKING = ("INTENDED", "UNKNOWN")


def _load():
    if not os.path.exists(LEDGER):
        return []
    return [json.loads(l) for l in open(LEDGER) if l.strip()]


def _append(rec):
    os.makedirs(STATE, exist_ok=True)
    with open(LEDGER, "a") as f:
        f.write(json.dumps(rec) + "\n")


def _current(agent):
    """Fold the append-only ledger into current state per idempotency key."""
    cur = {}
    for r in _load():
        if r["agent"] != agent:
            continue
        cur[r["idem_key"]] = r
    return cur


def intend(agent, kind, idem_key, detail=None):
    """Record intent BEFORE executing. This is the whole trick."""
    cur = _current(agent)
    if idem_key in cur and cur[idem_key]["state"] == "COMMITTED":
        return {"duplicate_prevented": True, "idem_key": idem_key,
                "reason": "already COMMITTED — refusing to re-execute"}
    rec = {"agent": agent, "kind": kind, "idem_key": idem_key, "state": "INTENDED",
           "detail": detail, "ts": time.time()}
    _append(rec)
    return {"recorded": "INTENDED", "idem_key": idem_key, "kind": kind}


def settle(agent, idem_key, state):
    cur = _current(agent)
    if idem_key not in cur:
        return {"error": "unknown idem_key"}
    rec = {**cur[idem_key], "state": state, "ts": time.time()}
    _append(rec)
    return {"idem_key": idem_key, "state": state}


def check(agent):
    """Is the agent safe to seal? Returns the quiescence verdict."""
    cur = _current(agent)
    blocking = [r for r in cur.values() if r["state"] in BLOCKING]
    return {
        "agent": agent,
        "quiescent": not blocking,
        "blocking_effects": [{"kind": r["kind"], "idem_key": r["idem_key"],
                              "state": r["state"]} for r in blocking],
        "verdict": "SAFE TO SEAL" if not blocking else
                   "REFUSE TO SEAL — external effects in flight",
        "effects_total": len(cur),
    }


def _probe_provider(rec):
    """Ask the provider what actually happened, by idempotency key.

    Real impl: Stripe/GitHub/SMTP lookup by idem key. Here: deterministic stub
    that reports COMMITTED for keys the provider recorded.
    """
    seen = os.path.join(STATE, "provider_committed.json")
    committed = json.load(open(seen)) if os.path.exists(seen) else []
    return "COMMITTED" if rec["idem_key"] in committed else "FAILED"


def reconcile(agent):
    """On wake: resolve UNKNOWN effects before the agent is allowed to act."""
    cur = _current(agent)
    unknown = [r for r in cur.values() if r["state"] == "UNKNOWN"]
    out = []
    for r in unknown:
        truth = _probe_provider(r)
        settle(agent, r["idem_key"], truth)
        out.append({"idem_key": r["idem_key"], "kind": r["kind"],
                    "resolved_to": truth,
                    "action": "do NOT re-execute (already committed)" if truth == "COMMITTED"
                              else "safe to retry"})
    return {"agent": agent, "reconciled": len(out), "results": out,
            "now_quiescent": check(agent)["quiescent"]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("intend"); i.add_argument("agent"); i.add_argument("kind")
    i.add_argument("idem_key"); i.add_argument("--detail")
    c = sub.add_parser("commit"); c.add_argument("agent"); c.add_argument("idem_key")
    u = sub.add_parser("unknown"); u.add_argument("agent"); u.add_argument("idem_key")
    k = sub.add_parser("check"); k.add_argument("agent")
    r = sub.add_parser("reconcile"); r.add_argument("agent")
    a = ap.parse_args()
    fn = {"intend": lambda: intend(a.agent, a.kind, a.idem_key, a.detail),
          "commit": lambda: settle(a.agent, a.idem_key, "COMMITTED"),
          "unknown": lambda: settle(a.agent, a.idem_key, "UNKNOWN"),
          "check": lambda: check(a.agent),
          "reconcile": lambda: reconcile(a.agent)}[a.cmd]
    print(json.dumps(fn(), indent=2))
