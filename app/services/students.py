"""Manajemen akun & profil siswa (dipanggil dari rute admin maupun CLI)."""
import re
import sqlite3

from .. import security, timeutil

NAME_RE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ .,'’\-]{1,98}[A-Za-zÀ-ÖØ-öø-ÿ.]$")
NIS_RE = re.compile(r"^[0-9A-Za-z.\-]{3,20}$")


def list_students(db, q=None, status="semua"):
    sql = """SELECT s.user_id AS id, u.full_name, u.is_active, u.must_change_password, u.last_login_at, s.roll_no, s.nis
               FROM students s JOIN users u ON u.id = s.user_id WHERE 1=1"""
    args = []
    if q:
        sql += " AND u.name_key LIKE ? ESCAPE '\\'"
        args.append("%" + q.casefold().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
    if status == "aktif":
        sql += " AND u.is_active = 1"
    elif status == "nonaktif":
        sql += " AND u.is_active = 0"
    sql += " ORDER BY (s.roll_no IS NULL), s.roll_no, u.full_name"
    return db.execute(sql, args).fetchall()


def get_student(db, student_id):
    return db.execute(
        """SELECT s.user_id AS id, u.full_name, u.is_active, u.must_change_password, u.last_login_at, u.created_at,
                  s.roll_no, s.nis, s.class_id
             FROM students s JOIN users u ON u.id = s.user_id WHERE s.user_id = ?""", (student_id,)).fetchone()


def counts(db):
    row = db.execute("SELECT COUNT(*) total, COALESCE(SUM(u.is_active),0) aktif FROM students s JOIN users u ON u.id = s.user_id").fetchone()
    return {"total": row["total"], "aktif": row["aktif"], "nonaktif": row["total"] - row["aktif"]}


def _validate(db, full_name, roll_no, nis, exclude_id=None):
    errors = {}
    name = security.clean_name(full_name)
    if not NAME_RE.match(name):
        errors["full_name"] = "Nama lengkap 3–100 karakter, hanya huruf, spasi, titik, koma, apostrof, dan tanda hubung."
    else:
        dup = db.execute("SELECT id FROM users WHERE role = 'siswa' AND name_key = ?", (security.name_key(name),)).fetchone()
        if dup and dup["id"] != exclude_id:
            errors["full_name"] = ("Nama ini sudah terdaftar. Karena login memakai nama lengkap, bedakan dengan tambahan "
                                   "yang tetap, misalnya inisial nama orang tua atau tanda (B) di akhir nama.")
    roll = None
    if str(roll_no or "").strip():
        if not re.fullmatch(r"\d{1,3}", str(roll_no).strip()) or int(roll_no) < 1:
            errors["roll_no"] = "Nomor absen harus angka 1–999."
        else:
            roll = int(roll_no)
            dup = db.execute("SELECT user_id FROM students WHERE roll_no = ? AND class_id = (SELECT id FROM classes ORDER BY id LIMIT 1)", (roll,)).fetchone()
            if dup and dup["user_id"] != exclude_id:
                errors["roll_no"] = f"Nomor absen {roll} sudah dipakai siswa lain."
    nis = (nis or "").strip() or None
    if nis:
        if not NIS_RE.match(nis):
            errors["nis"] = "NIS 3–20 karakter (huruf, angka, titik, atau tanda hubung)."
        else:
            dup = db.execute("SELECT user_id FROM students WHERE nis = ?", (nis,)).fetchone()
            if dup and dup["user_id"] != exclude_id:
                errors["nis"] = "NIS ini sudah terdaftar pada siswa lain."
    return name, roll, nis, errors


def create_student(db, class_id, full_name, roll_no=None, nis=None):
    """Mengembalikan (student_id, temp_password, errors). Password sementara hanya ditampilkan sekali."""
    name, roll, nis, errors = _validate(db, full_name, roll_no, nis)
    if errors:
        return None, None, errors
    if roll is None:
        roll = (db.execute("SELECT COALESCE(MAX(roll_no),0) FROM students WHERE class_id = ?", (class_id,)).fetchone()[0]) + 1
    temp = security.generate_temp_password()
    try:
        cur = db.execute(
            "INSERT INTO users(role, full_name, name_key, password_hash, is_active, must_change_password, created_at) "
            "VALUES ('siswa', ?, ?, ?, 1, 1, ?)",
            (name, security.name_key(name), security.hash_password(temp), timeutil.iso(timeutil.now())))
        db.execute("INSERT INTO students(user_id, class_id, roll_no, nis) VALUES (?,?,?,?)", (cur.lastrowid, class_id, roll, nis))
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return None, None, {"full_name": "Data bentrok dengan siswa yang sudah ada (nama, nomor absen, atau NIS)."}
    return cur.lastrowid, temp, {}


def update_student(db, student_id, full_name, roll_no, nis):
    name, roll, nis, errors = _validate(db, full_name, roll_no, nis, exclude_id=student_id)
    if errors:
        return errors
    try:
        db.execute("UPDATE users SET full_name = ?, name_key = ? WHERE id = ? AND role = 'siswa'",
                   (name, security.name_key(name), student_id))
        db.execute("UPDATE students SET roll_no = ?, nis = ? WHERE user_id = ?", (roll, nis, student_id))
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return {"full_name": "Data bentrok dengan siswa yang sudah ada (nama, nomor absen, atau NIS)."}
    return {}


def set_active(db, student_id, active):
    db.execute("UPDATE users SET is_active = ? WHERE id = ? AND role = 'siswa'", (1 if active else 0, student_id))
    db.commit()
    if not active:
        security.end_user_sessions(student_id)


def reset_password(db, student_id):
    """Buat password sementara baru, wajib diganti saat login berikutnya, dan akhiri semua sesi siswa."""
    temp = security.generate_temp_password()
    db.execute("UPDATE users SET password_hash = ?, must_change_password = 1 WHERE id = ? AND role = 'siswa'",
               (security.hash_password(temp), student_id))
    db.commit()
    security.end_user_sessions(student_id)
    return temp
