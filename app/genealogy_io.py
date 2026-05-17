import csv
from io import StringIO

from psycopg2.extras import execute_values


CSV_COLUMNS = [
    "record_type",
    "legacy_id",
    "name",
    "surname",
    "compiled_at",
    "gender",
    "birth_year",
    "death_year",
    "generation",
    "bio",
    "parent_legacy_id",
    "child_legacy_id",
    "husband_legacy_id",
    "wife_legacy_id",
    "start_year",
    "end_year",
]


def blank_row(record_type):
    row = {column: "" for column in CSV_COLUMNS}
    row["record_type"] = record_type
    return row


def clean_text(value):
    value = (value or "").strip()
    return value or None


def parse_int(value, field_name):
    value = clean_text(value)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} 必须是整数。") from exc


def read_genealogy_csv(file_storage):
    content = file_storage.read().decode("utf-8-sig")
    reader = csv.DictReader(StringIO(content))
    if reader.fieldnames is None:
        raise ValueError("CSV 文件不能为空。")

    missing_columns = [column for column in CSV_COLUMNS if column not in reader.fieldnames]
    if missing_columns:
        raise ValueError(f"CSV 文件缺少列：{', '.join(missing_columns)}。")

    genealogy_rows = []
    member_rows = []
    parent_child_rows = []
    marriage_rows = []

    for line_number, row in enumerate(reader, start=2):
        record_type = clean_text(row.get("record_type"))
        if record_type == "genealogy":
            genealogy_rows.append(row)
        elif record_type == "member":
            member_rows.append(row)
        elif record_type == "parent_child":
            parent_child_rows.append(row)
        elif record_type == "marriage":
            marriage_rows.append(row)
        elif record_type is not None:
            raise ValueError(f"第 {line_number} 行的 record_type 无效。")

    if len(genealogy_rows) != 1:
        raise ValueError("CSV 文件必须包含且只包含一行 genealogy 记录。")
    if not member_rows:
        raise ValueError("CSV 文件至少需要包含一行 member 记录。")

    return genealogy_rows[0], member_rows, parent_child_rows, marriage_rows


def import_genealogy_csv(db, file_storage, creator_id):
    genealogy_row, member_rows, parent_child_rows, marriage_rows = read_genealogy_csv(
        file_storage
    )
    name = clean_text(genealogy_row.get("name"))
    surname = clean_text(genealogy_row.get("surname"))
    compiled_at = clean_text(genealogy_row.get("compiled_at"))
    if not name or not surname:
        raise ValueError("genealogy 记录必须包含 name 和 surname。")

    member_values = []
    seen_legacy_ids = set()
    for row in member_rows:
        legacy_id = parse_int(row.get("legacy_id"), "legacy_id")
        if legacy_id is None:
            raise ValueError("member 记录必须包含 legacy_id。")
        if legacy_id in seen_legacy_ids:
            raise ValueError(f"member legacy_id={legacy_id} 重复。")
        seen_legacy_ids.add(legacy_id)

        gender = clean_text(row.get("gender"))
        if gender not in ("M", "F"):
            raise ValueError(f"member legacy_id={legacy_id} 的 gender 必须为 M 或 F。")

        member_values.append(
            (
                legacy_id,
                clean_text(row.get("name")),
                gender,
                parse_int(row.get("birth_year"), "birth_year"),
                parse_int(row.get("death_year"), "death_year"),
                parse_int(row.get("generation"), "generation") or 1,
                clean_text(row.get("bio")),
            )
        )

    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO genealogies (name, surname, compiled_at, creator_id)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (name, surname, compiled_at, creator_id),
        )
        genealogy_id = cur.fetchone()[0]

        sorted_member_values = sorted(member_values, key=lambda item: item[0])
        execute_values(
            cur,
            """
            INSERT INTO members (
                genealogy_id, name, gender, birth_year, death_year, generation, bio
            )
            VALUES %s
            """,
            [
                (
                    genealogy_id,
                    name,
                    gender,
                    birth_year,
                    death_year,
                    generation,
                    bio,
                )
                for (
                    _legacy_id,
                    name,
                    gender,
                    birth_year,
                    death_year,
                    generation,
                    bio,
                ) in sorted_member_values
            ],
        )

        cur.execute(
            """
            SELECT id
            FROM members
            WHERE genealogy_id = %s
            ORDER BY id
            """,
            (genealogy_id,),
        )
        new_member_ids = [row[0] for row in cur.fetchall()]

        legacy_ids = [row[0] for row in sorted_member_values]
        member_id_map = dict(zip(legacy_ids, new_member_ids))

        parent_child_values = []
        for row in parent_child_rows:
            parent_legacy_id = parse_int(row.get("parent_legacy_id"), "parent_legacy_id")
            child_legacy_id = parse_int(row.get("child_legacy_id"), "child_legacy_id")
            try:
                parent_child_values.append(
                    (member_id_map[parent_legacy_id], member_id_map[child_legacy_id])
                )
            except KeyError as exc:
                raise ValueError("parent_child 记录引用了不存在的 member。") from exc

        if parent_child_values:
            execute_values(
                cur,
                """
                INSERT INTO parent_child (parent_id, child_id)
                VALUES %s
                ON CONFLICT DO NOTHING
                """,
                parent_child_values,
            )

        marriage_values = []
        for row in marriage_rows:
            husband_legacy_id = parse_int(row.get("husband_legacy_id"), "husband_legacy_id")
            wife_legacy_id = parse_int(row.get("wife_legacy_id"), "wife_legacy_id")
            try:
                marriage_values.append(
                    (
                        member_id_map[husband_legacy_id],
                        member_id_map[wife_legacy_id],
                        parse_int(row.get("start_year"), "start_year"),
                        parse_int(row.get("end_year"), "end_year"),
                    )
                )
            except KeyError as exc:
                raise ValueError("marriage 记录引用了不存在的 member。") from exc

        if marriage_values:
            execute_values(
                cur,
                """
                INSERT INTO marriages (husband_id, wife_id, start_year, end_year)
                VALUES %s
                """,
                marriage_values,
            )

    return genealogy_id


