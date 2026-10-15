# Phase 2a testbed: real 5G core + RAN emulation under a satellite-pass profile

**What it is:** Open5GS (5G SA core) + UERANSIM (gNB + UE) from `herlesupreeth/docker_open5gs`, with the Phase 0 simulator
shaping the UE<->gNB radio link (UERANSIM carries that link as UDP between the `nr_ue` and `nr_gnb` containers) using `tc netem`.

**What it tests:** whether a real core, session setup and traffic survive pass-shaped outages, delay and loss, and how long
recovery takes after each pass.
**What it cannot test:** Doppler, timing advance/Koffset, HARQ round-trip, PHY performance. UERANSIM has no PHY, and netem
cannot impose frequency offset. Those need an NTN-capable RAN (e.g. srsRAN/OAI NTN work) or SDR hardware; treat this testbed as
a control-plane/session-behaviour test, not an RF validation.

## Status (be honest about this)
- **Verified in the authoring environment:** profile generator, replay driver (via a Docker shim that records the exact `docker exec ... tc` commands), analyzer (synthetic logs), script syntax, OP -> OPc derivation for the shipped test UE.
- **Read from upstream (commit `1f3bcf7`, 2026-09-05), not executed:** compose files, container names, `.env` keys, image tags, `open5gs-dbctl` provisioning command.
- **Never run end-to-end:** that environment had no Docker and its kernel has no netem/veth. The first real run will likely need small fixes, especially log keywords in `analyze.py` and the ping target.

## Requirements
Linux host (kernel SCTP; macOS is not supported by this stack), Docker with Compose v2 >= 2.14, ~4 GB RAM, root/sudo,
Python 3 + `pycryptodome` (`pip install pycryptodome`) for OPc derivation. Check your firewall (upstream disables `ufw`; this kit does not).

## Run
```bash
cd testbed
./setup.sh                 # clones + pins docker_open5gs, pulls images, starts 5G SA core. Optional arg: host IP
./provision_subscriber.sh  # adds the .env test UE (derives OPc from Ki+OP, matching UERANSIM's opType 'OP')
./run_experiment.sh                                    # default: 24-sat constellation, best pass over Nairobi, +-60 s margin
./run_experiment.sh --aperture 0.25 --service ltem_data   # marginal link: loss ramps up and down across the pass
./run_experiment.sh --feeder-ms 8                       # add feeder-link delay for a bent-pipe path
```
Results land in `testbed/runs/<timestamp>/`: `profile.json`, `replay_events.jsonl`, `ping.log`, `ue.log`, `gnb.log`, `amf.log`, `summary.txt`.

## How to read `summary.txt`
| Line | Healthy result |
|---|---|
| reply_rate_in_outage | ~0 (the link is down) |
| reply_rate_in_pass vs expected_reply_rate_in_pass | close to each other (request and reply both cross the lossy link, so expected = (1-loss)^2) |
| median_rtt_ms_in_pass | >= expected_min_rtt_ms (2 x one-way delay) plus core/processing time |
| seconds_to_first_reply_after_link_up | Small if the UE kept its registration; large (many seconds) if it had to re-register. **This is the number that matters for store-and-forward IoT design.** |
| UE log events | Look for registration/PDU-session re-establishment after the outage. Keywords are guesses against UERANSIM wording; adjust `KEYS` in `analyze.py` after you see real logs. |

## Known risks when you first run it
- No subscriber or wrong credentials: UE never gets a PDU session (script exits after 90 s). Check `docker exec webui misc/db/open5gs-dbctl showall`.
- `PING_TARGET` default `8.8.8.8` needs an internet path through the UPF. Without one, set `PING_TARGET` to a host you control behind the UPF.
- netem acts on egress of `nr_ue` and `nr_gnb` (both privileged in upstream compose, with `tc` from iproute2 in the image). If `tc` errors, check `docker exec nr_ue tc qdisc show`.
- Satellite delay here is only ~2-4 ms one-way (LEO at 550 km), so delay alone will not stress timers. The interesting events are **outage edges and the loss ramp** on marginal links; add `--feeder-ms` or a GEO-like delay if you want timer stress.
- Do not leave the default WebUI credentials (`admin`/`1423`) exposed beyond a lab network.
