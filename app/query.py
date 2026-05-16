from flask import Blueprint, flash, render_template, request

from app.access import get_accessible_genealogy, require_genealogy_access
from app.auth import login_required
from app.db import get_db
from app.member import get_member, parse_int

query_bp = Blueprint("query", __name__, url_prefix="/genealogies/<int:genealogy_id>")


def build_tree(rows):
    nodes = {}
    root = None
    for row in rows:
        node = {
            "id": row[0],
            "name": row[1],
            "gender": row[2],
            "birth_year": row[3],
            "death_year": row[4],
            "generation": row[5],
            "parent_id": row[6],
            "depth": row[7],
            "child_count": row[8] if len(row) > 8 else 0,
            "spouses": (row[9] if len(row) > 9 else []) or [],
            "children": [],
        }
        nodes[node["id"]] = node

    for node in nodes.values():
        parent_id = node["parent_id"]
        if parent_id is None or parent_id not in nodes:
            root = node
        else:
            nodes[parent_id]["children"].append(node)

    for node in nodes.values():
        node["children"].sort(key=lambda item: (item["birth_year"] or 9999, item["id"]))
    return root


def get_default_root(genealogy_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT m.id
            FROM members m
            WHERE m.genealogy_id = %s
              AND NOT EXISTS (
                  SELECT 1 FROM parent_child pc WHERE pc.child_id = m.id
              )
            ORDER BY m.generation, m.birth_year NULLS LAST, m.id
            LIMIT 1
            """,
            (genealogy_id,),
        )
        row = cur.fetchone()
    return row[0] if row else None


@query_bp.route("/tree")
@login_required
def tree(genealogy_id):
    genealogy = get_accessible_genealogy(genealogy_id)
    root_id = parse_int(request.args.get("root_id")) or get_default_root(genealogy_id)
    max_depth = parse_int(request.args.get("max_depth")) or 3
    max_depth = max(1, min(max_depth, 8))
    child_limit = parse_int(request.args.get("child_limit")) or 6
    child_limit = max(1, min(child_limit, 20))
    if root_id is None:
        return render_template(
            "query/tree.html",
            genealogy=genealogy,
            root=None,
            root_id=None,
            max_depth=max_depth,
            child_limit=child_limit,
            node_count=0,
        )

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            WITH RECURSIVE branch AS (
                SELECT
                    m.id,
                    m.name,
                    m.gender,
                    m.birth_year,
                    m.death_year,
                    m.generation,
                    NULL::INT AS parent_id,
                    0 AS depth,
                    ARRAY[m.id] AS path
                FROM members m
                WHERE m.id = %s AND m.genealogy_id = %s

                UNION ALL

                SELECT
                    child.id,
                    child.name,
                    child.gender,
                    child.birth_year,
                    child.death_year,
                    child.generation,
                    child.parent_id,
                    b.depth + 1,
                    b.path || child.id
                FROM branch b
                JOIN LATERAL (
                    SELECT
                        c.id,
                        c.name,
                        c.gender,
                        c.birth_year,
                        c.death_year,
                        c.generation,
                        pc.parent_id
                    FROM parent_child pc
                    JOIN members c ON c.id = pc.child_id
                    WHERE pc.parent_id = b.id
                      AND c.genealogy_id = %s
                      AND NOT c.id = ANY(b.path)
                    ORDER BY c.birth_year NULLS LAST, c.id
                    LIMIT %s
                ) child ON TRUE
                WHERE NOT child.id = ANY(b.path)
                  AND b.depth < %s
            ),
            ranked AS (
                SELECT *,
                       ROW_NUMBER() OVER (PARTITION BY id ORDER BY depth, parent_id NULLS FIRST) AS rn
                FROM branch
            )
            SELECT
                id,
                name,
                gender,
                birth_year,
                death_year,
                generation,
                parent_id,
                depth,
                (
                    SELECT COUNT(*)
                    FROM parent_child pc
                    JOIN members child ON child.id = pc.child_id
                    WHERE pc.parent_id = ranked.id
                      AND child.genealogy_id = %s
                ) AS child_count,
                ARRAY(
                    SELECT spouse.name || ' #' || spouse.id
                    FROM marriages ma
                    JOIN members spouse
                        ON spouse.id = CASE
                            WHEN ma.husband_id = ranked.id THEN ma.wife_id
                            ELSE ma.husband_id
                        END
                    WHERE ma.husband_id = ranked.id OR ma.wife_id = ranked.id
                    ORDER BY ma.start_year NULLS LAST, spouse.id
                ) AS spouses
            FROM ranked
            WHERE rn = 1
            ORDER BY depth, generation, birth_year NULLS LAST, id
            """,
            (root_id, genealogy_id, genealogy_id, child_limit, max_depth, genealogy_id),
        )
        rows = cur.fetchall()

    root = build_tree(rows) if rows else None
    if root is None:
        flash("根成员不存在或无权访问。", "danger")

    return render_template(
        "query/tree.html",
        genealogy=genealogy,
        root=root,
        root_id=root_id,
        max_depth=max_depth,
        child_limit=child_limit,
        node_count=len(rows),
    )


