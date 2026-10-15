"""Compact binary payload decoders. NTN uplinks are tiny, so payloads are packed structs, not JSON."""
import struct

# telematics: lat_e6 int32 | lon_e6 int32 | battery_pct uint8 | flags uint8   (10 bytes)
# bit0 ignition, bit1 charging, bit2 crash/alert
_TEL = struct.Struct(">iiBB")
# climate: sensor_id uint16 | temp_c_x100 int16 | soil_moist_x100 int16 | battery_pct uint8   (7 bytes)
_CLI = struct.Struct(">HhhB")


def decode(vertical: str, payload: bytes) -> dict:
    if vertical == "telematics":
        la, lo, bat, fl = _TEL.unpack(payload)
        return dict(lat=la / 1e6, lon=lo / 1e6, battery_pct=bat, ignition=bool(fl & 1),
                    charging=bool(fl & 2), alert=bool(fl & 4))
    if vertical == "climate":
        sid, t, m, bat = _CLI.unpack(payload)
        return dict(sensor_id=sid, temp_c=t / 100, soil_moisture_pct=m / 100, battery_pct=bat)
    return {}


def encode_telematics(lat, lon, battery, ignition=False, charging=False, alert=False) -> bytes:
    return _TEL.pack(round(lat * 1e6), round(lon * 1e6), battery, int(ignition) | int(charging) << 1 | int(alert) << 2)


def encode_climate(sensor_id, temp_c, soil_pct, battery) -> bytes:
    return _CLI.pack(sensor_id, round(temp_c * 100), round(soil_pct * 100), battery)
