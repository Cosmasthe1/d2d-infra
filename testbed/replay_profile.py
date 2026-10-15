#!/usr/bin/env python3
"""Replay an impairment profile on the UERANSIM radio link.

UERANSIM simulates the Uu radio link as UDP between the nr_ue and nr_gnb containers (RLS, port 4997), so we shape
each container's egress with tc netem: UE->gNB uses nr_ue's egress, gNB->UE uses nr_gnb's egress. Each side gets the
one-way delay; a ping crosses the link once each way, so added RTT = 2x one-way delay. During outage seconds loss is 100%.

Env:  DOCKER=docker (override with a shim for dry runs)   DEV=eth0
Usage: replay_profile.py profile.json [--speedup 1] [--containers nr_ue nr_gnb] [--log events.jsonl]
"""
import argparse, json, os, subprocess, sys, time

DOCKER = os.environ.get("DOCKER", "docker")
DEV = os.environ.get("DEV", "eth0")


def tc(container, args):
    cmd = [DOCKER, "exec", container, "tc", "qdisc", *args]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r


def apply(container, row, first):
    verb = "replace" if first else "change"
    loss = f"{row['loss_pct']:.2f}%"
    if row["in_pass"]:
        a = [verb, "dev", DEV, "root", "netem", "delay", f"{row['delay_ms']:.1f}ms", "0.3ms", "loss", loss]
    else:
        a = [verb, "dev", DEV, "root", "netem", "loss", "100%"]
    r = tc(container, a)
    if r.returncode != 0 and not first:                    # 'change' fails if qdisc vanished; fall back to replace
        r = tc(container, ["replace"] + a[1:])
    if r.returncode != 0:
        print(f"tc failed on {container}: {r.stderr.strip()}", file=sys.stderr)
    return r.returncode == 0


def cleanup(containers):
    for c in containers:
        tc(c, ["del", "dev", DEV, "root"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile"); ap.add_argument("--speedup", type=float, default=1.0)
    ap.add_argument("--containers", nargs="+", default=["nr_ue", "nr_gnb"])
    ap.add_argument("--log", default="replay_events.jsonl")
    a = ap.parse_args()
    prof = json.load(open(a.profile))
    t0 = time.time()
    ok = True
    try:
        with open(a.log, "w") as log:
            for i, row in enumerate(prof["rows"]):
                for c in a.containers:
                    ok &= apply(c, row, first=(i == 0))
                log.write(json.dumps(dict(wall=time.time(), t=row["t"], in_pass=row["in_pass"], delay_ms=row["delay_ms"],
                                          loss_pct=row["loss_pct"], el_deg=row["el_deg"])) + "\n"); log.flush()
                nxt = t0 + (i + 1) / a.speedup
                time.sleep(max(0.0, nxt - time.time()))
    finally:
        cleanup(a.containers)
    print("replay finished", "OK" if ok else "WITH tc ERRORS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
