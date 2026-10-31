"""Portal siswa. Setiap query memakai g.user['id']; siswa tidak pernah bisa melihat data siswa lain."""
from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from .. import security, timeutil
from ..db import get_db
from ..services import attendance as att
from ..services import settings as settings_svc

bp = Blueprint("student", __name__, url_prefix="/siswa")


def _profile(db):
    return db.execute("SELECT s.roll_no, s.nis FROM students s WHERE s.user_id = ?", (g.user["id"],)).fetchone()


@bp.get("/")
@security.login_required("siswa")
def dashboard():
    db = get_db()
    now = timeutil.now()
    settings = settings_svc.load(db)
    return render_template(
        "siswa/dashboard.html", profile=_profile(db), today=now.date(),
        record=att.get_record(db, g.user["id"], now.date()),
        window=settings_svc.window_state(settings, now),
        summary=att.student_month_summary(db, g.user["id"], now.year, now.month),
        recent=att.student_history(db, g.user["id"], limit=7))


@bp.route("/presensi", methods=["GET", "POST"])
@security.login_required("siswa")
def presensi():
    db = get_db()
    now = timeutil.now()
    settings = settings_svc.load(db)
    record = att.get_record(db, g.user["id"], now.date())
    if record:
        return redirect(url_for("student.dashboard"))
    window = settings_svc.window_state(settings, now)
    fence = settings_svc.geofence(settings)

    if request.method == "POST":
        ok, code, message = att.submit_student_attendance(
            db, g.user["id"], request.form.get("status"), request.form.get("note"),
            request.form.get("lat"), request.form.get("lng"), settings, now)
        if ok:
            flash("Presensi berhasil dicatat.", "success")
            return redirect(url_for("student.dashboard"))
        if code == "duplicate":
            flash(message, "info")
            return redirect(url_for("student.dashboard"))
        return render_template("siswa/presensi.html", window=window, geo=bool(fence), today=now.date(),
                               error=message, error_code=code,
                               form={"status": request.form.get("status", ""), "note": request.form.get("note", "")}), 422
    return render_template("siswa/presensi.html", window=window, geo=bool(fence), today=now.date(),
                           error=None, error_code=None, form={"status": "", "note": ""})


@bp.get("/riwayat")
@security.login_required("siswa")
def riwayat():
    db = get_db()
    today = timeutil.today()
    year, month = timeutil.parse_month_arg(request.args.get("bulan"), today)
    start, end = timeutil.month_range(year, month)
    py, pm = timeutil.shift_month(year, month, -1)
    ny, nm = timeutil.shift_month(year, month, 1)
    return render_template(
        "siswa/riwayat.html", year=year, month=month, label=timeutil.month_label(year, month),
        history=att.student_history(db, g.user["id"], start, end),
        summary=att.student_month_summary(db, g.user["id"], year, month),
        prev=f"{py}-{pm:02d}", next=None if (ny, nm) > (today.year, today.month) else f"{ny}-{nm:02d}")
