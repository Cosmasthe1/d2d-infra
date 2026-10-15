import json, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "testbed"))
from analyze import analyze


def synth(loss_in_pass=0.0, lead=10, passlen=30, tail=10, delay_ms=4.0, interval=0.5, seed=1):
    rng = random.Random(seed)
    base = 1_000_000.0
    events, ping = [], []
    for t in range(lead + passlen + tail):
        inp = lead <= t < lead + passlen
        events.append(dict(wall=base + t, t=t, in_pass=inp, delay_ms=delay_ms if inp else 0.0,
                           loss_pct=100 * loss_in_pass if inp else 100.0, el_deg=40 if inp else None))
    seq = 0
    n = int((lead + passlen + tail) / interval)
    for i in range(n):
        ts = base + i * interval
        t = int(i * interval)
        e = events[t]
        seq += 1
        ok = e["in_pass"] and rng.random() > (1 - (1 - e["loss_pct"] / 100) ** 2)
        if ok:
            rtt = 2 * delay_ms + 20.0                     # 2D radio + 20 ms core/processing
            ping.append(f"[{ts + rtt/1000:.6f}] 64 bytes from 8.8.8.8: icmp_seq={seq} ttl=117 time={rtt:.1f} ms")
        else:
            ping.append(f"[{ts:.6f}] no answer yet for icmp_seq={seq}")
    return ping, events


def test_clean_pass_replies_only_in_pass():
    ping, events = synth(loss_in_pass=0.0)
    r = analyze(ping, events, 0.5)
    assert r["reply_rate_in_pass"] > 0.95
    assert r["reply_rate_in_outage"] == 0
    assert 0 <= r["seconds_to_first_reply_after_link_up"] < 1.0       # measured from link-up, so ~one ping interval at most
    assert abs(r["expected_min_rtt_ms"] - 8.0) < 1e-6
    assert r["median_rtt_ms_in_pass"] >= r["expected_min_rtt_ms"]


def test_lossy_pass_matches_model():
    ping, events = synth(loss_in_pass=0.3, passlen=200, seed=5)
    r = analyze(ping, events, 0.5)
    assert abs(r["expected_reply_rate_in_pass"] - 0.49) < 1e-6          # (1-0.3)^2
    assert abs(r["reply_rate_in_pass"] - 0.49) < 0.08
