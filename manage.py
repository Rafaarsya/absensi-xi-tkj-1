#!/usr/bin/env python3
"""CLI administrasi: inisialisasi database, akun admin, impor siswa (beserta sandi sementara),
reset sandi, dan aktif/nonaktif akun.

Contoh:
  python manage.py init-db
  python manage.py create-admin --name "Ketua Kelas XI TKJ 1"
  python manage.py import-students data/daftar_siswa_XI_TKJ_1.md
"""
import argparse
import csv
import getpass
import os
import re
import sys
from pathlib import Path

from app import create_app, db as dbmod, security, timeutil
from app.services import students as stu


def _app():
    return create_app()


def cmd_init_db(args):
    app = _app()
    conn = dbmod.connect(app.config["DATABASE"])
    applied = dbmod.migrate(conn)
    dbmod.seed_class(conn, app.config["CLASS_NAME"], app.config["SCHOOL_NAME"])
    conn.close()
    print("Migrasi diterapkan:", ", ".join(applied) if applied else "tidak ada (sudah terbaru)")
    print(f"Kelas: {app.config['CLASS_NAME']} — {app.config['SCHOOL_NAME']}")
    print(f"Database: {app.config['DATABASE']}")


def _read_password(args):
    if args.password_stdin:
        return sys.stdin.readline().rstrip("\n")
    first = getpass.getpass("Kata sandi: ")
    if first != getpass.getpass("Ulangi kata sandi: "):
        sys.exit("Kata sandi tidak sama.")
    return first


def cmd_create_admin(args):
    app = _app()
    with app.app_context():
        conn = dbmod.get_db()
        name = security.clean_name(args.name)
        if len(name) < 3:
            sys.exit("Nama terlalu pendek.")
        password = _read_password(args)
        problem = security.validate_new_password(password, name)
        if problem:
            sys.exit(problem)
        if conn.execute("SELECT 1 FROM users WHERE role IN ('admin','guru') AND name_key=?", (security.name_key(name),)).fetchone():
            sys.exit("Akun admin dengan nama itu sudah ada. Pakai `reset-password` untuk mengganti kata sandi.")
        conn.execute(
            "INSERT INTO users(role, full_name, name_key, password_hash, is_active, must_change_password, created_at) "
            "VALUES ('admin', ?, ?, ?, 1, 0, ?)",
            (name, security.name_key(name), security.hash_password(password), timeutil.iso(timeutil.now())))
        conn.commit()
        print(f"Akun admin dibuat: {name}")
        if not app.config["ADMIN_ACCESS_KEY"]:
            print("PERINGATAN: ADMIN_ACCESS_KEY belum diatur di .env, login admin belum bisa dipakai.")


def _parse_names(path):
    """Mendukung tabel markdown (| No | Nama |) maupun satu nama per baris. Mengembalikan [(no, nama)]."""
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or set(line) <= set("|-: "):
            continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 2 and cells[0].isdigit():
                out.append((int(cells[0]), cells[1]))
        elif not re.match(r"^(no|nama)\b", line, re.I):
            out.append((None, line))
    return out


def cmd_import_students(args):
    app = _app()
    with app.app_context():
        conn = dbmod.get_db()
        klass = conn.execute("SELECT * FROM classes ORDER BY id LIMIT 1").fetchone()
        if not klass:
            sys.exit("Kelas belum ada. Jalankan `python manage.py init-db` dahulu.")
        entries = _parse_names(args.file)
        if not entries:
            sys.exit("Tidak ada nama yang terbaca dari berkas.")
        out_path = Path(args.credentials_out or Path("instance") / f"kredensial_siswa_{timeutil.today():%Y%m%d}.csv")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        created, skipped = [], []
        for roll, name in entries:
            sid, temp, errors = stu.create_student(conn, klass["id"], name, roll)
            if errors:
                skipped.append((name, "; ".join(errors.values())))
            else:
                created.append((roll, security.clean_name(name), temp))
        if created:
            fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # hanya pemilik yang bisa baca
            with os.fdopen(fd, "w", newline="", encoding="utf-8-sig") as fh:
                w = csv.writer(fh)
                w.writerow(["No. Absen", "Nama Lengkap", "Kata Sandi Sementara"])
                w.writerows(created)
        print(f"Dibuat: {len(created)} siswa | Dilewati: {len(skipped)}")
        for name, why in skipped:
            print(f"  - {name}: {why}")
        if created:
            print(f"Daftar kata sandi sementara: {out_path}  (bagikan lalu HAPUS berkas ini)")
            print("Siswa wajib mengganti kata sandi saat login pertama.")


