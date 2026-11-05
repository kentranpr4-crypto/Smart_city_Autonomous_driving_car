"""Safety supervisor (docs/phase2/10 section 4). Independent of the planner: it constrains what the planner proposes.
P1 invariant: a_cmd <= a_local ALWAYS, where a_local is what LOCAL evidence alone would command. Remote information can only ADD braking."""
from __future__ import annotations
import math
from .planner import Planner, occluded
from .types import ADVISORY, CORROBORATED, LOCAL, Decision, EgoState, Hypothesis, Rear

INF = float("inf")


def follower_decel_cap(ego: EgoState, rear: Rear, prm: dict) -> float:
    """Largest ego deceleration [m/s2] that still lets a following human driver (reaction t_r, braking a_f) stop behind the ego. INF = unconstrained / no follower seen."""
    if rear is None or rear.gap is None or rear.v_follower is None or rear.gap > prm["follower_radius_m"]:
        return INF
    vf, tr, af, g = rear.v_follower, prm["follower_react_s"], prm["follower_decel"], rear.gap
    need = vf * tr + vf * vf / (2.0 * af) - g            # extra distance the ego's own stopping distance must provide
    if need <= 0.0:
        return INF
    return max((ego.v * ego.v) / (2.0 * need), 0.0)


class Supervisor:
    def __init__(self, prm: dict, v_ref: float, conservative: bool = False, naive: bool = False):
        self.prm, self.naive = prm, naive
        self.planner = Planner(prm, v_ref, conservative)

    def _cap(self, level: str) -> float:
        p = self.prm
        return {LOCAL: p["a_emerg"], CORROBORATED: p["corroborated_cap"], ADVISORY: p["advisory_cap"]}[level]

    def _contradicted(self, h: Hypothesis, ego: EgoState, local_hyps) -> bool:
        """Remote-only object inside the ego sensor's clear field of view and range, with no local detection nearby (map occluders considered)."""
        p = self.prm
        sx = ego.x + p["sensor_offset_x"]
        dx, dy = h.x - sx, h.y
        rng = math.hypot(dx, dy)
        if rng > p["sensor_range_m"] or rng < 1.0 or dx <= 0:
            return False
        if abs(math.atan2(dy, dx)) > math.radians(p["sensor_fov_deg"]) / 2:
            return False
        if occluded((sx, 0.0), (h.x, h.y), p.get("occluders", ())):
            return False                                   # could be hidden: absence is NOT evidence
        return not any(math.hypot(l.x - h.x, l.y - h.y) < 3.0 for l in local_hyps)

    def decide(self, ego: EgoState, hyps, rear: Rear | None) -> Decision:
        p = self.prm
        local = [h for h in hyps if h.level == LOCAL]
        remote = [h for h in hyps if h.level in (CORROBORATED, ADVISORY)]
        pl = self.planner
        base_items = [(h, self._cap(LOCAL), True, None) for h in local + pl.phantoms(ego)]
        a_local, info_l = pl.candidate(ego, base_items)
        items, reasons, ncontra = list(base_items), [], 0
        for h in remote:
            if (not self.naive) and h.level == ADVISORY and self._contradicted(h, ego, local):
                d = h.x - (ego.x + ego.front_offset)
                ncontra += 1
                if d > 12.0:
                    items.append((h, 1.5, False, p["cautious_speed"]))    # far: speed ceiling only, no hazard braking
                else:
                    items.append((h, self._cap(h.level), True, None))     # close: the local tracker may simply not have confirmed yet -> ordinary ADVISORY hazard (comfort braking at most), never dismissed
                reasons.append("contradicted_hold")
                continue
            items.append((h, self._cap(h.level), True, None))
        a_all, info = pl.candidate(ego, items)
        a_prop = min(a_all, a_local)                       # P1: more evidence can only add braking
        remote_triggered = a_prop < a_local - 0.05
        a_cmd = a_prop
        f_cap = INF if self.naive else follower_decel_cap(ego, rear, p)
        if remote_triggered and not self.naive:
            if f_cap < -a_prop:
                a_cmd = min(a_local, max(a_prop, -f_cap))
                reasons.append("follower_cap")
        if remote_triggered:
            reasons.append("remote_triggered_brake")
        if a_local < -f_cap and not self.naive and f_cap < INF:
            reasons.append("follower_risk_accepted")       # LOCAL hazard braking harder than the follower-safe level: measurable, not hidden
        a_cmd = max(-p["a_emerg"], min(p["a_accel"], a_cmd))
        mode = "emergency" if a_cmd < -p["a_comf"] - 0.05 else "comfort"
        age = max([h.remote_age_s for h in hyps if h.assurance != "local"] + [0.0])
        return Decision(float(a_cmd), mode, float(a_local), float(a_prop), tuple(reasons),
                        {"p_max": info["p_max"], "binding": info["binding"], "n_remote_used": len(remote), "n_contradicted": ncontra, "remote_age_s": age,
                         "follower_cap": None if f_cap == INF else float(f_cap), "remote_triggered": bool(remote_triggered)})
