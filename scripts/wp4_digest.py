#!/usr/bin/env python3
"""Deterministic digest of a WP4 results.json: removes wall-clock-dependent fields (runtime, wall_s, verdicts of runtime metrics) and hashes the rest, so that a clean-room re-run can be compared bit-for-bit."""
import hashlib, json, sys
def scrub(o):
    if isinstance(o, dict):
        return {k: scrub(v) for k, v in o.items() if "runtime" not in k and k != "wall_s"}
    if isinstance(o, list): return [scrub(v) for v in o]
    return o
r = json.load(open(sys.argv[1]))
r["verdicts"] = [v for v in r["verdicts"] if v["id"] != "H11"]
print(hashlib.sha256(json.dumps(scrub(r), sort_keys=True).encode()).hexdigest())
