import argparse
import csv
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import Config


TABLES = [
    ("users", ["id", "username", "password_hash", "created_at"]),
    ("genealogies", ["id", "name", "surname", "compiled_at", "creator_id", "created_at"]),
    ("genealogy_users", ["genealogy_id", "user_id", "role", "created_at"]),
    (
        "members",
        [
            "id",
            "genealogy_id",
            "name",
            "gender",
            "birth_year",
            "death_year",
            "generation",
            "bio",
            "created_at",
        ],
    ),
    ("parent_child", ["parent_id", "child_id"]),
    ("marriages", ["id", "husband_id", "wife_id", "start_year", "end_year"]),
]

SEQUENCES = [
    ("users_id_seq", "users"),
    ("genealogies_id_seq", "genealogies"),
    ("members_id_seq", "members"),
    ("marriages_id_seq", "marriages"),
]


def copy_table(cursor, input_dir, table_name, columns):
    csv_path = input_dir / f"{table_name}.csv"
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader)
        cursor.copy_expert(
            sql.SQL(
                """
                COPY {} ({})
                FROM STDIN WITH (FORMAT CSV, NULL '', DELIMITER ',', QUOTE '"')
                """
            ).format(
                sql.Identifier(table_name),
                sql.SQL(", ").join(sql.Identifier(column) for column in columns),
            ).as_string(cursor),
            f,
        )


def import_csv(input_dir, truncate):
    load_dotenv()
    conn = psycopg2.connect(**Config.DB_PARAMS)
    try:
        with conn:
            with conn.cursor() as cur:
                if truncate:
                    cur.execute(
                        """
                        TRUNCATE TABLE
                            marriages,
                            parent_child,
                            members,
                            genealogy_users,
                            genealogies,
                            users
                        RESTART IDENTITY CASCADE
                        """
                    )

                cur.execute(
                    "ALTER TABLE genealogies DISABLE TRIGGER trg_add_genealogy_owner"
                )
                try:
                    for table_name, columns in TABLES:
                        copy_table(cur, input_dir, table_name, columns)
                finally:
                    cur.execute(
                        "ALTER TABLE genealogies ENABLE TRIGGER trg_add_genealogy_owner"
                    )

                for sequence_name, table_name in SEQUENCES:
                    cur.execute(
                        sql.SQL(
                            "SELECT setval(%s::regclass, "
                            "COALESCE((SELECT MAX(id) FROM {}), 1))"
                        ).format(sql.Identifier(table_name)).as_string(cur),
                        (sequence_name,),
                    )

        print(f"Imported CSV files from {input_dir}.")
    finally:
        conn.close()


def parse_args():
    parser = argparse.ArgumentParser(description="Import generated CSV files with COPY.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "output",
    )
    parser.add_argument("--truncate", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    import_csv(args.input_dir, args.truncate)
