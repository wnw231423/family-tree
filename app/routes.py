from flask import Blueprint, g, redirect, render_template, url_for

from app.auth import login_required
from app.db import get_db

routes_bp = Blueprint("routes", __name__)


@routes_bp.route("/")
def index():
    return redirect(url_for("routes.dashboard"))


@routes_bp.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT
                g.id,
                g.name,
                g.surname,
                g.compiled_at,
                COUNT(m.id) AS member_count,
                COALESCE(SUM(CASE WHEN m.gender = 'M' THEN 1 ELSE 0 END), 0) AS male_count,
                COALESCE(SUM(CASE WHEN m.gender = 'F' THEN 1 ELSE 0 END), 0) AS female_count
            FROM genealogies g
            JOIN genealogy_users gu ON gu.genealogy_id = g.id
            LEFT JOIN members m ON m.genealogy_id = g.id
            WHERE gu.user_id = %s
            GROUP BY g.id, g.name, g.surname, g.compiled_at
            ORDER BY g.id
            """,
            (g.user["id"],),
        )
        genealogies = [
            {
                "id": row[0],
                "name": row[1],
                "surname": row[2],
                "compiled_at": row[3],
                "member_count": row[4],
                "male_count": row[5],
                "female_count": row[6],
            }
            for row in cur.fetchall()
        ]

    return render_template("dashboard.html", genealogies=genealogies)
