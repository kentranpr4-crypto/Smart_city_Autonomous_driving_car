"""Tracker presets. Decision (owner, WP3): tracks published to V2X use 3-of-4 confirmation; 2-of-3 is kept ONLY as an experimental baseline.
(The TrackerConfig class default stays 2-of-3 so that all WP2 tests/evidence remain valid.)"""
from .tracker import TrackerConfig

V2X_PUBLISH = TrackerConfig(confirm_m=3, confirm_n=4)
EXPERIMENTAL_2OF3_BASELINE = TrackerConfig(confirm_m=2, confirm_n=3)


def confirmation_label(cfg: TrackerConfig) -> str:
    """'3of4' for the production policy, otherwise '<m>of<n>-experimental'."""
    return "3of4" if (cfg.confirm_m, cfg.confirm_n) == (3, 4) else f"{cfg.confirm_m}of{cfg.confirm_n}-experimental"
