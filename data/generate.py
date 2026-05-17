import argparse
import csv
import random
from pathlib import Path

from faker import Faker


OUTPUT_DIR = Path(__file__).resolve().parent / "output"
DEFAULT_GENEALOGY_SIZES = [50000, 7000, 6500, 6200, 6000, 5800, 5600, 5400, 5200, 4300]
FAMILY_SURNAMES = ["李", "王", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴"]
OUTSIDE_SURNAMES = [
    "孙", "朱", "胡", "林", "郭", "何", "高", "罗", "郑", "梁", "谢", "宋"
]
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


def write_genealogy_csv(output_dir, genealogy, members, parent_child, marriages):
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"genealogy_{genealogy['id']}.csv"
    member_ids = {member["id"] for member in members}

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        row = blank_row("genealogy")
        row["name"] = genealogy["name"]
        row["surname"] = genealogy["surname"]
        row["compiled_at"] = genealogy["compiled_at"]
        writer.writerow(row)

        for member in members:
            row = blank_row("member")
            row["legacy_id"] = member["id"]
            row["name"] = member["name"]
            row["gender"] = member["gender"]
            row["birth_year"] = member["birth_year"]
            row["death_year"] = member["death_year"]
            row["generation"] = member["generation"]
            row["bio"] = member["bio"]
            writer.writerow(row)

        for relation in parent_child:
            if (
                relation["parent_id"] in member_ids
                and relation["child_id"] in member_ids
            ):
                row = blank_row("parent_child")
                row["parent_legacy_id"] = relation["parent_id"]
                row["child_legacy_id"] = relation["child_id"]
                writer.writerow(row)

        for marriage in marriages:
            if (
                marriage["husband_id"] in member_ids
                and marriage["wife_id"] in member_ids
            ):
                row = blank_row("marriage")
                row["husband_legacy_id"] = marriage["husband_id"]
                row["wife_legacy_id"] = marriage["wife_id"]
                row["start_year"] = marriage["start_year"]
                row["end_year"] = marriage["end_year"]
                writer.writerow(row)

    return path


def choose_spouse_surname(family_surname):
    choices = [surname for surname in OUTSIDE_SURNAMES if surname != family_surname]
    return random.choice(choices)


def make_name(fake, surname, gender):
    if gender == "M":
        return surname + fake.first_name_male()
    return surname + fake.first_name_female()


def child_count():
    counts = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    weights = [4, 8, 10, 9, 7, 5, 3, 2, 1]
    return random.choices(counts, weights=weights, k=1)[0]


def life_span(birth_year):
    if birth_year >= 1975:
        return ""
    return birth_year + random.randint(50, 92)


def choose_value(values, index, default_value):
    if values and index < len(values):
        return values[index]
    return default_value


def generate_dataset(
    output_dir,
    sizes,
    generation_count,
    seed,
    surnames=None,
    genealogy_names=None,
    compiled_dates=None,
):
    fake = Faker("zh_CN")
    Faker.seed(seed)
    random.seed(seed)

    genealogies = []
    members = []
    parent_child = []
    marriages = []

    genealogy_id = 1
    member_id = 1
    marriage_id = 1

    def add_member(gid, surname, gender, generation, birth_year, bio):
        nonlocal member_id
        row = {
            "id": member_id,
            "genealogy_id": gid,
            "name": make_name(fake, surname, gender),
            "gender": gender,
            "birth_year": birth_year,
            "death_year": life_span(birth_year),
            "generation": generation,
            "bio": bio,
            "created_at": "2026-05-15 00:00:00",
        }
        members.append(row)
        member_id += 1
        return row["id"]

    def add_marriage(husband_id, wife_id, start_year):
        nonlocal marriage_id
        marriages.append(
            {
                "id": marriage_id,
                "husband_id": husband_id,
                "wife_id": wife_id,
                "start_year": start_year,
                "end_year": "",
            }
        )
        marriage_id += 1

    for index, target_size in enumerate(sizes):
        default_surname = FAMILY_SURNAMES[index % len(FAMILY_SURNAMES)]
        family_surname = choose_value(surnames, index, default_surname)
        default_name = f"{family_surname}氏族谱"
        genealogy_name = choose_value(genealogy_names, index, default_name)
        compiled_at = choose_value(
            compiled_dates,
            index,
            f"2026-{(index % 12) + 1:02d}-01",
        )
        genealogies.append(
            {
                "id": genealogy_id,
                "name": genealogy_name,
                "surname": family_surname,
                "compiled_at": compiled_at,
            }
        )

        genealogy_start_count = len(members)
        founder_birth_year = 1100 + index * 3
        founder_id = add_member(
            genealogy_id,
            family_surname,
            "M",
            1,
            founder_birth_year,
            f"{family_surname}氏第1代本族成员",
        )
        founder_wife_id = add_member(
            genealogy_id,
            choose_spouse_surname(family_surname),
            "F",
            1,
            founder_birth_year + random.randint(-3, 3),
            f"{family_surname}氏第1代配偶",
        )
        add_marriage(founder_id, founder_wife_id, founder_birth_year + 22)

        active_couples = [(founder_id, founder_wife_id)]

        for generation in range(2, generation_count + 1):
            remaining = target_size - (len(members) - genealogy_start_count)
            if remaining <= 0:
                break

            future_generations = generation_count - generation
            reserved_for_male_line = 2 * future_generations
            current_budget = remaining - reserved_for_male_line
            if generation < generation_count:
                current_budget = max(2, current_budget)
            else:
                current_budget = remaining

            next_couples = []
            couples = active_couples[:]
            random.shuffle(couples)
            birth_base = 1100 + index * 3 + (generation - 1) * 25
            chain_created = False

            for father_id, mother_id in couples:
                if current_budget <= 0:
                    break

                max_children_for_couple = min(9, child_count())
                created_for_couple = 0

                if generation < generation_count and not chain_created and current_budget >= 2:
                    son_id = add_member(
                        genealogy_id,
                        family_surname,
                        "M",
                        generation,
                        birth_base + random.randint(0, 8),
                        f"{family_surname}氏第{generation}代本族成员",
                    )
                    wife_id = add_member(
                        genealogy_id,
                        choose_spouse_surname(family_surname),
                        "F",
                        generation,
                        birth_base + random.randint(-2, 6),
                        f"{family_surname}氏第{generation}代配偶",
                    )
                    parent_child.append({"parent_id": father_id, "child_id": son_id})
                    parent_child.append({"parent_id": mother_id, "child_id": son_id})
                    add_marriage(son_id, wife_id, birth_base + 22 + random.randint(0, 5))
                    next_couples.append((son_id, wife_id))
                    current_budget -= 2
                    created_for_couple += 1
                    chain_created = True

                while created_for_couple < max_children_for_couple and current_budget > 0:
                    gender = "M" if random.random() < 0.55 else "F"
                    child_id = add_member(
                        genealogy_id,
                        family_surname,
                        gender,
                        generation,
                        birth_base + random.randint(0, 8),
                        f"{family_surname}氏第{generation}代本族成员",
                    )
                    parent_child.append({"parent_id": father_id, "child_id": child_id})
                    parent_child.append({"parent_id": mother_id, "child_id": child_id})
                    current_budget -= 1
                    created_for_couple += 1

                    if gender == "M" and generation < generation_count and current_budget > 0:
                        wife_id = add_member(
                            genealogy_id,
                            choose_spouse_surname(family_surname),
                            "F",
                            generation,
                            birth_base + random.randint(-2, 6),
                            f"{family_surname}氏第{generation}代配偶",
                        )
                        add_marriage(child_id, wife_id, birth_base + 22 + random.randint(0, 5))
                        next_couples.append((child_id, wife_id))
                        current_budget -= 1

            if generation < generation_count and not next_couples:
                father_id, mother_id = active_couples[0]
                son_id = add_member(
                    genealogy_id,
                    family_surname,
                    "M",
                    generation,
                    birth_base,
                    f"{family_surname}氏第{generation}代本族成员",
                )
                wife_id = add_member(
                    genealogy_id,
                    choose_spouse_surname(family_surname),
                    "F",
                    generation,
                    birth_base,
                    f"{family_surname}氏第{generation}代配偶",
                )
                parent_child.append({"parent_id": father_id, "child_id": son_id})
                parent_child.append({"parent_id": mother_id, "child_id": son_id})
                add_marriage(son_id, wife_id, birth_base + 22)
                next_couples.append((son_id, wife_id))

            active_couples = next_couples or active_couples[:1]

        genealogy_id += 1

    written_paths = []
    for genealogy in genealogies:
        genealogy_members = [
            member for member in members if member["genealogy_id"] == genealogy["id"]
        ]
        written_paths.append(
            write_genealogy_csv(
                output_dir,
                genealogy,
                genealogy_members,
                parent_child,
                marriages,
            )
        )

    print(f"Generated {len(genealogies)} genealogies.")
    print(f"Generated {len(members)} members.")
    print(f"Generated {len(parent_child)} parent-child rows.")
    print(f"Generated {len(marriages)} marriage rows.")
    print(f"CSV files written to {output_dir}.")
    for path in written_paths:
        print(path)


def parse_args():
    parser = argparse.ArgumentParser(description="Generate family-tree CSV data.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory for generated CSV files.",
    )
    parser.add_argument(
        "--sizes",
        default=",".join(str(size) for size in DEFAULT_GENEALOGY_SIZES),
        help="Comma-separated member counts for each genealogy.",
    )
    parser.add_argument(
        "--generations",
        type=int,
        default=30,
        help="Generation count per genealogy.",
    )
    parser.add_argument(
        "--surname",
        help="Surname for the first genealogy. Use --surnames for multiple values.",
    )
    parser.add_argument(
        "--name",
        help="Name for the first genealogy. Use --names for multiple values.",
    )
    parser.add_argument(
        "--compiled-at",
        help="Compiled date for the first genealogy, for example 2026-05-17.",
    )
    parser.add_argument(
        "--surnames",
        help="Comma-separated surnames for generated genealogies.",
    )
    parser.add_argument(
        "--names",
        help="Comma-separated genealogy names for generated genealogies.",
    )
    parser.add_argument(
        "--compiled-dates",
        help="Comma-separated compiled dates for generated genealogies.",
    )
    parser.add_argument("--seed", type=int, default=20260515)
    return parser.parse_args()


def parse_csv_arg(value):
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


if __name__ == "__main__":
    args = parse_args()
    sizes = [int(item.strip()) for item in args.sizes.split(",") if item.strip()]
    surnames = parse_csv_arg(args.surnames)
    genealogy_names = parse_csv_arg(args.names)
    compiled_dates = parse_csv_arg(args.compiled_dates)
    if args.surname:
        surnames = [args.surname.strip()] + surnames[1:]
    if args.name:
        genealogy_names = [args.name.strip()] + genealogy_names[1:]
    if args.compiled_at:
        compiled_dates = [args.compiled_at.strip()] + compiled_dates[1:]

    generate_dataset(
        args.output_dir,
        sizes,
        args.generations,
        args.seed,
        surnames=surnames,
        genealogy_names=genealogy_names,
        compiled_dates=compiled_dates,
    )
