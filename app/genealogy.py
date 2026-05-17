from flask import (
    Blueprint,
    Response,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from app.access import get_accessible_genealogy, require_genealogy_access
from app.auth import login_required
from app.db import get_db
from app.genealogy_io import export_genealogy_csv, import_genealogy_csv

genealogy_bp = Blueprint("genealogy", __name__, url_prefix="/genealogies")


@genealogy_bp.route("/new", methods=("GET", "POST"))
@login_required
def create():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        surname = request.form.get("surname", "").strip()
        compiled_at = request.form.get("compiled_at") or None

        if not name or not surname:
            flash("谱名和姓氏不能为空。", "danger")
        else:
            db = get_db()
            try:
                with db.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO genealogies (name, surname, compiled_at, creator_id)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                        """,
                        (name, surname, compiled_at, g.user["id"]),
                    )
                    genealogy_id = cur.fetchone()[0]
                db.commit()
            except Exception:
                db.rollback()
                flash("创建族谱失败。", "danger")
            else:
                flash("族谱已创建。", "success")
                return redirect(url_for("genealogy.detail", genealogy_id=genealogy_id))

    return render_template("genealogy/form.html", genealogy=None)


@genealogy_bp.route("/import", methods=("POST",))
@login_required
def import_csv():
    upload = request.files.get("csv_file")
    if upload is None or not upload.filename:
        flash("请选择需要导入的 CSV 文件。", "danger")
        return redirect(url_for("routes.dashboard"))

    db = get_db()
    try:
        genealogy_id = import_genealogy_csv(db, upload, g.user["id"])
        db.commit()
    except Exception as exc:
        db.rollback()
        flash(f"导入族谱失败：{exc}", "danger")
        return redirect(url_for("routes.dashboard"))

    flash("族谱已导入。", "success")
    return redirect(url_for("genealogy.detail", genealogy_id=genealogy_id))


@genealogy_bp.route("/<int:genealogy_id>")
@login_required
def detail(genealogy_id):
    genealogy = get_accessible_genealogy(genealogy_id)
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*) AS total_count,
                COALESCE(SUM(CASE WHEN gender = 'M' THEN 1 ELSE 0 END), 0) AS male_count,
                COALESCE(SUM(CASE WHEN gender = 'F' THEN 1 ELSE 0 END), 0) AS female_count,
                COALESCE(MAX(generation), 0) AS max_generation
            FROM members
            WHERE genealogy_id = %s
            """,
            (genealogy_id,),
        )
        stats_row = cur.fetchone()

        cur.execute(
            """
            SELECT id, username, role
            FROM genealogy_users gu
            JOIN users u ON u.id = gu.user_id
            WHERE gu.genealogy_id = %s
            ORDER BY gu.role DESC, u.id
            """,
            (genealogy_id,),
        )
        collaborators = [
            {"id": row[0], "username": row[1], "role": row[2]}
            for row in cur.fetchall()
        ]

    stats = {
        "total_count": stats_row[0],
        "male_count": stats_row[1],
        "female_count": stats_row[2],
        "max_generation": stats_row[3],
    }
    return render_template(
        "genealogy/detail.html",
        genealogy=genealogy,
        stats=stats,
        collaborators=collaborators,
    )


@genealogy_bp.route("/<int:genealogy_id>/export")
@login_required
def export_csv(genealogy_id):
    genealogy = get_accessible_genealogy(genealogy_id)
    db = get_db()
    content = export_genealogy_csv(db, genealogy_id)
    filename = f"genealogy_{genealogy_id}.csv"
    return Response(
        content,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )


@genealogy_bp.route("/<int:genealogy_id>/edit", methods=("GET", "POST"))
@login_required
def edit(genealogy_id):
    genealogy = get_accessible_genealogy(genealogy_id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        surname = request.form.get("surname", "").strip()
        compiled_at = request.form.get("compiled_at") or None

        if not name or not surname:
            flash("谱名和姓氏不能为空。", "danger")
        else:
            db = get_db()
            try:
                with db.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE genealogies
                        SET name = %s, surname = %s, compiled_at = %s
                        WHERE id = %s
                        """,
                        (name, surname, compiled_at, genealogy_id),
                    )
                db.commit()
            except Exception:
                db.rollback()
                flash("保存族谱失败。", "danger")
            else:
                flash("族谱已保存。", "success")
                return redirect(url_for("genealogy.detail", genealogy_id=genealogy_id))

    return render_template("genealogy/form.html", genealogy=genealogy)


@genealogy_bp.route("/<int:genealogy_id>/delete", methods=("POST",))
@login_required
def delete(genealogy_id):
    genealogy = get_accessible_genealogy(genealogy_id)
    if genealogy["creator_id"] != g.user["id"]:
        flash("只有创建者可以删除族谱。", "danger")
        return redirect(url_for("genealogy.detail", genealogy_id=genealogy_id))

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM genealogies WHERE id = %s", (genealogy_id,))
        db.commit()
        flash("族谱已删除。", "success")
    except Exception:
        db.rollback()
        flash("删除族谱失败。", "danger")

    return redirect(url_for("routes.dashboard"))


@genealogy_bp.route("/<int:genealogy_id>/invite", methods=("POST",))
@login_required
def invite(genealogy_id):
    genealogy = get_accessible_genealogy(genealogy_id)
    username = request.form.get("username", "").strip()
    if not username:
        flash("请输入用户名。", "danger")
        return redirect(url_for("genealogy.detail", genealogy_id=genealogy_id))

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            row = cur.fetchone()
            if row is None:
                flash("用户不存在。", "danger")
                return redirect(url_for("genealogy.detail", genealogy_id=genealogy_id))

            cur.execute(
                """
                INSERT INTO genealogy_users (genealogy_id, user_id, role)
                VALUES (%s, %s, 'collaborator')
                ON CONFLICT (genealogy_id, user_id) DO NOTHING
                """,
                (genealogy_id, row[0]),
            )
        db.commit()
        flash(f"已邀请 {username} 参与《{genealogy['name']}》。", "success")
    except Exception:
        db.rollback()
        flash("邀请失败。", "danger")

    return redirect(url_for("genealogy.detail", genealogy_id=genealogy_id))
