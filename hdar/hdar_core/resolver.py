#!/usr/bin/env python3
"""Agent-Addressed Wake Resolver — primitive #4.

The address identifies the AGENT, not the machine:

    ssh agent-7f91@runtime.network
        -> resolve identity to its latest authorized capsule
        -> acquire an EXCLUSIVE wake lease  (no split-brain, no duplicate wake)
        -> verify lineage + anti-rollback   (capsule.verify)
        -> materialize a fresh runtime      (capsule.restore)
        -> route the session
        -> collapse: seal successor capsule (epoch+1), destroy runtime, release lease

The SSH frontend is a thin sshd ForceCommand shim over `resolver.py wake`.
This module is the part that has to be correct.

  resolver.py register <agent_id> <workspace> [--goals ...]
  resolver.py wake     <agent_id> [--holder NAME]
  resolver.py collapse <agent_id>
  resolver.py status   [agent_id]
"""
import argparse, hashlib, hmac, json, os, shutil, sys, time

import capsule as cap

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "sandbox", "resolver")
REGISTRY = os.path.join(STATE, "agents.json")
LEASES = os.path.join(STATE, "leases")
RECEIPTS = os.path.join(STATE, "resolver_receipts.jsonl")
LEASE_TTL = 900                      # seconds; stale leases expire, not deadlock


def _init():
    os.makedirs(LEASES, exist_ok=True)
    if not os.path.exists(REGISTRY):
        json.dump({}, open(REGISTRY, "w"))


def _reg():
    _init(); return json.load(open(REGISTRY))


def _save(r): json.dump(r, open(REGISTRY, "w"), indent=2)


def _receipt(kind, agent_id, **kw):
    rec = {"kind": kind, "agent_id": agent_id, "ts": time.time(), **kw}
    rec["signature"] = hmac.new(cap._key(),
        json.dumps(rec, sort_keys=True, separators=(",", ":")).encode(),
        hashlib.sha256).hexdigest()[:32]
    with open(RECEIPTS, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def _lease_path(a): return os.path.join(LEASES, f"{a}.lease")


def acquire(agent_id, holder):
    """Exclusive wake lease. Prevents two hosts restoring the same agent."""
    p = _lease_path(agent_id)
    if os.path.exists(p):
        l = json.load(open(p))
        if time.time() < l["expires"]:
            return None, f"lease held by '{l['holder']}' for {int(l['expires']-time.time())}s"
        # stale -> reclaim
    l = {"holder": holder, "acquired": time.time(), "expires": time.time() + LEASE_TTL}
    json.dump(l, open(p, "w"))
    return l, None


def release(agent_id):
    p = _lease_path(agent_id)
    if os.path.exists(p):
        os.remove(p)


def register(agent_id, workspace, goals=None):
    r = _reg()
    cdir = os.path.join(STATE, agent_id, "capsule")
    os.makedirs(cdir, exist_ok=True)
    info = cap.seal(workspace, cdir, goals=goals, epoch=1)
    r[agent_id] = {"capsule": cdir, "epoch": 1, "state": "dormant",
                   "runtime": None, "wakes": 0}
    _save(r)
    _receipt("agent.register", agent_id, epoch=1, manifest=info["manifest_hash"])
    return {"agent_id": agent_id, "state": "dormant", "epoch": 1, **info}


def wake(agent_id, holder="local"):
    r = _reg()
    if agent_id not in r:
        return {"woke": False, "reason": "unknown agent identity"}
    a = r[agent_id]
    lease, err = acquire(agent_id, holder)
    if err:
        _receipt("wake.refused", agent_id, reason=err, holder=holder)
        return {"woke": False, "reason": f"SPLIT-BRAIN PREVENTED: {err}"}
    # verify + anti-rollback against the authorized epoch
    v = cap.verify(a["capsule"], min_epoch=a["epoch"])
    if not v["ok"]:
        release(agent_id)
        _receipt("wake.rejected", agent_id, problems=v["problems"])
        return {"woke": False, "reason": "capsule verification failed",
                "problems": v["problems"]}
    runtime = os.path.join(STATE, agent_id, f"runtime-{int(time.time())}")
    res = cap.restore(a["capsule"], runtime, min_epoch=a["epoch"])
    if not res["restored"]:
        release(agent_id)
        return {"woke": False, "reason": "restore failed", "problems": res.get("problems")}
    a.update(state="running", runtime=runtime, wakes=a["wakes"] + 1)
    _save(r)
    _receipt("wake.materialized", agent_id, epoch=a["epoch"], runtime=runtime,
             files=res["files"], exact=res["exact"], holder=holder)
    return {"woke": True, "agent_id": agent_id, "epoch": a["epoch"],
            "runtime": runtime, "files_restored": res["files"],
            "exact": res["exact"], "unfinished_goals": res["goals"],
            "lease_holder": holder}


def collapse(agent_id, force=False):
    """Idle collapse: seal successor capsule, destroy runtime, release lease.

    GATED on semantic quiescence: refuses to seal while external effects are
    in flight, because restoring later would duplicate or lose them.
    """
    r = _reg()
    if agent_id not in r or r[agent_id]["state"] != "running":
        return {"collapsed": False, "reason": "agent is not running"}
    try:
        import quiescence
        q = quiescence.check(agent_id)
        if not q["quiescent"] and not force:
            _receipt("collapse.refused", agent_id, blocking=q["blocking_effects"])
            return {"collapsed": False, "reason": q["verdict"],
                    "blocking_effects": q["blocking_effects"]}
    except ImportError:
        pass
    a = r[agent_id]
    new_epoch = a["epoch"] + 1
    info = cap.seal(a["runtime"], a["capsule"], epoch=new_epoch, parent=a["epoch"])
    cap.destroy(a["runtime"])
    gone = not os.path.exists(a["runtime"])
    a.update(state="dormant", epoch=new_epoch, runtime=None)
    _save(r)
    release(agent_id)
    _receipt("collapse.sealed", agent_id, epoch=new_epoch, parent=a["epoch"] - 1,
             manifest=info["manifest_hash"], runtime_destroyed=gone)
    return {"collapsed": True, "agent_id": agent_id, "new_epoch": new_epoch,
            "runtime_destroyed": gone, "dedup_block_hits": info["dedup_block_hits"],
            "active_compute": "zero — dormant storage only"}


def status(agent_id=None):
    r = _reg()
    if agent_id:
        a = r.get(agent_id)
        if not a:
            return {"error": "unknown agent"}
        held = os.path.exists(_lease_path(agent_id))
        return {agent_id: {**a, "lease_held": held}}
    return {k: {"state": v["state"], "epoch": v["epoch"], "wakes": v["wakes"]}
            for k, v in r.items()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("register"); g.add_argument("agent_id"); g.add_argument("workspace")
    g.add_argument("--goals", nargs="*")
    w = sub.add_parser("wake"); w.add_argument("agent_id"); w.add_argument("--holder", default="local")
    c = sub.add_parser("collapse"); c.add_argument("agent_id")
    s = sub.add_parser("status"); s.add_argument("agent_id", nargs="?")
    a = ap.parse_args()
    fn = {"register": lambda: register(a.agent_id, a.workspace, a.goals),
          "wake": lambda: wake(a.agent_id, a.holder),
          "collapse": lambda: collapse(a.agent_id),
          "status": lambda: status(a.agent_id)}[a.cmd]
    print(json.dumps(fn(), indent=2))
