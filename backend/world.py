"""Authoritative fixed-step world. No wall-clock access anywhere in this module (I11).

Step order (docs/phase2/07 §1): (1) effective commands -> (2) integrate vehicles -> (3) advance pedestrians and test contacts
-> (4) record frame.  Time is t = step * dt computed from an integer step counter.
"""
from __future__ import annotations
import hashlib, math
import numpy as np
from .params import LIMITATIONS
from .dynamics import VehicleState, initial_state, step_vehicle
from .collision import sat_obb_obb, capsule_hits_obb, dist_segment_obb, closest_point_obb
from .scenario import Scenario, ScriptedCmd
from .telemetry import TelemetryWriter

BACKEND_NAME = "lightweight-planar-physics"
BACKEND_VERSION = "0.1.0"


def rng_stream(seed: int, name: str) -> np.random.Generator:
    key = int.from_bytes(hashlib.sha256(name.encode()).digest()[:4], "big")
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(entropy=seed, spawn_key=(key,))))


def _draw(x, rng):
    return float(rng.uniform(x["low"], x["high"])) if isinstance(x, dict) else float(x)


class Pedestrian:
    def __init__(self, spec, seed):
        rng = rng_stream(seed, f"ped:{spec.id}")
        self.id, self.radius = spec.id, spec.radius
        self.speed = _draw(spec.speed, rng)          # draw order is part of the contract
        self.t_start = _draw(spec.start_time, rng)
        self.path = spec.path
        self.cum = [0.0]
        for a, b in zip(self.path, self.path[1:]):
            self.cum.append(self.cum[-1] + math.dist(a, b))

    def at(self, t):
        d = self.speed * (t - self.t_start)
        total = self.cum[-1]
        moving = 0.0 < d < total
        d = min(max(d, 0.0), total)
        for i in range(len(self.path) - 1):
            if d <= self.cum[i + 1] or i == len(self.path) - 2:
                seg = self.cum[i + 1] - self.cum[i]
                u = 0.0 if seg == 0 else (d - self.cum[i]) / seg
                a, b = self.path[i], self.path[i + 1]
                x, y = a[0] + u * (b[0] - a[0]), a[1] + u * (b[1] - a[1])
                vx = vy = 0.0
                if moving and seg > 0:
                    vx, vy = self.speed * (b[0] - a[0]) / seg, self.speed * (b[1] - a[1]) / seg
                return x, y, vx, vy
        raise AssertionError


