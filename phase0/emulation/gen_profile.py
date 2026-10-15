"""Build a satellite-pass impairment profile for the radio link (UE <-> gNB) from the Phase 0 simulator.

One profile row per simulated second:  t, in_pass, one_way_delay_ms, loss_pct, el_deg, margin_db, doppler_hz
- Before/after the pass the link is DOWN (100% loss) so the UE sees real coverage loss and re-acquisition.
- Delay is one-way service-link delay (+ optional feeder-link delay for a bent-pipe path to a ground gNB).
- Doppler is recorded for analysis only; netem cannot emulate it (the RAN under test must pre-compensate).
"""
import argparse, json, sys
from ntn_sim.orbit import walker_delta
from ntn_sim.schedule import pass_windows, link_state
from ntn_sim.link import Payload, SERVICES


def build(lat, lon, sats=24, planes=6, min_el=20.0, lead_s=60, tail_s=60, feeder_ms=0.0, pick="best", aperture_m2=2.0, service="nbiot_sms"):
    con = walker_delta(sats, planes, 53, 550)
    kw = dict(pay=Payload(aperture_m2=aperture_m2), svc=SERVICES[service], min_el_deg=min_el)
    w = pass_windows(con, lat, lon, duration_s=6 * 3600, min_el_deg=min_el, step_s=5)
    if not w:
        raise SystemExit("no pass found in 6 h window")
    p = max(w, key=lambda x: x.max_el_deg) if pick == "best" else w[0]
    rows, t = [], p.start_s - lead_s
    while t < p.end_s + tail_s:
        s = link_state(con, lat, lon, t, **kw)
        if s is None:
            rows.append(dict(t=round(t - (p.start_s - lead_s)), in_pass=False, delay_ms=0.0, loss_pct=100.0,
                             el_deg=None, margin_db=None, doppler_hz=None))
        else:
            rows.append(dict(t=round(t - (p.start_s - lead_s)), in_pass=True, delay_ms=round(s["delay_ms"] + feeder_ms, 2),
                             loss_pct=round(100 * s["loss_prob"], 2), el_deg=round(s["el_deg"], 1),
                             margin_db=round(s["margin_db"], 1), doppler_hz=round(s["doppler_hz"])))
        t += 1
    return dict(pass_start_s=p.start_s, pass_end_s=p.end_s, max_el_deg=p.max_el_deg, lead_s=lead_s, rows=rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, default=-1.2921); ap.add_argument("--lon", type=float, default=36.8219)
    ap.add_argument("--sats", type=int, default=24); ap.add_argument("--min-el", type=float, default=20.0)
    ap.add_argument("--lead", type=int, default=60); ap.add_argument("--tail", type=int, default=60)
    ap.add_argument("--feeder-ms", type=float, default=0.0)
    ap.add_argument("--aperture", type=float, default=2.0, help="payload aperture m^2 (smaller = marginal link, more loss)")
    ap.add_argument("--service", default="nbiot_sms", choices=list(SERVICES))
    ap.add_argument("--out", default="-")
    a = ap.parse_args()
    prof = build(a.lat, a.lon, a.sats, 6 if a.sats % 6 == 0 else 1, a.min_el, a.lead, a.tail, a.feeder_ms, aperture_m2=a.aperture, service=a.service)
    f = sys.stdout if a.out == "-" else open(a.out, "w")
    json.dump(prof, f, indent=1)
