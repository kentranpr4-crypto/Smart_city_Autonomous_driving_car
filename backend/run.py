"""CLI: python -m backend.run SCENARIO.yaml --seed N --out DIR [--verify-hash HEX]
Writes DIR/telemetry.jsonl and DIR/manifest.json (R-DOC-01). Exit 3 if --verify-hash mismatches."""
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, platform, subprocess, sys
import numpy
from .scenario import load_scenario
from .telemetry import TelemetryWriter
from .world import World, BACKEND_NAME, BACKEND_VERSION
from .params import LIMITATIONS


def _git(*a):
    try:
        return subprocess.run(["git", *a], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return None


def environment() -> dict:
    return {"python": platform.python_version(), "numpy": numpy.__version__, "platform": platform.platform(), "machine": platform.machine()}


def run_scenario(path, seed: int, out_dir=None, keep=False):
    scn = load_scenario(path)
    out = pathlib.Path(out_dir) if out_dir else None
    if out: out.mkdir(parents=True, exist_ok=True)
    tw = TelemetryWriter(out / "telemetry.jsonl" if out else None, keep=keep)
    w = World(scn, seed, tw)
    summary = w.run()
    tw.close()
    manifest = {
        "schema_version": "0.1.0", "scenario": str(path), "scenario_id": scn.id, "config_sha256": scn.config_sha256(), "seed": seed,
        "telemetry_sha256": tw.hexdigest(), "telemetry_lines": tw.count,
        "backend": {"name": BACKEND_NAME, "version": BACKEND_VERSION, "carla_equivalent": False, "limitations": list(LIMITATIONS)},
        "git": {"commit": _git("rev-parse", "HEAD"), "dirty": bool(_git("status", "--porcelain"))},
        "environment": environment(), "summary": summary,
    }
    if out: (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest, tw


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("scenario"); ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", default=None); ap.add_argument("--verify-hash", default="")
    a = ap.parse_args(argv)
    m, _ = run_scenario(a.scenario, a.seed, a.out)
    print(json.dumps({"telemetry_sha256": m["telemetry_sha256"], "lines": m["telemetry_lines"], "summary": m["summary"]}, sort_keys=True))
    if a.verify_hash and a.verify_hash != m["telemetry_sha256"]:
        print(f"HASH MISMATCH expected {a.verify_hash}", file=sys.stderr); return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
