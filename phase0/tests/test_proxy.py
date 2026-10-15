import asyncio, socket
import numpy as np
from ntn_sim.orbit import walker_delta
from ntn_sim.schedule import pass_windows, link_state
from emulation.channel_proxy import SatChannelProxy, start

LAT, LON = -1.2921, 36.8219


def test_pass_windows_exist_and_ordered():
    con = walker_delta(24, 6, 53, 550)
    w = pass_windows(con, LAT, LON, duration_s=86400, min_el_deg=20)
    assert len(w) > 3 and all(a.end_s > a.start_s for a in w)
    assert all(w[i].end_s <= w[i + 1].start_s for i in range(len(w) - 1))


def test_link_state_none_outside_window_and_valid_inside():
    con = walker_delta(24, 6, 53, 550)
    w = pass_windows(con, LAT, LON, duration_s=86400, min_el_deg=20)
    mid = (w[0].start_s + w[0].end_s) / 2
    st = link_state(con, LAT, LON, mid)
    assert st and 3 < st["delay_ms"] < 12 and abs(st["doppler_hz"]) < 50e3
    gap_t = (w[0].end_s + w[1].start_s) / 2
    assert link_state(con, LAT, LON, gap_t) is None


def test_proxy_drops_in_outage_and_forwards_in_pass():
    async def run():
        con = walker_delta(24, 6, 53, 550)
        w = pass_windows(con, LAT, LON, duration_s=86400, min_el_deg=20)
        sink = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sink.bind(("127.0.0.1", 0)); sink.setblocking(False)
        target = sink.getsockname()
        # start inside a high-elevation pass, huge speedup keeps delay negligible
        best = max(w, key=lambda p: p.max_el_deg)
        t_in_pass = (best.start_s + best.end_s) / 2
        p = SatChannelProxy(con, LAT, LON, target, t_sim0=t_in_pass, speedup=1.0, seed=3)
        t_in, t_out = await start(p, ("127.0.0.1", 0))
        port = t_in.get_extra_info("sockname")[1]
        c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for i in range(200):
            c.sendto(b"x%d" % i, ("127.0.0.1", port))
        await asyncio.sleep(0.5)
        in_pass = dict(p.stats)
        # now jump into an outage
        gap = (w[0].end_s + w[1].start_s) / 2
        p.t0, p.wall0 = gap, __import__("time").monotonic()
        for i in range(50):
            c.sendto(b"y", ("127.0.0.1", port))
        await asyncio.sleep(0.3)
        t_in.close(); t_out.close(); sink.close()
        return in_pass, p.stats
    a, b = asyncio.run(run())
    assert a["fwd"] > 100 and a["dropped_outage"] == 0
    assert b["dropped_outage"] >= 50
