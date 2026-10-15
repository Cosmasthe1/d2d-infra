"""Link budget for a phone / IoT device <-> LEO satellite (S-band-ish, ~2 GHz)."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
from .orbit import C, RE

K_DBW = -228.6  # Boltzmann, dBW/K/Hz


def fspl_db(rng_m, f_hz):
    return 20 * np.log10(4 * np.pi * rng_m * f_hz / C)


def antenna_gain_dbi(area_m2, f_hz, eff=0.6):
    lam = C / f_hz
    return 10 * np.log10(eff * 4 * np.pi * area_m2 / lam**2)


def beam_footprint_km(area_m2, f_hz, slant_m, eff=0.6):
    """Approx. -3 dB footprint diameter at nadir for a circular aperture."""
    d = np.sqrt(4 * area_m2 / np.pi)
    bw = np.radians(70 * (C / f_hz) / d)
    return slant_m * bw / 1e3


@dataclass
class Device:
    name: str = "phone"
    eirp_dbm: float = 23.0       # 3GPP power class 3 (200 mW)
    gain_dbi: float = 0.0        # typical handset, omni-ish
    noise_figure_db: float = 9.0
    t_ant_k: float = 290.0
    env_loss_db: float = 0.0     # extra penetration / body loss


@dataclass
class Payload:
    name: str = "smallsat"
    aperture_m2: float = 2.0
    eff: float = 0.6
    ptx_per_beam_w: float = 10.0
    t_sys_k: float = 500.0
    max_scan_deg: float = 60.0


@dataclass
class Service:
    name: str
    bw_ul_hz: float
    bw_dl_hz: float
    req_snr_db: float            # required SNR incl. any repetition gain


# Required SNRs are planning values, not 3GPP conformance numbers.
SERVICES = {
    "nbiot_sms":  Service("NB-IoT (SMS/telemetry)", 15e3, 180e3, -2.0),
    "ltem_data":  Service("LTE-M style (1.4 MHz)", 180e3, 1.4e6, 0.0),
    "lte_qpsk":   Service("LTE QPSK (5 MHz)", 360e3, 5e6, 2.0),
    "lte_16qam":  Service("LTE 16QAM (5 MHz)", 360e3, 5e6, 12.0),
}

FIXED_LOSSES_DB = 0.5 + 3.0 + 1.0   # atmosphere + polarisation mismatch + pointing


def scan_loss_db(el, a, max_scan_deg):
    from .orbit import nadir_angle
    th = nadir_angle(el, a)
    loss = -10 * np.log10(np.maximum(np.cos(th), 1e-3))
    return np.where(np.degrees(th) > max_scan_deg, np.inf, loss)


def budget(el, rng, a, f_hz, dev: Device, pay: Payload, svc: Service):
    """Return dict of uplink/downlink SNR and margin (dB) for arrays el, rng."""
    g_sat = antenna_gain_dbi(pay.aperture_m2, f_hz, pay.eff)
    scan = scan_loss_db(el, a, pay.max_scan_deg)
    path = fspl_db(rng, f_hz)
    loss = path + FIXED_LOSSES_DB + dev.env_loss_db + scan

    # uplink: device -> satellite
    c_ul = (dev.eirp_dbm - 30) + g_sat - loss                     # dBW
    n_ul = K_DBW + 10 * np.log10(pay.t_sys_k) + 10 * np.log10(svc.bw_ul_hz)
    snr_ul = c_ul - n_ul

    # downlink: satellite -> device
    eirp_sat = 10 * np.log10(pay.ptx_per_beam_w) + g_sat
    t_dev = dev.t_ant_k + 290 * (10 ** (dev.noise_figure_db / 10) - 1)
    c_dl = eirp_sat - loss + dev.gain_dbi
    n_dl = K_DBW + 10 * np.log10(t_dev) + 10 * np.log10(svc.bw_dl_hz)
    snr_dl = c_dl - n_dl

    return {
        "snr_ul": snr_ul, "snr_dl": snr_dl,
        "margin_ul": snr_ul - svc.req_snr_db, "margin_dl": snr_dl - svc.req_snr_db,
        "g_sat_dbi": g_sat,
    }


def min_aperture_for_margin(el, rng, a, f_hz, dev, pay, svc, target_db=3.0):
    """Smallest aperture (m^2) giving >= target margin on both links at (el, rng). Bisection."""
    lo, hi = 0.01, 2000.0
    for _ in range(60):
        mid = np.sqrt(lo * hi)
        p = Payload(**{**pay.__dict__, "aperture_m2": mid})
        b = budget(np.array(el), np.array(rng), a, f_hz, dev, p, svc)
        ok = min(float(b["margin_ul"]), float(b["margin_dl"])) >= target_db
        lo, hi = (lo, mid) if ok else (mid, hi)
    return hi
