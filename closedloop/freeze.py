"""Freeze record helper: deterministic hashes of the files that define the WP5 policy, physics and protocol. FREEZE.json is written once before the final evaluation."""
import hashlib, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
FROZEN = ["planning", "fusion", "comm", "perception", "backend", "closedloop/conditions.py", "closedloop/runner.py", "closedloop/metrics.py", "closedloop/preregistration.json",
          "experiments/conditions.py", "scripts/run_wp5_closedloop.py", "schemas", "scenarios"]


def tree_hashes() -> dict:
    out = {}
    for item in FROZEN:
        p = ROOT / item
        files = [p] if p.is_file() else sorted(q for q in p.rglob("*") if q.is_file() and "__pycache__" not in q.parts and q.suffix in (".py", ".json", ".yaml", ".yml"))
        h = hashlib.sha256()
        for f in files:
            h.update(str(f.relative_to(ROOT)).encode()); h.update(b"\0"); h.update(f.read_bytes()); h.update(b"\0")
        out[item] = h.hexdigest()
    return out
