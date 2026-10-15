# Phase 2 - 6U NB-NTN payload demo: derived requirements

Orbit-plane alignment (RAAN) is swept because one satellite's contact with a fixed site varies widely with it; the launch slot matters. All numbers are produced by `mission_design.py` from the Phase 0 simulator (planning-grade; see caveats).

## Mission objective
Demonstrate closing a link between **unmodified 3GPP NB-IoT modules (23 dBm, ~0 dBi)** and a LEO payload, and register / exchange store-and-forward messages with the Phase 1 platform, from sites in Kenya.

## Contact opportunity (single satellite, >=20 deg elevation, averaged over 12 plane alignments)

| Orbit | Site | Passes/day (avg) | Contact min/day avg | Range over alignments | Msgs/day/beam | Devices @4 msg/day | Payload Wh/day |
|---|---|---|---|---|---|---|---|
| 550 km / 97.6 deg SSO-like | Nairobi | 1.6 | 7.1 | 0-11 | 169 | 42 | 4.1 |
| 550 km / 97.6 deg SSO-like | Turkana (Lodwar) | 1.7 | 7.2 | 0-12 | 171 | 42 | 4.2 |
| 550 km / 97.6 deg SSO-like | Mombasa | 1.9 | 7.4 | 3-10 | 178 | 44 | 4.3 |
| 550 km / 53 deg | Nairobi | 2.2 | 9.1 | 4-13 | 217 | 54 | 5.3 |
| 550 km / 53 deg | Turkana (Lodwar) | 2.1 | 9.5 | 6-14 | 226 | 56 | 5.5 |
| 550 km / 53 deg | Mombasa | 2.2 | 8.7 | 6-11 | 209 | 52 | 5.1 |
| 500 km / 6 deg equatorial-ish | Nairobi | 14.2 | 65.6 | 64-69 | 1573 | 393 | 38.2 |
| 500 km / 6 deg equatorial-ish | Turkana (Lodwar) | 14.2 | 59.5 | 58-63 | 1428 | 357 | 34.7 |
| 500 km / 6 deg equatorial-ish | Mombasa | 12.0 | 52.5 | 51-56 | 1260 | 315 | 30.6 |

Energy check: payload energy/day must stay below roughly 300 Wh generation minus bus load (assumed 6U with deployable panels).

## Link closure, NB-IoT-style narrowband service, 550 km orbit, outdoor handset

| Elevation | Aperture m2 | Slant km | UL margin dB | DL margin dB | Beam footprint km |
|---|---|---|---|---|---|
| 20 | 0.25 | 1294 | 5.9 | 2.5 | 420 |
| 20 | 0.5 | 1294 | 8.9 | 5.5 | 297 |
| 20 | 1.0 | 1294 | 11.9 | 8.5 | 210 |
| 20 | 2.0 | 1294 | 14.9 | 11.5 | 148 |
| 30 | 0.25 | 993 | 9.0 | 5.6 | 322 |
| 30 | 0.5 | 993 | 12.0 | 8.6 | 228 |
| 30 | 1.0 | 993 | 15.0 | 11.6 | 161 |
| 30 | 2.0 | 993 | 18.0 | 14.6 | 114 |

**Smallest aperture tested that gives >=3 dB margin on both links at 20 deg elevation: 0.5 m2.**

## Payload requirements (derived)
- Band: S-band (~2 GHz) 3GPP NB-IoT NTN band, **spectrum/licence subject to ITU and CA Kenya approval (experimental licence first)**.
- Antenna: deployable array/mesh sized from the table above; plan for pointing and scan loss to 60 deg off-nadir.
- Regenerative eNodeB-lite: timing advance and Doppler pre-compensation computed on board from ephemeris (+-~45 kHz at 2 GHz, up to ~270 Hz/s).
- Timers: RTT up to ~12 ms service link at 550 km, plus feeder link; Koffset sized accordingly.
- Store-and-forward buffer on orbit; downlink to the Phase 0/1 gateway over a separate feeder link (UHF/S/X TBD).

## Field test plan (Kenya)
1. Phase 2a - **Emulated**: run the Phase 0 channel proxy / netem replay against a COTS NB-IoT module and SDR-based eNodeB.
2. Phase 2b - **Balloon/drone-hosted payload** at 20-30 km to validate the RF chain without launch cost.
3. Phase 2c - **Orbital**: rideshare launch; beacon + 2 test sites (Nairobi, Lodwar) with outdoor devices.

## Caveats
- Spherical Earth, circular two-body orbits; use SGP4/real TLEs for operations.
- No interference, multi-device contention, or ionospheric effects modeled; required-SNR values are planning heuristics, not 3GPP conformance results.
- Airtime-per-message, scheduling efficiency, and power numbers are assumptions at the top of `mission_design.py`; replace after emulation (2a).