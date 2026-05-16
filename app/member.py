from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.access import get_accessible_genealogy, require_genealogy_access
from app.auth import login_required
from app.db import get_db

member_bp = Blueprint(
    "member", __name__, url_prefix="/genealogies/<int:genealogy_id>/members"
)


def parse_int(value):
    if value in (None, ""):
        return None
    return int(value)


def get_member(member_id, genealogy_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT id, genealogy_id, name, gender, birth_year, death_year, generation, bio
            FROM members
            WHERE id = %s AND genealogy_id = %s
            """,
            (member_id, genealogy_id),
        )
        row = cur.fetchone()

    if row is None:
        return None
    return {
        "id": row[0],
        "genealogy_id": row[1],
        "name": row[2],
        "gender": row[3],
        "birth_year": row[4],
        "death_year": row[5],
        "generation": row[6],
        "bio": row[7],
    }


@member_bp.route("/")
@login_required
def list_members(genealogy_id):
    genealogy = get_accessible_genealogy(genealogy_id)
    keyword = request.args.get("q", "").strip()
    db = get_db()

    params = [genealogy_id]
    where_sql = "m.genealogy_id = %s"
    if keyword:
        where_sql += " AND m.name ILIKE %s"
        params.append(f"%{keyword}%")

    with db.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                m.id,
                m.name,
                m.gender,
                m.birth_year,
                m.death_year,
                m.generation,
                COUNT(pc.child_id) AS child_count
            FROM members m
            LEFT JOIN parent_child pc ON pc.parent_id = m.id
            WHERE {where_sql}
            GROUP BY m.id
            ORDER BY m.generation, m.birth_year NULLS LAST, m.id
            LIMIT 200
            """,
            params,
        )
        members = [
            {
                "id": row[0],
                "name": row[1],
                "gender": row[2],
                "birth_year": row[3],
                "death_year": row[4],
                "generation": row[5],
                "child_count": row[6],
            }
            for row in cur.fetchall()
        ]

    return render_template(
        "member/list.html",
        genealogy=genealogy,
        members=members,
        keyword=keyword,
    )


@member_bp.route("/new", methods=("GET", "POST"))
@login_required
def create(genealogy_id):
    genealogy = get_accessible_genealogy(genealogy_id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        gender = request.form.get("gender", "")
        birth_year = parse_int(request.form.get("birth_year"))
        death_year = parse_int(request.form.get("death_year"))
        generation = parse_int(request.form.get("generation")) or 1
        bio = request.form.get("bio", "").strip()

        if not name or gender not in ("M", "F"):
            flash("姓名和性别不能为空。", "danger")
        else:
            db = get_db()
            try:
                with db.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO members (
                            genealogy_id, name, gender, birth_year,
                            death_year, generation, bio
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            genealogy_id,
                            name,
                            gender,
                            birth_year,
                            death_year,
                            generation,
                            bio,
                        ),
                    )
                    member_id = cur.fetchone()[0]
                db.commit()
            except Exception as exc:
                db.rollback()
                flash(f"新增成员失败：{exc}", "danger")
            else:
                flash("成员已新增。", "success")
                return redirect(
                    url_for(
                        "member.detail",
                        genealogy_id=genealogy_id,
                        member_id=member_id,
                    )
                )

    return render_template("member/form.html", genealogy=genealogy, member=None)


