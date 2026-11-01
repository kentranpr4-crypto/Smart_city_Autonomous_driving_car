"""Perception stack (tracker). I9: this package may import ONLY from the standard library, numpy, perception.*, and backend.observation
(pure data types). It must never import ground-truth modules (backend.world/truth/sensors/dynamics/collision/scenario).
Enforced by tests/perception/test_iso_*.py (AST scan + subprocess with a blocking import hook)."""
