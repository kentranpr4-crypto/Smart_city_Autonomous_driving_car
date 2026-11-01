"""Named, order-independent random streams (PCG64 + SeedSequence keyed by name)."""
from __future__ import annotations
import hashlib
import numpy as np


def rng_stream(seed: int, name: str) -> np.random.Generator:
    key = int.from_bytes(hashlib.sha256(name.encode()).digest()[:4], "big")
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(entropy=seed, spawn_key=(key,))))
