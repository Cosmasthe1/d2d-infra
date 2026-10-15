import numpy as np
from ntn_sim.orbit import walker_delta, propagate_ecef, ground_ecef, look_angles, doppler_hz, RE
from ntn_sim.link import fspl_db, Device, Payload, SERVICES, budget, min_aperture_for_margin


def test_fspl_500km_2ghz():
    assert abs(fspl_db(500e3, 2e9) - 152.45) < 0.1


def test_period_550km():
    con = walker_delta(1, 1, 53, 550)
    assert abs(con.period_s / 60 - 95.5) < 0.5


def test_altitude_constant_and_velocity():
    con = walker_delta(12, 3, 53, 550)
    pos, vel = propagate_ecef(con, np.array([0, 1000, 5000.0]))
    r = np.linalg.norm(pos, axis=-1)
    assert np.allclose(r, con.a, rtol=1e-9)


def test_max_doppler_s_band():
    con = walker_delta(1, 1, 53, 550)
    gs = ground_ecef(0.0, 0.0)
    ts = np.arange(0, 86400, 5.0)
    pos, vel = propagate_ecef(con, ts)
    el, rng, rr = look_angles(pos, vel, gs)
    vis = el[:, 0, 0] > np.radians(10)
    d = doppler_hz(rr[:, 0, 0][vis], 2e9)
    assert vis.any()
    assert 25e3 < np.abs(d).max() < 50e3


def test_link_monotonic_in_aperture():
    el, rng = np.array(np.radians(30)), np.array(900e3)
    dev, svc = Device(), SERVICES["nbiot_sms"]
    a = budget(el, rng, RE + 550e3, 2e9, dev, Payload(aperture_m2=1), svc)
    b = budget(el, rng, RE + 550e3, 2e9, dev, Payload(aperture_m2=10), svc)
    assert b["margin_ul"] > a["margin_ul"] and b["margin_dl"] > a["margin_dl"]


def test_min_aperture_closes_link():
    el, rng = np.radians(30), 900e3
    dev, svc, pay = Device(), SERVICES["lte_16qam"], Payload()
    ap = min_aperture_for_margin(el, rng, RE + 550e3, 2e9, dev, pay, svc, 3.0)
    b = budget(np.array(el), np.array(rng), RE + 550e3, 2e9, dev, Payload(aperture_m2=ap), svc)
    assert min(b["margin_ul"], b["margin_dl"]) >= 2.99
