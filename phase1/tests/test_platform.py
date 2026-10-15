import numpy as np
import pytest
from fastapi.testclient import TestClient
from d2dplatform.app import create_app
from d2dplatform import decoders
from ntn_sim.orbit import walker_delta
from ntn_sim.schedule import pass_windows

LAT, LON = -1.2921, 36.8219
GW = {"X-Gateway-Key": "dev-gateway"}


@pytest.fixture()
def client():
    return TestClient(create_app(":memory:"))


@pytest.fixture()
def tenant(client):
    r = client.post("/v1/tenants", json={"name": "acme"}, headers={"X-Admin-Key": "dev-admin"})
    assert r.status_code == 200
    return {"X-Api-Key": r.json()["api_key"]}


def test_auth_required(client):
    assert client.get("/v1/devices").status_code == 401
    assert client.post("/v1/tenants", json={"name": "x"}).status_code == 401


def test_decoder_roundtrip():
    p = decoders.encode_telematics(-1.2921, 36.8219, 87, ignition=True, alert=True)
    d = decoders.decode("telematics", p)
    assert abs(d["lat"] + 1.2921) < 1e-6 and d["ignition"] and d["alert"] and not d["charging"]
    c = decoders.decode("climate", decoders.encode_climate(7, 24.35, 31.2, 90))
    assert c["temp_c"] == 24.35 and c["soil_moisture_pct"] == 31.2 and len(decoders.encode_climate(1, 1, 1, 1)) == 7


def test_device_uplink_dedupe_and_metering(client, tenant):
    assert client.post("/v1/devices", json={"dev_eui": "ev-001", "vertical": "telematics"}, headers=tenant).status_code == 201
    assert client.post("/v1/devices", json={"dev_eui": "ev-001"}, headers=tenant).status_code == 409
    pl = decoders.encode_telematics(-1.3, 36.8, 55).hex()
    r = client.post("/v1/gateway/uplink", json={"dev_eui": "ev-001", "payload_hex": pl, "seq": 1}, headers=GW)
    assert r.json()["status"] == "accepted" and r.json()["decoded"]["battery_pct"] == 55
    # retry of same seq (store-and-forward) must not double count
    assert client.post("/v1/gateway/uplink", json={"dev_eui": "ev-001", "payload_hex": pl, "seq": 1}, headers=GW).json()["status"] == "duplicate"
    client.post("/v1/gateway/uplink", json={"dev_eui": "ev-001", "payload_hex": pl, "seq": 2}, headers=GW)
    ups = client.get("/v1/devices/ev-001/uplinks", headers=tenant).json()
    assert len(ups) == 2
    u = client.get("/v1/billing/usage", headers=tenant).json()
    assert u["messages"] == 2 and u["devices"] == 1 and u["extra_messages"] == 0 and u["total"] == 1000.0


def test_tenant_isolation(client, tenant):
    client.post("/v1/devices", json={"dev_eui": "a1"}, headers=tenant)
    other = client.post("/v1/tenants", json={"name": "other"}, headers={"X-Admin-Key": "dev-admin"}).json()["api_key"]
    assert client.get("/v1/devices/a1/uplinks", headers={"X-Api-Key": other}).status_code == 404


def test_validation(client, tenant):
    client.post("/v1/devices", json={"dev_eui": "c1", "vertical": "climate"}, headers=tenant)
    assert client.post("/v1/gateway/uplink", json={"dev_eui": "c1", "payload_hex": "zz"}, headers=GW).status_code == 422
    assert client.post("/v1/gateway/uplink", json={"dev_eui": "c1", "payload_hex": "00" * 3}, headers=GW).status_code == 422
    assert client.post("/v1/gateway/uplink", json={"dev_eui": "c1", "payload_hex": "00" * 200}, headers=GW).status_code == 413
    assert client.post("/v1/gateway/uplink", json={"dev_eui": "nope", "payload_hex": "00"}, headers=GW).status_code == 404
    assert client.post("/v1/gateway/uplink", json={"dev_eui": "c1", "payload_hex": "00"}).status_code == 401


def test_downlink_held_until_pass(client, tenant):
    client.post("/v1/devices", json={"dev_eui": "d1"}, headers=tenant)
    assert client.post("/v1/devices/d1/downlink", json={"payload_hex": "a1b2"}, headers=tenant).status_code == 202
    con = walker_delta(24, 6, 53, 550)
    w = pass_windows(con, LAT, LON, duration_s=86400, min_el_deg=20)
    gap = (w[0].end_s + w[1].start_s) / 2
    r = client.post("/v1/gateway/dispatch", json={"sim_t": gap}, headers=GW).json()
    assert r["link"] == "down" and r["released"] == []
    best = max(w, key=lambda p: p.max_el_deg)
    r = client.post("/v1/gateway/dispatch", json={"sim_t": (best.start_s + best.end_s) / 2}, headers=GW).json()
    assert r["link"] == "up" and r["released"][0]["payload_hex"] == "a1b2"
    # not re-sent
    r2 = client.post("/v1/gateway/dispatch", json={"sim_t": (best.start_s + best.end_s) / 2}, headers=GW).json()
    assert r2["released"] == []


def test_next_pass(client):
    r = client.get("/v1/network/next-pass", params={"after": 0}).json()["next"]
    assert r and r["end_s"] > r["start_s"] and r["wait_s"] >= 0
