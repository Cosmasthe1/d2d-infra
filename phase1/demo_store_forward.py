"""How long does an IoT message wait for a satellite? Store-and-forward latency vs constellation size (Nairobi, 24 h)."""
import numpy as np
from ntn_sim.orbit import walker_delta
from ntn_sim.schedule import pass_windows

LAT, LON = -1.2921, 36.8219
rng = np.random.default_rng(7)
rows = []
for name, n, planes in [("6 sats", 6, 3), ("12 sats", 12, 3), ("24 sats", 24, 6), ("48 sats", 48, 8), ("120 sats", 120, 12)]:
    con = walker_delta(n, planes, 53, 550)
    # 3 days of windows so late-day messages can still be delivered
    w = pass_windows(con, LAT, LON, duration_s=3 * 86400, min_el_deg=20, step_s=10)
    starts = np.array([p.start_s for p in w]); ends = np.array([p.end_s for p in w])
    msgs = rng.uniform(0, 86400, 2000)          # random message creation times in day 1
    lat = []
    for t in msgs:
        inwin = (starts <= t) & (ends > t)
        if inwin.any():
            lat.append(0.0)
        else:
            nxt = starts[starts > t]
            lat.append(float(nxt[0] - t) if len(nxt) else np.nan)
    lat = np.array(lat) / 60
    rows.append((name, np.nanmedian(lat), np.nanpercentile(lat, 95), np.nanmax(lat)))
print(f"{'constellation':14s} {'median min':>10s} {'p95 min':>9s} {'max min':>9s}")
for r in rows:
    print(f"{r[0]:14s} {r[1]:10.1f} {r[2]:9.1f} {r[3]:9.1f}")
