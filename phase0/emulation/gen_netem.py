"""Emit a bash script that replays a satellite pass on a Linux interface using tc netem.

Use with the Open5GS/UERANSIM testbed (docker-compose.yml): apply to the veth/bridge between the UE/gNB
container and the core so the RAN<->core path experiences realistic delay and loss.

  python emulation/gen_netem.py --dev br-ntn --lat -1.29 --lon 36.82 > replay_pass.sh
"""
import argparse
from ntn_sim.orbit import walker_delta
from ntn_sim.schedule import pass_windows, link_state

ap = argparse.ArgumentParser()
ap.add_argument("--dev", default="br-ntn"); ap.add_argument("--lat", type=float, default=-1.2921)
ap.add_argument("--lon", type=float, default=36.8219); ap.add_argument("--sats", type=int, default=24)
ap.add_argument("--min-el", type=float, default=20.0)
a = ap.parse_args()
con = walker_delta(a.sats, 6, 53, 550)
w = pass_windows(con, a.lat, a.lon, duration_s=6 * 3600, min_el_deg=a.min_el)
if not w:
    raise SystemExit("no pass in window")
p = max(w, key=lambda x: x.max_el_deg)
print("#!/usr/bin/env bash\nset -e\nDEV=%s\ntc qdisc replace dev $DEV root netem delay 5ms" % a.dev)
t = p.start_s
while t < p.end_s:
    s = link_state(con, a.lat, a.lon, t, min_el_deg=a.min_el)
    if s:
        print(f"tc qdisc change dev $DEV root netem delay {s['delay_ms']:.1f}ms 0.5ms loss {100*s['loss_prob']:.2f}%  # el={s['el_deg']:.0f} margin={s['margin_db']:.1f}dB")
        print("sleep 1")
    t += 1
print("tc qdisc del dev $DEV root || true")