@member_bp.route("/<int:member_id>")
@login_required
def detail(genealogy_id, member_id):
    genealogy = get_accessible_genealogy(genealogy_id)
    member = get_member(member_id, genealogy_id)
    if member is None:
        flash("成员不存在。", "danger")
        return redirect(url_for("member.list_members", genealogy_id=genealogy_id))

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT p.id, p.name, p.gender, p.birth_year
            FROM parent_child pc
            JOIN members p ON p.id = pc.parent_id
            WHERE pc.child_id = %s
            ORDER BY p.gender, p.id
            """,
            (member_id,),
        )
        parents = [
            {"id": row[0], "name": row[1], "gender": row[2], "birth_year": row[3]}
            for row in cur.fetchall()
        ]

        cur.execute(
            """
            SELECT c.id, c.name, c.gender, c.birth_year
            FROM parent_child pc
            JOIN members c ON c.id = pc.child_id
            WHERE pc.parent_id = %s
            ORDER BY c.birth_year NULLS LAST, c.id
            """,
            (member_id,),
        )
        children = [
            {"id": row[0], "name": row[1], "gender": row[2], "birth_year": row[3]}
            for row in cur.fetchall()
        ]

        cur.execute(
            """
            SELECT
                spouse.id,
                spouse.name,
                spouse.gender,
                ma.start_year,
                ma.end_year
            FROM marriages ma
            JOIN members spouse
                ON spouse.id = CASE
                    WHEN ma.husband_id = %s THEN ma.wife_id
                    ELSE ma.husband_id
                END
            WHERE ma.husband_id = %s OR ma.wife_id = %s
            ORDER BY ma.start_year NULLS LAST, spouse.id
            """,
            (member_id, member_id, member_id),
        )
        spouses = [
            {
                "id": row[0],
                "name": row[1],
                "gender": row[2],
                "start_year": row[3],
                "end_year": row[4],
            }
            for row in cur.fetchall()
        ]

    return render_template(
        "member/detail.html",
        genealogy=genealogy,
        member=member,
        parents=parents,
        children=children,
        spouses=spouses,
    )


@member_bp.route("/<int:member_id>/edit", methods=("GET", "POST"))
@login_required
def edit(genealogy_id, member_id):
    genealogy = get_accessible_genealogy(genealogy_id)
    member = get_member(member_id, genealogy_id)
    if member is None:
        flash("成员不存在。", "danger")
        return redirect(url_for("member.list_members", genealogy_id=genealogy_id))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        gender = request.form.get("gender", "")
        birth_year = parse_int(request.form.get("birth_year"))
        death_year = parse_int(request.form.get("death_year"))
        generation = parse_int(request.form.get("generation")) or 1
        bio = request.form.get("bio", "").strip()

        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute(
                    """
                    UPDATE members
                    SET name = %s,
                        gender = %s,
                        birth_year = %s,
                        death_year = %s,
                        generation = %s,
                        bio = %s
                    WHERE id = %s AND genealogy_id = %s
                    """,
                    (
                        name,
                        gender,
                        birth_year,
                        death_year,
                        generation,
                        bio,
                        member_id,
                        genealogy_id,
                    ),
                )
            db.commit()
        except Exception as exc:
            db.rollback()
            flash(f"保存成员失败：{exc}", "danger")
        else:
            flash("成员已保存。", "success")
            return redirect(
                url_for(
                    "member.detail",
                    genealogy_id=genealogy_id,
                    member_id=member_id,
                )
            )

    return render_template("member/form.html", genealogy=genealogy, member=member)


@member_bp.route("/<int:member_id>/delete", methods=("POST",))
@login_required
def delete(genealogy_id, member_id):
    require_genealogy_access(genealogy_id)
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "DELETE FROM members WHERE id = %s AND genealogy_id = %s",
                (member_id, genealogy_id),
            )
        db.commit()
        flash("成员已删除。", "success")
    except Exception:
        db.rollback()
        flash("删除成员失败。", "danger")

    return redirect(url_for("member.list_members", genealogy_id=genealogy_id))


@member_bp.route("/<int:member_id>/parents", methods=("POST",))
@login_required
def add_parent(genealogy_id, member_id):
    require_genealogy_access(genealogy_id)
    parent_id = parse_int(request.form.get("parent_id"))
    if parent_id is None:
        flash("请输入父母成员 ID。", "danger")
        return redirect(
            url_for("member.detail", genealogy_id=genealogy_id, member_id=member_id)
        )

    if get_member(parent_id, genealogy_id) is None or get_member(member_id, genealogy_id) is None:
        flash("父母成员或当前成员不存在。", "danger")
        return redirect(
            url_for("member.detail", genealogy_id=genealogy_id, member_id=member_id)
        )

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO parent_child (parent_id, child_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (parent_id, member_id),
            )
        db.commit()
        flash("亲子关系已保存。", "success")
    except Exception as exc:
        db.rollback()
        flash(f"保存亲子关系失败：{exc}", "danger")

    return redirect(url_for("member.detail", genealogy_id=genealogy_id, member_id=member_id))


@member_bp.route("/<int:member_id>/children", methods=("POST",))
@login_required
def add_child(genealogy_id, member_id):
    require_genealogy_access(genealogy_id)
    child_id = parse_int(request.form.get("child_id"))
    if child_id is None:
        flash("请输入子女成员 ID。", "danger")
        return redirect(
            url_for("member.detail", genealogy_id=genealogy_id, member_id=member_id)
        )

    if get_member(child_id, genealogy_id) is None or get_member(member_id, genealogy_id) is None:
        flash("子女成员或当前成员不存在。", "danger")
        return redirect(
            url_for("member.detail", genealogy_id=genealogy_id, member_id=member_id)
        )

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO parent_child (parent_id, child_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (member_id, child_id),
            )
        db.commit()
        flash("亲子关系已保存。", "success")
    except Exception as exc:
        db.rollback()
        flash(f"保存亲子关系失败：{exc}", "danger")

    return redirect(url_for("member.detail", genealogy_id=genealogy_id, member_id=member_id))


@member_bp.route("/<int:member_id>/spouses", methods=("POST",))
@login_required
def add_spouse(genealogy_id, member_id):
    require_genealogy_access(genealogy_id)
    spouse_id = parse_int(request.form.get("spouse_id"))
    start_year = parse_int(request.form.get("start_year"))
    end_year = parse_int(request.form.get("end_year"))
    member = get_member(member_id, genealogy_id)
    spouse = get_member(spouse_id, genealogy_id) if spouse_id else None

    if member is None or spouse is None:
        flash("成员或配偶不存在。", "danger")
        return redirect(
            url_for("member.detail", genealogy_id=genealogy_id, member_id=member_id)
        )

    if member["gender"] == "M" and spouse["gender"] == "F":
        husband_id, wife_id = member_id, spouse_id
    elif member["gender"] == "F" and spouse["gender"] == "M":
        husband_id, wife_id = spouse_id, member_id
    else:
        flash("婚姻关系需要一名男性成员和一名女性成员。", "danger")
        return redirect(
            url_for("member.detail", genealogy_id=genealogy_id, member_id=member_id)
        )

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO marriages (husband_id, wife_id, start_year, end_year)
                VALUES (%s, %s, %s, %s)
                """,
                (husband_id, wife_id, start_year, end_year),
            )
        db.commit()
        flash("婚姻关系已保存。", "success")
    except Exception as exc:
        db.rollback()
        flash(f"保存婚姻关系失败：{exc}", "danger")

    return redirect(url_for("member.detail", genealogy_id=genealogy_id, member_id=member_id))