@query_bp.route("/ancestors", methods=("GET", "POST"))
@login_required
def ancestors(genealogy_id):
    genealogy = get_accessible_genealogy(genealogy_id)
    member_id = parse_int(request.values.get("member_id"))
    ancestors_tree = None
    member = get_member(member_id, genealogy_id) if member_id else None

    if member_id and member is None:
        flash("成员不存在或无权访问。", "danger")
    elif member_id:
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                """
                WITH RECURSIVE ancestors AS (
                    SELECT
                        p.id,
                        p.name,
                        p.gender,
                        p.birth_year,
                        p.death_year,
                        p.generation,
                        c.id AS parent_id,
                        1 AS depth,
                        ARRAY[c.id, p.id] AS path
                    FROM members c
                    JOIN parent_child pc ON pc.child_id = c.id
                    JOIN members p ON p.id = pc.parent_id
                    WHERE c.id = %s AND c.genealogy_id = %s

                    UNION ALL

                    SELECT
                        gp.id,
                        gp.name,
                        gp.gender,
                        gp.birth_year,
                        gp.death_year,
                        gp.generation,
                        a.id AS parent_id,
                        a.depth + 1,
                        a.path || gp.id
                    FROM ancestors a
                    JOIN parent_child pc ON pc.child_id = a.id
                    JOIN members gp ON gp.id = pc.parent_id
                    WHERE NOT gp.id = ANY(a.path)
                      AND a.depth < 60
                )
                SELECT
                    id,
                    name,
                    gender,
                    birth_year,
                    death_year,
                    generation,
                    parent_id,
                    depth
                FROM ancestors
                ORDER BY depth, generation DESC, id
                """,
                (member_id, genealogy_id),
            )
            rows = cur.fetchall()

        nodes = [
            {
                "id": member["id"],
                "name": member["name"],
                "gender": member["gender"],
                "birth_year": member["birth_year"],
                "death_year": member["death_year"],
                "generation": member["generation"],
                "parent_id": None,
                "depth": 0,
                "children": [],
            }
        ]
        nodes.extend(rows)
        ancestors_tree = build_tree(
            [
                (
                    node["id"],
                    node["name"],
                    node["gender"],
                    node["birth_year"],
                    node["death_year"],
                    node["generation"],
                    node["parent_id"],
                    node["depth"],
                )
                if isinstance(node, dict)
                else node
                for node in nodes
            ]
        )

    return render_template(
        "query/ancestors.html",
        genealogy=genealogy,
        member_id=member_id,
        member=member,
        root=ancestors_tree,
    )


