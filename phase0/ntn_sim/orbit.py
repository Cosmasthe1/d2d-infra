"""Circular-orbit constellation geometry (spherical Earth, two-body, no perturbations).

Good enough for coverage / Doppler / delay planning. Not good enough for
conjunction analysis or precise pass prediction (use SGP4 + real TLEs for that).
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

MU = 3.986004418e14      # m^3/s^2
RE = 6371000.0           # mean Earth radius, m
WE = 7.2921159e-5        # Earth rotation rate, rad/s
C = 299792458.0          # m/s


@dataclass(frozen=True)
class Constellation:
    a: float             # semi-major axis, m
    inc: float           # inclination, rad
    raan: np.ndarray     # (N,) rad
    u0: np.ndarray       # (N,) argument of latitude at t=0, rad

    @property
    def n_sats(self) -> int:
        return len(self.raan)

    @property
    def mean_motion(self) -> float:
        return np.sqrt(MU / self.a**3)

    @property
    def period_s(self) -> float:
        return 2 * np.pi / self.mean_motion

    @property
    def altitude_km(self) -> float:
        return (self.a - RE) / 1e3


def walker_delta(total: int, planes: int, inc_deg: float, alt_km: float,
                 phasing: int = 1) -> Constellation:
    """Walker-delta i:T/P/F constellation."""
    if total % planes:
        raise ValueError("total must be divisible by planes")
    per = total // planes
    raan, u0 = [], []
    for p in range(planes):
        for s in range(per):
            raan.append(2 * np.pi * p / planes)
            u0.append(2 * np.pi * s / per + 2 * np.pi * phasing * p / total)
    return Constellation(a=RE + alt_km * 1e3, inc=np.radians(inc_deg),
                         raan=np.array(raan), u0=np.array(u0))


def propagate_ecef(con: Constellation, t: np.ndarray):
    """Return position (T,N,3) and ECEF-frame velocity (T,N,3) in metres, m/s."""
    t = np.atleast_1d(t).astype(float)[:, None]
    n = con.mean_motion
    u = con.u0[None, :] + n * t
    cO, sO = np.cos(con.raan)[None, :], np.sin(con.raan)[None, :]
    ci, si = np.cos(con.inc), np.sin(con.inc)
    xo, yo = con.a * np.cos(u), con.a * np.sin(u)
    vxo, vyo = -con.a * n * np.sin(u), con.a * n * np.cos(u)

    def to_eci(x, y):
        return (x * cO - y * ci * sO, x * sO + y * ci * cO, y * si)

    x, y, z = to_eci(xo, yo)
    vx, vy, vz = to_eci(vxo, vyo)
    th = WE * t
    c, s = np.cos(th), np.sin(th)
    xe, ye = x * c + y * s, -x * s + y * c
    vxe_r, vye_r = vx * c + vy * s, -vx * s + vy * c
    # velocity relative to rotating Earth: v_ecef = R v_eci - w x r_ecef
    vxe, vye = vxe_r + WE * ye, vye_r - WE * xe
    pos = np.stack([xe, ye, z], axis=-1)
    vel = np.stack([vxe, vye, vz], axis=-1)
    return pos, vel


def ground_ecef(lat_deg, lon_deg) -> np.ndarray:
    lat, lon = np.radians(np.atleast_1d(lat_deg)), np.radians(np.atleast_1d(lon_deg))
    return RE * np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], axis=-1)


def look_angles(pos, vel, gs):
    """Elevation (rad), slant range (m), range-rate (m/s; + = receding) for sats vs ground points.

    pos, vel: (T,N,3); gs: (G,3).  Returns arrays shaped (T,N,G).
    """
    rho = pos[:, :, None, :] - gs[None, None, :, :]
    rng = np.linalg.norm(rho, axis=-1)
    up = gs / np.linalg.norm(gs, axis=-1, keepdims=True)
    sin_el = np.einsum("tngk,gk->tng", rho, up) / rng
    el = np.arcsin(np.clip(sin_el, -1, 1))
    rr = np.einsum("tngk,tnk->tng", rho, vel) / rng
    return el, rng, rr


def doppler_hz(range_rate, f_hz):
    return -f_hz * range_rate / C


def one_way_delay_ms(rng):
    return rng / C * 1e3


def nadir_angle(el, a):
    """Off-nadir angle (rad) at the satellite for a user at elevation el."""
    return np.arcsin(np.clip(RE * np.cos(el) / a, -1, 1))
