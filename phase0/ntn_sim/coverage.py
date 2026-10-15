"""Coverage / revisit analysis over a lat/lon grid."""
from __future__ import annotations
import numpy as np
from .orbit import propagate_ecef, ground_ecef, look_angles

KENYA_BBOX = dict(lat=(-4.7, 5.0), lon=(33.9, 41.9))


def grid(bbox=KENYA_BBOX, step_deg=1.0):
    lats = np.arange(bbox["lat"][0], bbox["lat"][1] + 1e-9, step_deg)
    lons = np.arange(bbox["lon"][0], bbox["lon"][1] + 1e-9, step_deg)
    LA, LO = np.meshgrid(lats, lons, indexing="ij")
    return lats, lons, LA.ravel(), LO.ravel()


def visibility_series(con, lat, lon, min_el_deg=25.0, duration_s=86400, step_s=30, chunk=240):
    """Boolean array (T, G): at least one satellite above min elevation."""
    gs = ground_ecef(lat, lon)
    ts = np.arange(0, duration_s, step_s)
    out = []
    for i in range(0, len(ts), chunk):
        pos, vel = propagate_ecef(con, ts[i:i + chunk])
        el, _, _ = look_angles(pos, vel, gs)
        out.append((el >= np.radians(min_el_deg)).any(axis=1))
    return ts, np.concatenate(out, axis=0)


def gap_stats(vis, step_s):
    """Per-point coverage fraction, mean and max outage gap (s)."""
    T, G = vis.shape
    frac = vis.mean(axis=0)
    mean_gap = np.zeros(G)
    max_gap = np.zeros(G)
    for g in range(G):
        v = vis[:, g]
        gaps, run = [], 0
        for x in v:
            if not x:
                run += 1
            elif run:
                gaps.append(run); run = 0
        if run:
            gaps.append(run)
        if gaps:
            mean_gap[g] = np.mean(gaps) * step_s
            max_gap[g] = np.max(gaps) * step_s
    return frac, mean_gap, max_gap
