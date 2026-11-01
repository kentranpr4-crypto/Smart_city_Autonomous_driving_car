"""Named random streams (same construction as backend.rng, duplicated so comm never imports truth-side modules)."""
from __future__ import annotations
import hashlib
import numpy as np


def rng_stream(seed: int, name: str) -> np.random.Generator:
    key = int.from_bytes(hashlib.sha256(name.encode()).digest()[:4], "big")
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(entropy=seed, spawn_key=(key,))))