class World:
    def __init__(self, scn: Scenario, seed: int, telemetry: TelemetryWriter | None = None):
        self.scn, self.seed, self.dt = scn, seed, scn.dt
        self.p, self.fr = scn.vparams, scn.friction
        self.n = 0
        self.finished = False
        self.tw = telemetry or TelemetryWriter(keep=False)
        self.n_act = round(self.p.t_act / self.dt)
        self.n_steer = round(self.p.t_steer / self.dt)
        self.veh = {v.id: initial_state(v.x, v.y, v.psi, v.v, v.delta, self.p, self.fr) for v in scn.vehicles}
        self.init_delta = {v.id: v.delta for v in scn.vehicles}
        self.cmds = {v.id: [(round(c.t / self.dt), c) for c in v.script] for v in scn.vehicles}   # (issue_step, cmd), sorted
        self.peds = [Pedestrian(s, seed) for s in scn.pedestrians]
        self.obst = scn.obstacles
        self.events_log: list[dict] = []
        self.counts = {"friction_limited_steps": 0, "outside_model_validity_steps": 0, "outside_odd_steps": 0}
        self.min_clearance = math.inf
        self._last_cmd = {v.id: (0.0, self.init_delta[v.id], "comfort") for v in scn.vehicles}
        self._last_info = {v.id: False for v in scn.vehicles}
        self._ped_prev = {p.id: p.at(0.0)[:2] for p in self.peds}

    # ------------------------------------------------------------------ public API
    @property
    def t(self) -> float:
        return self.n * self.dt

    def issue(self, vid: str, cmd: ScriptedCmd):
        """Schedule a control command at the CURRENT step (used by closed-loop controllers in later WPs)."""
        self.cmds[vid].append((self.n, cmd))
        self.cmds[vid].sort(key=lambda z: z[0])

    def header(self) -> dict:
        from dataclasses import asdict
        return {"type": "header", "schema_version": "0.1.0", "scenario_id": self.scn.id, "seed": self.seed, "dt": self.dt,
                "backend": {"name": BACKEND_NAME, "version": BACKEND_VERSION, "limitations": list(LIMITATIONS)},
                "params": {"vehicle": asdict(self.p), "mu": self.fr.mu, "g": self.fr.g}}

    def run(self, on_step=None):
        self.tw.write(self.header())
        self._record([])
        total = round(self.scn.duration / self.dt)
        while self.n < total and not self.finished:
            self.step()
            if on_step is not None:
                on_step(self)                       # observers must not change state; tested by PHY-01
        return self.summary()

    # ------------------------------------------------------------------ internals
    def _effective(self, vid):
        a_cmd, d_cmd, mode = 0.0, self.init_delta[vid], "comfort"
        for issue, c in self.cmds[vid]:
            if issue + self.n_act <= self.n:
                a_cmd, mode = c.a_cmd, c.mode
            if issue + self.n_steer <= self.n:
                d_cmd = c.delta_cmd
        return a_cmd, d_cmd, mode

    def _obb(self, st):
        c = math.cos(st.psi); s = math.sin(st.psi); off = self.p.obb_offset
        return (st.x + off * c, st.y + off * s, st.psi, self.p.length / 2.0, self.p.width / 2.0)

    def step(self):
        events = []
        info_all = {}
        for vid, st in self.veh.items():
            a_cmd, d_cmd, mode = self._effective(vid)
            self._last_cmd[vid] = (a_cmd, d_cmd, mode)
            new, info = step_vehicle(st, a_cmd, d_cmd, mode, self.p, self.fr, self.dt)
            self.veh[vid] = new
            info_all[vid] = info
            self._last_info[vid] = info.friction_limited
            if info.friction_limited: self.counts["friction_limited_steps"] += 1
            if info.ay > self.p.ay_validity_fraction * self.fr.mug:
                self.counts["outside_model_validity_steps"] += 1
                events.append({"type": "outside_model_validity", "actor": vid, "ay": info.ay})
            if new.v > self.p.v_max_odd + 1e-9:
                self.counts["outside_odd_steps"] += 1
                events.append({"type": "outside_odd", "actor": vid, "v": new.v})
        self.n += 1
        t = self.t
        # pedestrians + contacts
        ped_now = {p.id: p.at(t) for p in self.peds}
        for vid, st in self.veh.items():
            obb = self._obb(st)
            for p in self.peds:
                x0y0 = self._ped_prev[p.id]
                x1, y1 = ped_now[p.id][:2]
                self.min_clearance = min(self.min_clearance, max(dist_segment_obb(obb, x0y0, (x1, y1)) - p.radius, 0.0))
                if capsule_hits_obb(obb, x0y0, (x1, y1), p.radius):
                    cp = closest_point_obb(obb, x1, y1)
                    vx, vy = st.v * math.cos(st.psi), st.v * math.sin(st.psi)
                    events.append({"type": "collision", "actors": [vid, p.id], "impact_speed": math.hypot(vx - ped_now[p.id][2], vy - ped_now[p.id][3]),
                                   "point": [cp[0], cp[1]], "t": t})
            for o in self.obst:
                ob = (o.cx, o.cy, o.yaw, o.length / 2.0, o.width / 2.0)
                if sat_obb_obb(obb, ob):
                    events.append({"type": "collision", "actors": [vid, o.id], "impact_speed": st.v, "point": [obb[0], obb[1]], "t": t})
        ids = list(self.veh)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                if sat_obb_obb(self._obb(self.veh[ids[i]]), self._obb(self.veh[ids[j]])):
                    events.append({"type": "collision", "actors": [ids[i], ids[j]], "impact_speed": abs(self.veh[ids[i]].v - self.veh[ids[j]].v), "point": [0.0, 0.0], "t": t})
        self._ped_prev = {k: v[:2] for k, v in ped_now.items()}
        self._ped_now = ped_now
        if any(e["type"] == "collision" for e in events) and self.scn.stop_on_collision:
            self.finished = True
        if self.scn.stop_when_all_stopped and all(s.v == 0.0 and s.a == 0.0 for s in self.veh.values()) and t > 0:
            self.finished = True
        self.events_log.extend(events)
        if self.n % self.scn.telemetry_every == 0 or self.finished:
            self._record(events)

    def _record(self, events):
        t = self.t
        ped = {p.id: p.at(t) for p in self.peds}
        self.tw.write({
            "type": "frame", "step": self.n, "t": t,
            "vehicles": [{"id": vid, "x": s.x, "y": s.y, "psi": s.psi, "v": s.v, "a": s.a, "delta": s.delta, "delta_eff": s.delta_eff,
                          "wheel_rot": s.wheel_rot, "friction_limited": self._last_info[vid],
                          "cmd": {"a_cmd": self._last_cmd[vid][0], "delta_cmd": self._last_cmd[vid][1], "mode": self._last_cmd[vid][2]}}
                         for vid, s in self.veh.items()],
            "pedestrians": [{"id": p.id, "x": ped[p.id][0], "y": ped[p.id][1], "vx": ped[p.id][2], "vy": ped[p.id][3]} for p in self.peds],
            "events": events})

    def summary(self) -> dict:
        cols = [e for e in self.events_log if e["type"] == "collision"]
        out = {"steps": self.n, "t_end": self.t, "collision": bool(cols),
               "impact_speed": cols[0]["impact_speed"] if cols else None,
               "min_clearance": None if math.isinf(self.min_clearance) else self.min_clearance,
               "vehicles": {vid: {"x": s.x, "y": s.y, "v": s.v, "a": s.a} for vid, s in self.veh.items()},
               "counts": dict(self.counts), "telemetry_lines": self.tw.count}
        return out
