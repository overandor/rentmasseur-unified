#!/usr/bin/env python3
"""Apply small, idempotent runtime wiring updates to the static dashboard."""
from __future__ import annotations

import argparse
from pathlib import Path

TRIAL_HELPER = r"""
    async function createTrial(payload){
      const endpoints=[];
      if(!location.hostname.endsWith('.hf.space'))endpoints.push(`${location.origin}/api/trials`);
      endpoints.push(`${API_BASE}/api/trials`);
      let lastError=new Error('No trial endpoint was available.');
      for(const endpoint of [...new Set(endpoints)]){
        const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),18000);
        try{
          const response=await fetch(endpoint,{method:'POST',signal:controller.signal,headers:{'content-type':'application/json'},body:JSON.stringify(payload)});
          let data={};
          try{data=await response.json()}catch{}
          if(response.status===404||response.status===405){lastError=new Error(`${endpoint} does not expose trial intake`);continue}
          if(!response.ok)throw new Error(data.error||data.reason||`${endpoint} returned ${response.status}`);
          return {...data,endpoint};
        }catch(error){
          lastError=error;
          if(endpoint===endpoints[endpoints.length-1])throw error;
        }finally{clearTimeout(timer)}
      }
      throw lastError;
    }
""".strip("\n")


def patch(path: Path) -> None:
    source = path.read_text()

    legacy = "const result=await api('/api/metrics/ingest',{method:'POST',body:payload,timeout:18000});"
    direct = "const result=await api('/api/trials',{method:'POST',body:payload,timeout:18000});"
    routed = "const result=await createTrial(payload);"
    if routed not in source:
        if direct in source:
            source = source.replace(direct, routed, 1)
        elif legacy in source:
            source = source.replace(legacy, routed, 1)
        else:
            raise SystemExit("Could not find trial submission endpoint")

    if "async function createTrial(payload)" not in source:
        anchor = "    function capability(id,detailId,status,detail,tone='neutral')"
        if anchor not in source:
            raise SystemExit("Could not find dashboard helper anchor")
        source = source.replace(anchor, TRIAL_HELPER + "\n" + anchor, 1)

    replacements = {
        "This sends a `trial_signup` event to the live optimizer.":
            "This creates a dedicated trial record through the active multicloud host.",
        "This creates a dedicated trial record in the live optimizer.":
            "This creates a dedicated trial record through the active multicloud host.",
        "The optimizer accepted the event and returned this receipt:":
            "The active trial endpoint accepted the request and returned this receipt:",
        "result.receipt||result.trial_id||'Receipt created'":
            "result.receiptId||result.receipt||result.trial_id||'Receipt created'",
    }
    for old, new in replacements.items():
        source = source.replace(old, new)

    path.write_text(source)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    patch(args.path)
    print(f"patched {args.path}")


if __name__ == "__main__":
    main()
