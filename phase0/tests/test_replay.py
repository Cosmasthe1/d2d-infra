import json, os, stat, subprocess, sys, textwrap
from emulation.gen_profile import build

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REPLAY = os.path.join(ROOT, "testbed", "replay_profile.py")


def test_profile_has_outage_pass_outage():
    p = build(-1.2921, 36.8219, lead_s=30, tail_s=30)
    inp = [r["in_pass"] for r in p["rows"]]
    assert inp[0] is False and inp[-1] is False and any(inp)
    assert p["rows"][0]["loss_pct"] == 100.0
    ins = [r for r in p["rows"] if r["in_pass"]]
    assert all(1.5 < r["delay_ms"] < 12 for r in ins)  # ~1.8 ms at zenith (550 km), ~4.3 ms at 20 deg
    assert all(abs(r["doppler_hz"]) < 50_000 for r in ins)
    assert max(r["el_deg"] for r in ins) >= 20


def test_feeder_delay_is_added():
    a = build(-1.2921, 36.8219, feeder_ms=0.0, lead_s=0, tail_s=0)["rows"][5]["delay_ms"]
    b = build(-1.2921, 36.8219, feeder_ms=8.0, lead_s=0, tail_s=0)["rows"][5]["delay_ms"]
    assert abs((b - a) - 8.0) < 0.05


def test_replay_issues_expected_docker_commands(tmp_path):
    shim = tmp_path / "docker"
    calls = tmp_path / "calls.txt"
    shim.write_text(f'#!/usr/bin/env bash\necho "$@" >> {calls}\n')
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    prof = {"rows": [
        {"t": 0, "in_pass": False, "delay_ms": 0.0, "loss_pct": 100.0, "el_deg": None},
        {"t": 1, "in_pass": True, "delay_ms": 5.2, "loss_pct": 3.5, "el_deg": 40.0},
        {"t": 2, "in_pass": True, "delay_ms": 4.8, "loss_pct": 0.0, "el_deg": 55.0}]}
    pf = tmp_path / "p.json"; pf.write_text(json.dumps(prof))
    env = {**os.environ, "DOCKER": str(shim), "DEV": "eth0"}
    r = subprocess.run([sys.executable, REPLAY, str(pf), "--speedup", "50", "--log", str(tmp_path / "ev.jsonl")],
                       env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    lines = calls.read_text().strip().splitlines()
    assert lines[0] == "exec nr_ue tc qdisc replace dev eth0 root netem loss 100%"
    assert lines[1] == "exec nr_gnb tc qdisc replace dev eth0 root netem loss 100%"
    assert "change dev eth0 root netem delay 5.2ms 0.3ms loss 3.50%" in lines[2]
    assert lines[-2].endswith("tc qdisc del dev eth0 root") and lines[-1].endswith("tc qdisc del dev eth0 root")
    ev = [json.loads(l) for l in (tmp_path / "ev.jsonl").read_text().splitlines()]
    assert [e["in_pass"] for e in ev] == [False, True, True]
