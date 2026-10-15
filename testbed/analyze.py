#!/usr/bin/env python3
"""Correlate ping results and UE log events with the replayed satellite-link profile."""
import argparse, json, re, statistics as st
from datetime import datetime

PING = re.compile(r"^\[(?P<ts>\d+\.\d+)\].*?icmp_seq=(?P<seq>\d+).*?time=(?P<rtt>[\d.]+) ms")
KEYS = re.compile(r"(Registration is successful|PDU Session establishment is successful|Radio link failure|RLF|"
                  r"Connection Release|Signal lost|cell selection|Deregistration|Sync|NG Setup)", re.I)


def parse_ts(s):  # docker --timestamps: 2026-10-15T05:13:21.123456789Z
    s = s.rstrip("Z"); head, _, frac = s.partition(".")
    return datetime.fromisoformat(head + "+00:00").timestamp() + float("0." + (frac or "0"))


def load_events(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def state_at(events, t):
    """Link state (in_pass, delay_ms, loss_pct) at wall time t: last event at or before t."""
    cur = None
    for e in events:
        if e["wall"] <= t:
            cur = e
        else:
            break
    return cur


def analyze(ping_lines, events, interval, ue_lines=()):
    replies = []
    for l in ping_lines:
        m = PING.match(l)
        if m:
            replies.append((float(m["ts"]), int(m["seq"]), float(m["rtt"])))
    t0, t1 = events[0]["wall"], events[-1]["wall"] + 1.0
    exp_per_s = 1.0 / interval
    secs = {}
    for e in events:
        secs[e["t"]] = dict(in_pass=e["in_pass"], replies=0, delay_ms=e["delay_ms"], loss_pct=e["loss_pct"])
    for ts, _, rtt in replies:
        e = state_at(events, ts - rtt / 1000)       # attribute to the second the request left
        if e and t0 <= ts <= t1 + 5:
            secs[e["t"]]["replies"] += 1
    ins = [v for v in secs.values() if v["in_pass"]]
    outs = [v for v in secs.values() if not v["in_pass"]]
    def rate(rows): return sum(r["replies"] for r in rows) / (len(rows) * exp_per_s) if rows else None
    in_rate, out_rate = rate(ins), rate(outs)
    exp_in = st.mean((1 - r["loss_pct"] / 100) ** 2 for r in ins) if ins else None   # request AND reply cross the lossy link
    # recovery: first reply after first in-pass second
    first_in_t = next((e["wall"] for e in events if e["in_pass"]), None)
    rec = next((ts - first_in_t for ts, _, _ in replies if first_in_t and ts >= first_in_t), None)
    rtts = [r for ts, _, r in replies if (e := state_at(events, ts)) and e["in_pass"]]
    mean_delay = st.mean(r["delay_ms"] for r in ins) if ins else None
    res = dict(in_pass_seconds=len(ins), outage_seconds=len(outs),
               reply_rate_in_pass=in_rate, expected_reply_rate_in_pass=exp_in,
               reply_rate_in_outage=out_rate, seconds_to_first_reply_after_link_up=rec,
               median_rtt_ms_in_pass=st.median(rtts) if rtts else None,
               expected_min_rtt_ms=2 * mean_delay if mean_delay else None)
    res["ue_events"] = []
    for l in ue_lines:
        if KEYS.search(l):
            try:
                res["ue_events"].append((round(parse_ts(l.split()[0]) - t0, 1), l.split(None, 1)[1].strip()[:140]))
            except Exception:
                pass
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ping", required=True); ap.add_argument("--events", required=True)
    ap.add_argument("--ue-log"); ap.add_argument("--interval", type=float, default=0.5)
    a = ap.parse_args()
    r = analyze(open(a.ping).read().splitlines(), load_events(a.events), a.interval,
                open(a.ue_log).read().splitlines() if a.ue_log else [])
    ev = r.pop("ue_events")
    for k, v in r.items():
        print(f"{k:55s} {v if not isinstance(v, float) else round(v, 3)}")
    print("\nUE log events (seconds from profile start) - verify keywords against your UERANSIM version:")
    for t, m in ev:
        print(f"  {t:7.1f}s  {m}")


if __name__ == "__main__":
    main()
