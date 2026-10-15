"""Pass windows and instantaneous link state for a ground site. Used by Phase 0 emulation and Phase 1 platform."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from .orbit import Constellation, propagate_ecef, ground_ecef, look_angles, doppler_hz, one_way_delay_ms, RE
from .link import Device, Payload, Service, SERVICES, budget

F_DEFAULT = 2.0e9


@dataclass
class Pass:
    start_s: float
    end_s: float
    max_el_deg: float

    @property
    def duration_s(self):
        return self.end_s - self.start_s


def pass_windows(con: Constellation, lat: float, lon: float, t0: float = 0.0, duration_s: float = 86400,
                 min_el_deg: float = 20.0, step_s: float = 5.0):
    """Windows where >=1 satellite is above min_el_deg (union over constellation)."""
    gs = ground_ecef(lat, lon)
    ts = np.arange(t0, t0 + duration_s, step_s)
    pos, vel = propagate_ecef(con, ts)
    el, _, _ = look_angles(pos, vel, gs)
    best = np.degrees(el[:, :, 0].max(axis=1))
    up = best >= min_el_deg
    out, start = [], None
    for i, u in enumerate(up):
        if u and start is None:
            start = i
        if (not u or i == len(up) - 1) and start is not None:
            end = i if not u else i + 1
            out.append(Pass(float(ts[start]), float(ts[min(end, len(ts) - 1)]), float(best[start:end].max())))
            start = None
    return out


def link_state(con: Constellation, lat: float, lon: float, t: float, f_hz=F_DEFAULT,
               dev: Device = Device(), pay: Payload = Payload(), svc: Service = SERVICES["nbiot_sms"],
               min_el_deg: float = 20.0):
    """State of the best-elevation satellite at time t, or None if nothing is in view."""
    gs = ground_ecef(lat, lon)
    pos, vel = propagate_ecef(con, np.array([t]))
    el, rng, rr = look_angles(pos, vel, gs)
    el, rng, rr = el[0, :, 0], rng[0, :, 0], rr[0, :, 0]
    k = int(np.argmax(el))
    if np.degrees(el[k]) < min_el_deg:
        return None
    b = budget(el[k], rng[k], con.a, f_hz, dev, pay, svc)
    margin = float(min(b["margin_ul"], b["margin_dl"]))
    return dict(sat=k, el_deg=float(np.degrees(el[k])), delay_ms=float(one_way_delay_ms(rng[k])),
                doppler_hz=float(doppler_hz(rr[k], f_hz)), margin_db=margin,
                loss_prob=float(1 / (1 + np.exp(1.5 * (margin + 1.0)))))  # logistic PER vs margin (planning heuristic)
