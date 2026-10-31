"""Pengaturan jadwal presensi dan geofence. Tidak ada nilai bawaan yang dikarang:
jadwal kosong = presensi mandiri siswa belum dibuka; geofence nonaktif sampai koordinat & radius diisi admin."""
import math
import re
from datetime import datetime

from .. import timeutil

DAY_KEYS = range(7)  # 0 = Senin ... 6 = Minggu
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

DEFAULTS = {"geo_enabled": "0", "geo_lat": "", "geo_lng": "", "geo_radius": ""}
for _i in DAY_KEYS:
    DEFAULTS[f"sched_{_i}_open"] = ""
    DEFAULTS[f"sched_{_i}_close"] = ""


def load(db):
    data = dict(DEFAULTS)
    for row in db.execute("SELECT key, value FROM settings"):
        if row["key"] in data:
            data[row["key"]] = row["value"]
    return data


def save(db, updates):
    for key, value in updates.items():
        if key in DEFAULTS:
            db.execute("INSERT INTO settings(key, value) VALUES (?, ?) "
                       "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
    db.commit()


def validate_form(form):
    """Validasi isian halaman Pengaturan. Mengembalikan (nilai_bersih, daftar_error)."""
    clean, errors = {}, []
    for i in DAY_KEYS:
        name = timeutil.DAYS_ID[i]
        o = (form.get(f"sched_{i}_open") or "").strip()
        c = (form.get(f"sched_{i}_close") or "").strip()
        if not o and not c:
            clean[f"sched_{i}_open"] = clean[f"sched_{i}_close"] = ""
            continue
        if not (TIME_RE.match(o) and TIME_RE.match(c)):
            errors.append(f"{name}: isi jam buka dan jam tutup dengan format JJ:MM (contoh 06:30), atau kosongkan keduanya.")
            continue
        if o >= c:
            errors.append(f"{name}: jam tutup harus lebih akhir dari jam buka.")
            continue
        clean[f"sched_{i}_open"], clean[f"sched_{i}_close"] = o, c

    enabled = form.get("geo_enabled") == "1"
    lat_s, lng_s, rad_s = (form.get(k, "").strip().replace(",", ".") for k in ("geo_lat", "geo_lng", "geo_radius"))
    lat = lng = radius = None
    try:
        lat = float(lat_s) if lat_s else None
        lng = float(lng_s) if lng_s else None
        radius = int(float(rad_s)) if rad_s else None
    except ValueError:
        errors.append("Latitude, longitude, dan radius harus berupa angka.")
    if lat is not None and not (math.isfinite(lat) and -90 <= lat <= 90):
        errors.append("Latitude harus antara -90 dan 90.")
    if lng is not None and not (math.isfinite(lng) and -180 <= lng <= 180):
        errors.append("Longitude harus antara -180 dan 180.")
    if radius is not None and not (10 <= radius <= 5000):
        errors.append("Radius harus antara 10 dan 5000 meter.")
    if enabled and (lat is None or lng is None or radius is None):
        errors.append("Untuk mengaktifkan verifikasi lokasi, isi latitude, longitude, dan radius terlebih dahulu.")
    clean["geo_enabled"] = "1" if enabled else "0"
    clean["geo_lat"] = "" if lat is None else repr(lat)
    clean["geo_lng"] = "" if lng is None else repr(lng)
    clean["geo_radius"] = "" if radius is None else str(radius)
    return clean, errors


def geofence(settings):
    """Mengembalikan (lat, lng, radius_m) bila geofence aktif dan lengkap, selain itu None."""
    if settings["geo_enabled"] != "1":
        return None
    try:
        return float(settings["geo_lat"]), float(settings["geo_lng"]), int(settings["geo_radius"])
    except ValueError:
        return None


def window_for(settings, d):
    """Jadwal (buka, tutup) berupa string 'HH:MM' untuk tanggal d, atau None bila tidak ada sesi."""
    o, c = settings[f"sched_{d.weekday()}_open"], settings[f"sched_{d.weekday()}_close"]
    return (o, c) if o and c else None


def window_state(settings, now):
    """Status sesi presensi pada waktu `now`:
    unset (jadwal belum diatur), off (tidak ada sesi hari ini), before, open, after."""
    if not any(settings[f"sched_{i}_open"] for i in DAY_KEYS):
        return {"state": "unset", "open": None, "close": None, "seconds_left": 0,
                "message": "Jadwal presensi belum diatur oleh admin kelas."}
    win = window_for(settings, now.date())
    if not win:
        return {"state": "off", "open": None, "close": None, "seconds_left": 0,
                "message": "Tidak ada sesi presensi hari ini."}
    o, c = win
    open_dt = datetime.combine(now.date(), datetime.strptime(o, "%H:%M").time(), tzinfo=now.tzinfo)
    close_dt = datetime.combine(now.date(), datetime.strptime(c, "%H:%M").time(), tzinfo=now.tzinfo)
    if now < open_dt:
        return {"state": "before", "open": o, "close": c, "seconds_left": 0,
                "message": f"Presensi dibuka pukul {o} WIB."}
    if now >= close_dt:
        return {"state": "after", "open": o, "close": c, "seconds_left": 0,
                "message": f"Sesi presensi hari ini ditutup pukul {c} WIB. Hubungi pengurus kelas bila perlu koreksi."}
    return {"state": "open", "open": o, "close": c, "seconds_left": int((close_dt - now).total_seconds()),
            "message": f"Presensi dibuka sampai pukul {c} WIB."}