@query_bp.route("/relationship", methods=("GET", "POST"))
@login_required
def relationship(genealogy_id):
    genealogy = get_accessible_genealogy(genealogy_id)
    member_a_id = parse_int(request.values.get("member_a_id"))
    member_b_id = parse_int(request.values.get("member_b_id"))
    path = None

    if member_a_id and member_b_id:
        member_a = get_member(member_a_id, genealogy_id)
        member_b = get_member(member_b_id, genealogy_id)
        if member_a is None or member_b is None:
            flash("输入的成员不存在或不属于当前族谱。", "danger")
        else:
            db = get_db()
            with db.cursor() as cur:
                cur.execute(
                    """
                    WITH RECURSIVE
                    up_a AS (
                        SELECT
                            m.id,
                            ARRAY[m.id] AS path_ids,
                            ARRAY[m.name] AS path_names,
                            0 AS depth
                        FROM members m
                        WHERE m.id = %s AND m.genealogy_id = %s

                        UNION ALL

                        SELECT
                            parent.id,
                            up_a.path_ids || parent.id,
                            up_a.path_names || parent.name,
                            up_a.depth + 1
                        FROM up_a
                        JOIN parent_child pc ON pc.child_id = up_a.id
                        JOIN members parent ON parent.id = pc.parent_id
                        WHERE parent.genealogy_id = %s
                          AND NOT parent.id = ANY(up_a.path_ids)
                          AND up_a.depth < 60
                    ),
                    up_b AS (
                        SELECT
                            m.id,
                            ARRAY[m.id] AS path_ids,
                            ARRAY[m.name] AS path_names,
                            0 AS depth
                        FROM members m
                        WHERE m.id = %s AND m.genealogy_id = %s

                        UNION ALL

                        SELECT
                            parent.id,
                            up_b.path_ids || parent.id,
                            up_b.path_names || parent.name,
                            up_b.depth + 1
                        FROM up_b
                        JOIN parent_child pc ON pc.child_id = up_b.id
                        JOIN members parent ON parent.id = pc.parent_id
                        WHERE parent.genealogy_id = %s
                          AND NOT parent.id = ANY(up_b.path_ids)
                          AND up_b.depth < 60
                    ),
                    common_ancestor_paths AS (
                        SELECT
                            up_a.path_ids ||
                                COALESCE((
                                    SELECT array_agg(value ORDER BY ord DESC)
                                    FROM unnest(up_b.path_ids) WITH ORDINALITY AS t(value, ord)
                                    WHERE ord < cardinality(up_b.path_ids)
                                ), ARRAY[]::INT[]) AS path_ids,
                            up_a.path_names ||
                                COALESCE((
                                    SELECT array_agg(value ORDER BY ord DESC)
                                    FROM unnest(up_b.path_names) WITH ORDINALITY AS t(value, ord)
                                    WHERE ord < cardinality(up_b.path_names)
                                ), ARRAY[]::VARCHAR[]) AS path_names,
                            up_a.depth + up_b.depth AS depth
                        FROM up_a
                        JOIN up_b ON up_b.id = up_a.id
                    ),
                    spouse_paths AS (
                        SELECT
                            ARRAY[a.id, b.id] AS path_ids,
                            ARRAY[a.name, b.name] AS path_names,
                            1 AS depth
                        FROM members a
                        JOIN members b ON b.id = %s AND b.genealogy_id = %s
                        WHERE a.id = %s
                          AND a.genealogy_id = %s
                          AND EXISTS (
                              SELECT 1
                              FROM marriages ma
                              WHERE (ma.husband_id = a.id AND ma.wife_id = b.id)
                                 OR (ma.husband_id = b.id AND ma.wife_id = a.id)
                          )
                    ),
                    candidate_paths AS (
                        SELECT * FROM common_ancestor_paths
                        UNION ALL
                        SELECT * FROM spouse_paths
                    )
                    SELECT path_ids, array_to_string(path_names, ' -> ') AS name_path, depth
                    FROM candidate_paths
                    ORDER BY depth, cardinality(path_ids)
                    LIMIT 1
                    """,
                    (
                        member_a_id,
                        genealogy_id,
                        genealogy_id,
                        member_b_id,
                        genealogy_id,
                        genealogy_id,
                        member_b_id,
                        genealogy_id,
                        member_a_id,
                        genealogy_id,
                    ),
                )
                row = cur.fetchone()
            if row:
                path = {"ids": row[0], "names": row[1], "depth": row[2]}
            else:
                flash("未查询到亲缘关系通路。", "warning")

    return render_template(
        "query/relationship.html",
        genealogy=genealogy,
        member_a_id=member_a_id,
        member_b_id=member_b_id,
        path=path,
    )


@query_bp.route("/descendants", methods=("GET", "POST"))
@login_required
def descendants(genealogy_id):
    genealogy = get_accessible_genealogy(genealogy_id)
    member_id = parse_int(request.values.get("member_id"))
    rows = []
    if member_id:
        require_genealogy_access(genealogy_id)
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                """
                WITH RECURSIVE descendants AS (
                    SELECT
                        c.id,
                        c.name,
                        c.gender,
                        c.birth_year,
                        c.death_year,
                        c.generation,
                        1 AS depth,
                        ARRAY[p.id, c.id] AS path
                    FROM members p
                    JOIN parent_child pc ON pc.parent_id = p.id
                    JOIN members c ON c.id = pc.child_id
                    WHERE p.id = %s AND p.genealogy_id = %s

                    UNION ALL

                    SELECT
                        c.id,
                        c.name,
                        c.gender,
                        c.birth_year,
                        c.death_year,
                        c.generation,
                        d.depth + 1,
                        d.path || c.id
                    FROM descendants d
                    JOIN parent_child pc ON pc.parent_id = d.id
                    JOIN members c ON c.id = pc.child_id
                    WHERE c.genealogy_id = %s
                      AND NOT c.id = ANY(d.path)
                      AND d.depth < 60
                )
                SELECT DISTINCT ON (id)
                    id,
                    name,
                    gender,
                    birth_year,
                    death_year,
                    generation,
                    depth
                FROM descendants
                ORDER BY id, depth
                """,
                (member_id, genealogy_id, genealogy_id),
            )
            rows = [
                {
                    "id": row[0],
                    "name": row[1],
                    "gender": row[2],
                    "birth_year": row[3],
                    "death_year": row[4],
                    "generation": row[5],
                    "depth": row[6],
                }
                for row in cur.fetchall()
            ]
        rows.sort(key=lambda item: (item["depth"], item["generation"], item["id"]))

    return render_template(
        "query/descendants.html",
        genealogy=genealogy,
        member_id=member_id,
        descendants=rows,
    )
