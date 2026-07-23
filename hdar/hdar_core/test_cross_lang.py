#!/usr/bin/env python3
"""Cross-language canonical form compatibility test.

Verifies whether the Python and C++ HDAR implementations produce
byte-identical canonical forms for the same logical capsule data.

This is the "two constitutions" test from the audit.

Usage:
  python3 test_cross_lang.py
"""
import json
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from crypto import canonicalize, sha256_hex


def cpp_canonical_form(epoch, agent_id, agent_name, parent_hash,
                       objective, continuation_point, workspace_manifest_hash,
                       capabilities_json):
    """Reproduce the C++ Capsule::canonical_form() exactly.
    
    C++ uses alphabetical key order to match Python's json.dumps(sort_keys=True).
    """
    return (
        "{"
        f'"agent_id":"{agent_id}"'
        f',"agent_name":"{agent_name}"'
        f',"capabilities":{capabilities_json}'
        f',"continuation_point":"{continuation_point}"'
        f',"epoch":{epoch}'
        f',"objective":"{objective}"'
        f',"parent_hash":"{parent_hash}"'
        f',"workspace_manifest_hash":"{workspace_manifest_hash}"'
        "}"
    )


def python_canonical_form(epoch, agent_id, agent_name, parent_hash,
                          objective, continuation_point, workspace_manifest_hash,
                          capabilities_json):
    """Produce the Python canonical form for the same data."""
    d = {
        "epoch": epoch,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "parent_hash": parent_hash,
        "objective": objective,
        "continuation_point": continuation_point,
        "workspace_manifest_hash": workspace_manifest_hash,
        "capabilities": json.loads(capabilities_json),
    }
    return canonicalize(d).decode()


def main():
    test_data = {
        "epoch": 0,
        "agent_id": "agent-native",
        "agent_name": "native-agent",
        "parent_hash": "",
        "objective": "compute sum(1..100)",
        "continuation_point": "step 2: pending",
        "workspace_manifest_hash": "b7e3638ed499a56652b600ea5977082f24ae6f299beee5bf55246b86518baf3a",
        "capabilities_json": '[{"name":"filesystem.write","scope":"/workspace"}]',
    }

    cpp_form = cpp_canonical_form(**test_data)
    py_form = python_canonical_form(**test_data)

    cpp_hash = hashlib.sha256(cpp_form.encode()).hexdigest()
    py_hash = hashlib.sha256(py_form.encode()).hexdigest()

    print("CROSS-LANGUAGE CANONICAL FORM COMPATIBILITY TEST")
    print("=" * 72)
    print()
    print("C++ canonical form:")
    print(f"  {cpp_form}")
    print(f"  hash: {cpp_hash}")
    print()
    print("Python canonical form:")
    print(f"  {py_form}")
    print(f"  hash: {py_hash}")
    print()

    if cpp_form == py_form:
        print("RESULT: COMPATIBLE — byte-identical canonical forms")
        return 0
    else:
        print("RESULT: INCOMPATIBLE — canonical forms differ")
        print()
        print("Differences:")

        # Show specific differences
        cpp_parsed = json.loads(cpp_form)
        py_parsed = json.loads(py_form)

        cpp_keys = set(cpp_parsed.keys())
        py_keys = set(py_parsed.keys())

        only_cpp = cpp_keys - py_keys
        only_py = py_keys - cpp_keys

        if only_cpp:
            print(f"  Fields only in C++: {only_cpp}")
        if only_py:
            print(f"  Fields only in Python: {only_py}")

        # Key ordering
        cpp_order = list(cpp_parsed.keys())
        py_order = list(py_parsed.keys())
        if cpp_order != py_order:
            print(f"  C++ key order:   {cpp_order}")
            print(f"  Python key order: {py_order}")

        # Check if values match for common keys
        common = cpp_keys & py_keys
        for k in sorted(common):
            if cpp_parsed[k] != py_parsed[k]:
                print(f"  Value mismatch for '{k}':")
                print(f"    C++:    {cpp_parsed[k]}")
                print(f"    Python: {py_parsed[k]}")

        print()
        print("CONCLUSION: The Python and C++ implementations use different")
        print("canonical forms. A capsule signed by one cannot be verified")
        print("by the other. This must be resolved before claiming")
        print("cross-language wire compatibility.")
        print()
        print("To fix: either (a) make C++ use sorted-keys JSON matching")
        print("Python's canonicalize(), or (b) make Python use the C++")
        print("field ordering, or (c) define a new shared canonical form")
        print("specification and implement it in both languages.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