def _user(conn, role, name):
    role = security.normalize_role(role)
    if role == "admin":
        row = conn.execute("SELECT * FROM users WHERE role IN ('admin','guru') AND name_key=?", (security.name_key(name),)).fetchone()
    else:
        row = conn.execute("SELECT * FROM users WHERE role='siswa' AND name_key=?", (security.name_key(name),)).fetchone()
    if not row:
        sys.exit("Akun tidak ditemukan.")
    return row


def cmd_reset_password(args):
    app = _app()
    with app.app_context():
        conn = dbmod.get_db()
        role = security.normalize_role(args.role)
        user = _user(conn, role, args.name)
        if role == "siswa":
            temp = stu.reset_password(conn, user["id"])
            print(f"Kata sandi sementara untuk {user['full_name']}: {temp}")
        else:
            password = _read_password(args)
            problem = security.validate_new_password(password, user["full_name"])
            if problem:
                sys.exit(problem)
            conn.execute("UPDATE users SET password_hash=?, must_change_password=0 WHERE id=?",
                         (security.hash_password(password), user["id"]))
            conn.execute("DELETE FROM sessions WHERE user_id=?", (user["id"],))
            conn.commit()
            print("Kata sandi admin diperbarui.")


def cmd_set_active(args):
    app = _app()
    with app.app_context():
        conn = dbmod.get_db()
        user = _user(conn, args.role, args.name)
        conn.execute("UPDATE users SET is_active=? WHERE id=?", (1 if args.on else 0, user["id"]))
        if not args.on:
            conn.execute("DELETE FROM sessions WHERE user_id=?", (user["id"],))
        conn.commit()
        print(f"Akun {user['full_name']} {'diaktifkan' if args.on else 'dinonaktifkan'}.")


def cmd_list_users(args):
    app = _app()
    with app.app_context():
        for r in dbmod.get_db().execute("SELECT role, full_name, is_active FROM users ORDER BY role, full_name"):
            print(f"{r['role']:<6} {'aktif' if r['is_active'] else 'NONAKTIF':<9} {r['full_name']}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db", help="terapkan migrasi dan buat data kelas").set_defaults(fn=cmd_init_db)

    for alias in ("create-admin", "create-teacher"):
        t = sub.add_parser(alias, help="buat akun admin (Ketua Kelas, Sekretaris, atau Wali Kelas)")
        t.add_argument("--name", required=True)
        t.add_argument("--password-stdin", action="store_true", help="baca kata sandi dari stdin (non-interaktif)")
        t.set_defaults(fn=cmd_create_admin)

    i = sub.add_parser("import-students", help="impor daftar siswa dari tabel markdown / satu nama per baris")
    i.add_argument("file")
    i.add_argument("--credentials-out", help="lokasi CSV kata sandi sementara (bawaan: instance/)")
    i.set_defaults(fn=cmd_import_students)

    r = sub.add_parser("reset-password", help="reset kata sandi akun")
    r.add_argument("--role", choices=("siswa", "admin", "guru"), required=True)
    r.add_argument("--name", required=True)
    r.add_argument("--password-stdin", action="store_true")
    r.set_defaults(fn=cmd_reset_password)

    a = sub.add_parser("set-active", help="aktifkan/nonaktifkan akun")
    a.add_argument("--role", choices=("siswa", "admin", "guru"), required=True)
    a.add_argument("--name", required=True)
    g = a.add_mutually_exclusive_group(required=True)
    g.add_argument("--on", action="store_true")
    g.add_argument("--off", action="store_true")
    a.set_defaults(fn=cmd_set_active)

    sub.add_parser("list-users", help="daftar akun").set_defaults(fn=cmd_list_users)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
