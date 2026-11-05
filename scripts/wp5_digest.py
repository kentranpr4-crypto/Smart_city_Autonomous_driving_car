#!/usr/bin/env python3
"""Deterministic digest of a WP5 results.json: drops wall-clock-dependent fields (decision latency, wall time and the latency verdict W-20), hashes the rest."""
import hashlib, json, sys
def scrub(o):
    if isinstance(o, dict): return {k: scrub(v) for k, v in o.items() if "latency" not in k and k != "wall_s"}
    if isinstance(o, list): return [scrub(v) for v in o]
    return o
r = json.load(open(sys.argv[1])); r["verdicts"] = [v for v in r["verdicts"] if v["id"] != "W-20"]
print(hashlib.sha256(json.dumps(scrub(r), sort_keys=True).encode()).hexdigest())
