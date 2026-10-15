"""Phase 2: cubesat NB-NTN payload demo - orbit contact analysis, link closure and spec generation."""
import json, os
import numpy as np
from ntn_sim.orbit import walker_delta, RE
from ntn_sim.schedule import pass_windows
from ntn_sim.link import Device, Payload, SERVICES, budget, beam_footprint_km

F = 2.0e9
SITES = {"Nairobi": (-1.2921, 36.8219), "Turkana (Lodwar)": (3.12, 35.60), "Mombasa": (-4.0435, 39.6682)}
ORBITS = {"550 km / 97.6 deg SSO-like": (97.6, 550), "550 km / 53 deg": (53, 550), "500 km / 6 deg equatorial-ish": (6, 500)}
APERTURES = [0.25, 0.5, 1.0, 2.0]       # deployable mesh / patch array options, m^2
MSG_AIRTIME_S = 1.5                     # assumed UL airtime for a 50-byte message incl. repetitions (planning)
SCHED_EFF = 0.6                         # fraction of contact time usable after acquisition/handshake
MSGS_PER_DEVICE_DAY = 4
PAYLOAD_POWER_W, GEN_WH_DAY = 35.0, 300.0   # assumptions for a 6U with deployable panels
OUT = os.path.join(os.path.dirname(__file__), "out"); os.makedirs(OUT, exist_ok=True)

from ntn_sim.orbit import Constellation
contact = []
for oname, (inc, alt) in ORBITS.items():
    for sname, (la, lo) in SITES.items():
        per_raan = []
        for raan in range(0, 360, 30):          # a single sat's contact depends on plane alignment at launch
            con = Constellation(a=RE + alt * 1e3, inc=np.radians(inc), raan=np.array([np.radians(raan)]), u0=np.array([0.0]))
            w = [p for p in pass_windows(con, la, lo, duration_s=2 * 86400, min_el_deg=20, step_s=10) if p.start_s < 86400]
            per_raan.append((len(w), sum(min(p.end_s, 86400) - p.start_s for p in w) / 60, max((p.max_el_deg for p in w), default=0)))
        arr = np.array(per_raan)
        mean_min, lo_min, hi_min = arr[:, 1].mean(), arr[:, 1].min(), arr[:, 1].max()
        msgs_beam = mean_min * 60 * SCHED_EFF / MSG_AIRTIME_S
        contact.append(dict(orbit=oname, site=sname, passes_per_day=round(float(arr[:, 0].mean()), 1),
                            contact_min_per_day=round(float(mean_min), 1),
                            contact_range=f"{lo_min:.0f}-{hi_min:.0f}", best_max_el=round(float(arr[:, 2].max()), 1),
                            msgs_per_day_per_beam=int(msgs_beam), devices_supported=int(msgs_beam / MSGS_PER_DEVICE_DAY),
                            payload_energy_wh=round(PAYLOAD_POWER_W * mean_min / 60, 1)))

closure = []
dev = Device()
a = RE + 550e3
for el_deg in (20, 30, 45):
    el = np.radians(el_deg)
    rng = np.sqrt(a**2 - (RE * np.cos(el))**2) - RE * np.sin(el)
    for ap in APERTURES:
        pay = Payload("cubesat", ap, ptx_per_beam_w=5)
        for key in ("nbiot_sms", "ltem_data"):
            b = budget(np.array(el), np.array(rng), a, F, dev, pay, SERVICES[key])
            closure.append(dict(el=el_deg, aperture_m2=ap, service=SERVICES[key].name, slant_km=round(rng / 1e3),
                                margin_ul=round(float(b["margin_ul"]), 1), margin_dl=round(float(b["margin_dl"]), 1),
                                footprint_km=round(float(beam_footprint_km(ap, F, rng)))))
json.dump(dict(contact=contact, closure=closure), open(f"{OUT}/mission.json", "w"), indent=1)