def export_genealogy_csv(db, genealogy_id):
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
    writer.writeheader()

    with db.cursor() as cur:
        cur.execute(
            """
            SELECT name, surname, compiled_at
            FROM genealogies
            WHERE id = %s
            """,
            (genealogy_id,),
        )
        genealogy = cur.fetchone()

        row = blank_row("genealogy")
        row["name"] = genealogy[0]
        row["surname"] = genealogy[1]
        row["compiled_at"] = genealogy[2] or ""
        writer.writerow(row)

        cur.execute(
            """
            SELECT id, name, gender, birth_year, death_year, generation, bio
            FROM members
            WHERE genealogy_id = %s
            ORDER BY id
            """,
            (genealogy_id,),
        )
        for member in cur.fetchall():
            row = blank_row("member")
            row["legacy_id"] = member[0]
            row["name"] = member[1]
            row["gender"] = member[2]
            row["birth_year"] = member[3] or ""
            row["death_year"] = member[4] or ""
            row["generation"] = member[5]
            row["bio"] = member[6] or ""
            writer.writerow(row)

        cur.execute(
            """
            SELECT pc.parent_id, pc.child_id
            FROM parent_child pc
            JOIN members parent ON parent.id = pc.parent_id
            JOIN members child ON child.id = pc.child_id
            WHERE parent.genealogy_id = %s
              AND child.genealogy_id = %s
            ORDER BY pc.parent_id, pc.child_id
            """,
            (genealogy_id, genealogy_id),
        )
        for parent_id, child_id in cur.fetchall():
            row = blank_row("parent_child")
            row["parent_legacy_id"] = parent_id
            row["child_legacy_id"] = child_id
            writer.writerow(row)

        cur.execute(
            """
            SELECT ma.husband_id, ma.wife_id, ma.start_year, ma.end_year
            FROM marriages ma
            JOIN members husband ON husband.id = ma.husband_id
            JOIN members wife ON wife.id = ma.wife_id
            WHERE husband.genealogy_id = %s
              AND wife.genealogy_id = %s
            ORDER BY ma.husband_id, ma.wife_id, ma.start_year NULLS LAST
            """,
            (genealogy_id, genealogy_id),
        )
        for husband_id, wife_id, start_year, end_year in cur.fetchall():
            row = blank_row("marriage")
            row["husband_legacy_id"] = husband_id
            row["wife_legacy_id"] = wife_id
            row["start_year"] = start_year or ""
            row["end_year"] = end_year or ""
            writer.writerow(row)

    return output.getvalue()
