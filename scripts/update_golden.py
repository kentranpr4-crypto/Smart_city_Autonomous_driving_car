#!/usr/bin/env python3
"""Record the regression-anchor hash for S00a seed 7 in the CURRENT environment. Run deliberately, review the diff.
The anchor detects unintended behavioural drift; it does NOT prove physical correctness (PHY-02..06 do)."""
import json, pathlib, platform, sys
import numpy
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from backend.run import run_scenario
root = pathlib.Path(__file__).resolve().parents[1]
m, _ = run_scenario(root / "scenarios" / "s00a_physics_sandbox_brake_early.yaml", 7)
g = {"environment": {"python": platform.python_version(), "numpy": numpy.__version__, "machine": platform.machine(), "system": platform.system()},
     "s00a_seed7_sha256": m["telemetry_sha256"], "note": "same-environment regression anchor only (docs/phase2/07 §6)"}
(root / "tests" / "physics" / "golden_hashes.json").write_text(json.dumps(g, indent=2, sort_keys=True) + "\n")
print(json.dumps(g, indent=2))
