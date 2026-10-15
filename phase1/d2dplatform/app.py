"""Phase 1: D2D service platform (device registry, uplink ingest, store-and-forward downlink, metering)."""
from __future__ import annotations
import os, sqlite3, secrets, sys, threading, time
from typing import Optional
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

try:
    from ntn_sim.orbit import walker_delta
except ImportError:  # allow running without PYTHONPATH
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "phase0"))
    from ntn_sim.orbit import walker_delta
from ntn_sim.schedule import pass_windows, link_state
from . import decoders
from .billing import Plan, invoice

MAX_PAYLOAD = 100  # bytes; planning limit for NB-IoT NTN style links
SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants(id INTEGER PRIMARY KEY, name TEXT, api_key TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS devices(id INTEGER PRIMARY KEY, tenant_id INT, dev_eui TEXT UNIQUE, vertical TEXT, created REAL);
CREATE TABLE IF NOT EXISTS uplinks(id INTEGER PRIMARY KEY, device_id INT, seq INT, ts REAL, payload BLOB, decoded TEXT,
  UNIQUE(device_id, seq));
CREATE TABLE IF NOT EXISTS downlinks(id INTEGER PRIMARY KEY, device_id INT, payload BLOB, status TEXT, created REAL, sent REAL);
CREATE TABLE IF NOT EXISTS usage(id INTEGER PRIMARY KEY, tenant_id INT, month TEXT, kind TEXT, bytes INT);
"""


class TenantIn(BaseModel):
    name: str

class DeviceIn(BaseModel):
    dev_eui: str
    vertical: str = "raw"

class UplinkIn(BaseModel):
    dev_eui: str
    payload_hex: str
    seq: Optional[int] = None
    ts: Optional[float] = None

class DownlinkIn(BaseModel):
    payload_hex: str

class DispatchIn(BaseModel):
    sim_t: float = 0.0


def create_app(db_path: str = ":memory:", admin_key: Optional[str] = None, gateway_key: Optional[str] = None,
               sats: int = 24, lat: float = -1.2921, lon: float = 36.8219) -> FastAPI:
    admin_key = admin_key or os.environ.get("ADMIN_KEY", "dev-admin")
    gateway_key = gateway_key or os.environ.get("GATEWAY_KEY", "dev-gateway")
    db = sqlite3.connect(db_path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    lock = threading.Lock()
    con = walker_delta(sats, 6 if sats % 6 == 0 else 1, 53, 550)
    app = FastAPI(title="D2D Platform", version="0.1")

    def tenant(api_key: Optional[str]):
        row = db.execute("SELECT * FROM tenants WHERE api_key=?", (api_key,)).fetchone() if api_key else None
        if not row:
            raise HTTPException(401, "invalid api key")
        return row

    def device(t, dev_eui):
        row = db.execute("SELECT * FROM devices WHERE dev_eui=? AND tenant_id=?", (dev_eui, t["id"])).fetchone()
        if not row:
            raise HTTPException(404, "device not found")
        return row

    def meter(tenant_id, kind, nbytes, ts):
        db.execute("INSERT INTO usage(tenant_id,month,kind,bytes) VALUES(?,?,?,?)",
                   (tenant_id, time.strftime("%Y-%m", time.gmtime(ts)), kind, nbytes))

    @app.get("/healthz")
    def health():
        return {"ok": True}

    @app.post("/v1/tenants")
    def create_tenant(body: TenantIn, x_admin_key: str = Header(None)):
        if x_admin_key != admin_key:
            raise HTTPException(401, "bad admin key")
        key = "tk_" + secrets.token_urlsafe(24)
        with lock:
            db.execute("INSERT INTO tenants(name, api_key) VALUES(?,?)", (body.name, key)); db.commit()
        return {"name": body.name, "api_key": key}

    @app.post("/v1/devices", status_code=201)
    def add_device(body: DeviceIn, x_api_key: str = Header(None)):
        t = tenant(x_api_key)
        if body.vertical not in ("raw", "telematics", "climate"):
            raise HTTPException(422, "unknown vertical")
        try:
            with lock:
                db.execute("INSERT INTO devices(tenant_id,dev_eui,vertical,created) VALUES(?,?,?,?)",
                           (t["id"], body.dev_eui, body.vertical, time.time())); db.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(409, "device exists")
        return {"dev_eui": body.dev_eui, "vertical": body.vertical}

    @app.get("/v1/devices")
    def list_devices(x_api_key: str = Header(None)):
        t = tenant(x_api_key)
        return [dict(r) for r in db.execute("SELECT dev_eui, vertical FROM devices WHERE tenant_id=?", (t["id"],))]

    @app.post("/v1/gateway/uplink")
    def ingest(body: UplinkIn, x_gateway_key: str = Header(None)):
        if x_gateway_key != gateway_key:
            raise HTTPException(401, "bad gateway key")
        d = db.execute("SELECT * FROM devices WHERE dev_eui=?", (body.dev_eui,)).fetchone()
        if not d:
            raise HTTPException(404, "unknown device")
        try:
            payload = bytes.fromhex(body.payload_hex)
        except ValueError:
            raise HTTPException(422, "payload_hex must be hex")
        if len(payload) > MAX_PAYLOAD:
            raise HTTPException(413, f"payload > {MAX_PAYLOAD} bytes")
        try:
            decoded = decoders.decode(d["vertical"], payload)
        except Exception:
            raise HTTPException(422, "payload does not match vertical schema")
        ts = body.ts or time.time()
        import json
        with lock:
            try:
                db.execute("INSERT INTO uplinks(device_id,seq,ts,payload,decoded) VALUES(?,?,?,?,?)",
                           (d["id"], body.seq, ts, payload, json.dumps(decoded)))
            except sqlite3.IntegrityError:
                return {"status": "duplicate"}      # store-and-forward retries are idempotent
            meter(d["tenant_id"], "uplink", len(payload), ts); db.commit()
        return {"status": "accepted", "decoded": decoded}

    @app.get("/v1/devices/{dev_eui}/uplinks")
    def uplinks(dev_eui: str, limit: int = 50, x_api_key: str = Header(None)):
        import json
        d = device(tenant(x_api_key), dev_eui)
        rows = db.execute("SELECT ts, seq, payload, decoded FROM uplinks WHERE device_id=? ORDER BY ts DESC LIMIT ?",
                          (d["id"], limit)).fetchall()
        return [dict(ts=r["ts"], seq=r["seq"], payload_hex=r["payload"].hex(), decoded=json.loads(r["decoded"])) for r in rows]

    @app.post("/v1/devices/{dev_eui}/downlink", status_code=202)
    def queue_downlink(dev_eui: str, body: DownlinkIn, x_api_key: str = Header(None)):
        d = device(tenant(x_api_key), dev_eui)
        payload = bytes.fromhex(body.payload_hex)
        if len(payload) > MAX_PAYLOAD:
            raise HTTPException(413, f"payload > {MAX_PAYLOAD} bytes")
        with lock:
            cur = db.execute("INSERT INTO downlinks(device_id,payload,status,created) VALUES(?,?,?,?)",
                             (d["id"], payload, "queued", time.time())); db.commit()
        return {"id": cur.lastrowid, "status": "queued"}

    @app.post("/v1/gateway/dispatch")
    def dispatch(body: DispatchIn, x_gateway_key: str = Header(None)):
        """Gateway calls this each tick. Queued downlinks are released only while a satellite is in view."""
        if x_gateway_key != gateway_key:
            raise HTTPException(401, "bad gateway key")
        st = link_state(con, lat, lon, body.sim_t)
        if st is None:
            return {"link": "down", "released": []}
        released = []
        with lock:
            rows = db.execute("SELECT d.id, d.payload, v.dev_eui, v.tenant_id FROM downlinks d JOIN devices v ON v.id=d.device_id "
                              "WHERE d.status='queued' ORDER BY d.id").fetchall()
            for r in rows:
                if st["loss_prob"] > 0.5:
                    break
                db.execute("UPDATE downlinks SET status='sent', sent=? WHERE id=?", (time.time(), r["id"]))
                meter(r["tenant_id"], "downlink", len(r["payload"]), time.time())
                released.append({"dev_eui": r["dev_eui"], "payload_hex": r["payload"].hex()})
            db.commit()
        return {"link": "up", "el_deg": st["el_deg"], "released": released}

    @app.get("/v1/network/next-pass")
    def next_pass(after: float = 0.0, horizon_s: float = 86400, min_el_deg: float = 20.0):
        w = [p for p in pass_windows(con, lat, lon, t0=after, duration_s=horizon_s, min_el_deg=min_el_deg) if p.end_s > after]
        if not w:
            return {"next": None}
        p = w[0]
        return {"next": dict(start_s=p.start_s, end_s=p.end_s, max_el_deg=p.max_el_deg,
                             wait_s=max(0.0, p.start_s - after))}

    @app.get("/v1/billing/usage")
    def usage(month: Optional[str] = None, x_api_key: str = Header(None)):
        t = tenant(x_api_key)
        month = month or time.strftime("%Y-%m", time.gmtime())
        n_dev = db.execute("SELECT COUNT(*) c FROM devices WHERE tenant_id=?", (t["id"],)).fetchone()["c"]
        msgs = db.execute("SELECT COUNT(*) c FROM usage WHERE tenant_id=? AND month=?", (t["id"], month)).fetchone()["c"]
        b = db.execute("SELECT COALESCE(SUM(bytes),0) s FROM usage WHERE tenant_id=? AND month=?", (t["id"], month)).fetchone()["s"]
        return {"month": month, "bytes": b, **invoice(Plan(), n_dev, msgs)}

    return app