# ---- generate PAYLOAD_SPEC.md from computed numbers ----
sel = [c for c in closure if c["service"].startswith("NB-IoT") and c["el"] == 20]
ok = [c for c in sel if min(c["margin_ul"], c["margin_dl"]) >= 3]
min_ap = min((c["aperture_m2"] for c in ok), default=None)
md = ["# Phase 2 - 6U NB-NTN payload demo: derived requirements", "",
      "Orbit-plane alignment (RAAN) is swept because one satellite's contact with a fixed site varies widely with it; the launch slot matters. All numbers are produced by `mission_design.py` from the Phase 0 simulator (planning-grade; see caveats).", "",
      "## Mission objective",
      "Demonstrate closing a link between **unmodified 3GPP NB-IoT modules (23 dBm, ~0 dBi)** and a LEO payload, "
      "and register / exchange store-and-forward messages with the Phase 1 platform, from sites in Kenya.", "",
      "## Contact opportunity (single satellite, >=20 deg elevation, averaged over 12 plane alignments)", "",
      "| Orbit | Site | Passes/day (avg) | Contact min/day avg | Range over alignments | Msgs/day/beam | Devices @4 msg/day | Payload Wh/day |",
      "|---|---|---|---|---|---|---|---|"]
for c in contact:
    md.append(f"| {c['orbit']} | {c['site']} | {c['passes_per_day']} | {c['contact_min_per_day']} | {c['contact_range']} | "
              f"{c['msgs_per_day_per_beam']} | {c['devices_supported']} | {c['payload_energy_wh']} |")
md += ["", f"Energy check: payload energy/day must stay below roughly {GEN_WH_DAY:.0f} Wh generation minus bus load (assumed 6U with deployable panels).", "",
       "## Link closure, NB-IoT-style narrowband service, 550 km orbit, outdoor handset", "",
       "| Elevation | Aperture m2 | Slant km | UL margin dB | DL margin dB | Beam footprint km |", "|---|---|---|---|---|---|"]
for c in sel + [x for x in closure if x["service"].startswith("NB-IoT") and x["el"] == 30]:
    md.append(f"| {c['el']} | {c['aperture_m2']} | {c['slant_km']} | {c['margin_ul']} | {c['margin_dl']} | {c['footprint_km']} |")
md += ["", f"**Smallest aperture tested that gives >=3 dB margin on both links at 20 deg elevation: "
       f"{min_ap if min_ap else 'none of the tested sizes'} m2.**", "",
       "## Payload requirements (derived)",
       "- Band: S-band (~2 GHz) 3GPP NB-IoT NTN band, **spectrum/licence subject to ITU and CA Kenya approval (experimental licence first)**.",
       "- Antenna: deployable array/mesh sized from the table above; plan for pointing and scan loss to 60 deg off-nadir.",
       "- Regenerative eNodeB-lite: timing advance and Doppler pre-compensation computed on board from ephemeris (+-~45 kHz at 2 GHz, up to ~270 Hz/s).",
       "- Timers: RTT up to ~12 ms service link at 550 km, plus feeder link; Koffset sized accordingly.",
       "- Store-and-forward buffer on orbit; downlink to the Phase 0/1 gateway over a separate feeder link (UHF/S/X TBD).", "",
       "## Field test plan (Kenya)",
       "1. Phase 2a - **Emulated**: run the Phase 0 channel proxy / netem replay against a COTS NB-IoT module and SDR-based eNodeB.",
       "2. Phase 2b - **Balloon/drone-hosted payload** at 20-30 km to validate the RF chain without launch cost.",
       "3. Phase 2c - **Orbital**: rideshare launch; beacon + 2 test sites (Nairobi, Lodwar) with outdoor devices.", "",
       "## Caveats",
       "- Spherical Earth, circular two-body orbits; use SGP4/real TLEs for operations.",
       "- No interference, multi-device contention, or ionospheric effects modeled; required-SNR values are planning heuristics, not 3GPP conformance results.",
       "- Airtime-per-message, scheduling efficiency, and power numbers are assumptions at the top of `mission_design.py`; replace after emulation (2a)."]
open(f"{OUT}/PAYLOAD_SPEC.md", "w").write("\n".join(md))
print("\n".join(md[:30]))
