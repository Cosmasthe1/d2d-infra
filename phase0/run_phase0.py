"""Phase 0 driver: Kenya coverage, pass analysis (Nairobi), link margins. Writes ./out/."""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from ntn_sim.orbit import walker_delta, propagate_ecef, ground_ecef, look_angles, doppler_hz, one_way_delay_ms, RE
from ntn_sim.link import Device, Payload, SERVICES, budget, beam_footprint_km, min_aperture_for_margin
from ntn_sim.coverage import grid, visibility_series, gap_stats

F = 2.0e9
OUT = os.path.join(os.path.dirname(__file__), "out")
os.makedirs(OUT, exist_ok=True)
NAIROBI = (-1.2921, 36.8219)
res = {}

# ---- 1. Coverage vs constellation size (Kenya grid, 25 deg min elevation, 24 h) ----
scen = [("6 sats / 53deg", 6, 3, 53), ("12 sats / 53deg", 12, 3, 53),
        ("24 sats / 53deg", 24, 6, 53), ("24 sats / 97.6deg SSO-like", 24, 6, 97.6),
        ("48 sats / 53deg", 48, 8, 53), ("120 sats / 53deg", 120, 12, 53)]
lats, lons, LA, LO = grid(step_deg=1.0)
cov = []
fig, axs = plt.subplots(2, 3, figsize=(13, 7))
for ax, (name, N, P, inc) in zip(axs.ravel(), scen):
    con = walker_delta(N, P, inc, 550)
    ts, vis = visibility_series(con, LA, LO, min_el_deg=25, step_s=30)
    frac, mg, xg = gap_stats(vis, 30)
    cov.append(dict(name=name, sats=N, mean_cov_pct=float(100 * frac.mean()),
                    mean_gap_min=float(mg.mean() / 60), worst_gap_min=float(xg.max() / 60)))
    im = ax.pcolormesh(lons, lats, 100 * frac.reshape(len(lats), len(lons)), vmin=0, vmax=100, shading="auto")
    ax.set_title(f"{name}\navg {100*frac.mean():.0f}% time covered", fontsize=9)
    ax.set_xlabel("lon"); ax.set_ylabel("lat")
fig.colorbar(im, ax=axs.ravel().tolist(), label="% of day with >=1 sat above 25 deg")
fig.savefig(f"{OUT}/kenya_coverage.png", dpi=110, bbox_inches="tight"); plt.close(fig)
res["coverage"] = cov

# ---- 2. Single-pass analysis over Nairobi (550 km, 53deg single sat, best pass of the day) ----
con1 = walker_delta(1, 1, 53, 550)
gs = ground_ecef(*NAIROBI)
ts = np.arange(0, 86400, 1.0)
pos, vel = propagate_ecef(con1, ts)
el, rng, rr = look_angles(pos, vel, gs)
el, rng, rr = el[:, 0, 0], rng[:, 0, 0], rr[:, 0, 0]
up = el > np.radians(10)
idx = np.flatnonzero(up)
splits = np.flatnonzero(np.diff(idx) > 1) + 1
passes = np.split(idx, splits)
best = max(passes, key=lambda p: el[p].max())
dop = doppler_hz(rr, F)
d_rate = np.gradient(dop, ts)
b = best
res["pass_nairobi"] = dict(
    n_passes_above_10deg_per_day_single_sat=len(passes),
    best_pass_duration_s=int(len(b)), best_pass_max_el_deg=float(np.degrees(el[b].max())),
    max_doppler_khz=float(np.abs(dop[b]).max() / 1e3),
    max_doppler_rate_hz_per_s=float(np.abs(d_rate[b]).max()),
    one_way_delay_ms_min=float(one_way_delay_ms(rng[b]).min()),
    one_way_delay_ms_max=float(one_way_delay_ms(rng[b]).max()),
    rtt_ms_max=float(2 * one_way_delay_ms(rng[b]).max()),
    # 3GPP-style rule of thumb: UE needs Koffset >= worst RTT (service link + feeder)
)
tt = ts[b] - ts[b][0]
fig, axs = plt.subplots(1, 3, figsize=(14, 3.6))
axs[0].plot(tt, np.degrees(el[b])); axs[0].set_title("Elevation (deg)")
axs[1].plot(tt, dop[b] / 1e3); axs[1].set_title("Doppler @2 GHz (kHz)")
axs[2].plot(tt, one_way_delay_ms(rng[b])); axs[2].set_title("One-way delay (ms)")
for a_ in axs: a_.set_xlabel("seconds into pass"); a_.grid(alpha=.3)
fig.savefig(f"{OUT}/pass_nairobi.png", dpi=110, bbox_inches="tight"); plt.close(fig)

# ---- 3. Link margin vs elevation for several payload sizes and services ----
a = con1.a
els = np.radians(np.linspace(10, 90, 81))
# slant range vs elevation for circular orbit
h = a - RE
slant = np.sqrt((a ** 2) - (RE * np.cos(els)) ** 2) - RE * np.sin(els)
dev = Device()
pays = [Payload("cubesat 0.5 m2", 0.5, ptx_per_beam_w=5), Payload("smallsat 2 m2", 2, ptx_per_beam_w=10),
        Payload("large 25 m2", 25, ptx_per_beam_w=20), Payload("very large 200 m2", 200, ptx_per_beam_w=30)]
fig, axs = plt.subplots(1, 4, figsize=(17, 3.8), sharey=True)
table = []
for ax, (key, svc) in zip(axs, SERVICES.items()):
    for p in pays:
        bgt = budget(els, slant, a, F, dev, p, svc)
        m = np.minimum(bgt["margin_ul"], bgt["margin_dl"])
        ax.plot(np.degrees(els), np.where(np.isfinite(m), m, np.nan), label=p.name)
        e30 = int(np.argmin(np.abs(np.degrees(els) - 30)))
        table.append(dict(service=svc.name, payload=p.name, margin_at_30deg_db=float(m[e30]),
                          ul_snr=float(bgt["snr_ul"][e30]), dl_snr=float(bgt["snr_dl"][e30]),
                          footprint_km_nadir=float(beam_footprint_km(p.aperture_m2, F, h))))
    ax.axhline(0, color="k", lw=.8); ax.set_title(svc.name, fontsize=9); ax.set_xlabel("elevation (deg)"); ax.grid(alpha=.3)
axs[0].set_ylabel("worst-link margin (dB), outdoor handset"); axs[0].legend(fontsize=7)
fig.savefig(f"{OUT}/link_margin.png", dpi=110, bbox_inches="tight"); plt.close(fig)
res["link_margin_30deg"] = table

# ---- 4. Required aperture to close each service (3 dB margin) at 30 deg for env losses ----
e30 = np.radians(30); r30 = float(np.sqrt(a**2 - (RE*np.cos(e30))**2) - RE*np.sin(e30))
req = []
for env_name, env_loss in [("outdoor", 0), ("vehicle", 8), ("indoor", 20)]:
    d = Device(env_loss_db=env_loss)
    for key, svc in SERVICES.items():
        ap = min_aperture_for_margin(e30, r30, a, F, d, Payload(ptx_per_beam_w=10), svc, 3.0)
        req.append(dict(environment=env_name, service=svc.name, min_aperture_m2=float(ap)))
res["required_aperture_30deg_3dB"] = req

json.dump(res, open(f"{OUT}/results.json", "w"), indent=2)
print(json.dumps(res["coverage"], indent=1)); print(json.dumps(res["pass_nairobi"], indent=1))
for r in req: print(f"{r['environment']:8s} {r['service']:28s} {r['min_aperture_m2']:9.2f} m2")
