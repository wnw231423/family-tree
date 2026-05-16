from functools import wraps

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from app.db import get_db

auth_bp = Blueprint("auth", __name__)


@auth_bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
        return

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, username, created_at FROM users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()

    if row is None:
        session.clear()
        g.user = None
    else:
        g.user = {"id": row[0], "username": row[1], "created_at": row[2]}


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.path))
        return view(**kwargs)

    return wrapped_view


@auth_bp.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username:
            flash("请输入用户名。", "danger")
        elif not password:
            flash("请输入密码。", "danger")
        else:
            db = get_db()
            try:
                with db.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO users (username, password_hash)
                        VALUES (%s, %s)
                        RETURNING id
                        """,
                        (username, generate_password_hash(password)),
                    )
                    user_id = cur.fetchone()[0]
                db.commit()
            except Exception:
                db.rollback()
                flash("用户名已存在或注册失败。", "danger")
            else:
                session.clear()
                session["user_id"] = user_id
                flash("注册成功。", "success")
                return redirect(url_for("routes.dashboard"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()

        with db.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash FROM users WHERE username = %s",
                (username,),
            )
            row = cur.fetchone()

        if row is None or not check_password_hash(row[2], password):
            flash("用户名或密码不正确。", "danger")
        else:
            session.clear()
            session["user_id"] = row[0]
            flash("登录成功。", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("routes.dashboard"))

    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=("POST",))
def logout():
    session.clear()
    flash("已退出登录。", "success")
    return redirect(url_for("auth.login"))
