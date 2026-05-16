import argparse
import csv
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import Config


BRANCH_QUERY = """
WITH RECURSIVE branch AS (
    SELECT
        m.id,
        m.genealogy_id,
        m.name,
        m.gender,
        m.birth_year,
        m.death_year,
        m.generation,
        m.bio,
        0 AS depth,
        ARRAY[m.id] AS path
    FROM members m
    WHERE m.id = %s

    UNION ALL

    SELECT
        child.id,
        child.genealogy_id,
        child.name,
        child.gender,
        child.birth_year,
        child.death_year,
        child.generation,
        child.bio,
        branch.depth + 1,
        branch.path || child.id
    FROM branch
    JOIN parent_child pc ON pc.parent_id = branch.id
    JOIN members child ON child.id = pc.child_id
    WHERE NOT child.id = ANY(branch.path)
)
SELECT
    id,
    genealogy_id,
    name,
    gender,
    birth_year,
    death_year,
    generation,
    bio,
    depth
FROM branch
ORDER BY depth, generation, id
"""


def export_branch(root_member_id, output_path):
    load_dotenv()
    conn = psycopg2.connect(**Config.DB_PARAMS)
    try:
        with conn.cursor() as cur:
            cur.execute(BRANCH_QUERY, (root_member_id,))
            rows = cur.fetchall()
            fieldnames = [desc[0] for desc in cur.description]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(fieldnames)
            writer.writerows(rows)

        print(f"Exported {len(rows)} branch members to {output_path}.")
    finally:
        conn.close()


def parse_args():
    parser = argparse.ArgumentParser(description="Export one descendant branch as CSV.")
    parser.add_argument("root_member_id", type=int)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "output" / "branch_backup.csv",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    export_branch(args.root_member_id, args.output)
