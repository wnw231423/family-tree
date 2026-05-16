from flask import abort, g

from app.db import get_db


def can_access_genealogy(genealogy_id, user_id=None):
    if user_id is None:
        user_id = g.user["id"] if g.get("user") else None
    if user_id is None:
        return False

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM genealogy_users
                WHERE genealogy_id = %s AND user_id = %s
            )
            """,
            (genealogy_id, user_id),
        )
        return cur.fetchone()[0]


def require_genealogy_access(genealogy_id):
    if not can_access_genealogy(genealogy_id):
        abort(404)


def get_accessible_genealogy(genealogy_id):
    require_genealogy_access(genealogy_id)
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, surname, compiled_at, creator_id
            FROM genealogies
            WHERE id = %s
            """,
            (genealogy_id,),
        )
        row = cur.fetchone()
    if row is None:
        abort(404)
    return {
        "id": row[0],
        "name": row[1],
        "surname": row[2],
        "compiled_at": row[3],
        "creator_id": row[4],
    }
