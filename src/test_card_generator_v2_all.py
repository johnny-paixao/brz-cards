import csv
from pathlib import Path

from cards.card_generator import generate_player_card_from_faceit_csv


BASE_DIR = Path(__file__).resolve().parents[1]
CSV_PATH = BASE_DIR / "data" / "brz_card_scores_v2.csv"


def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")

    with open(CSV_PATH, mode="r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            nickname = row["faceit_nickname"].strip()

            if not nickname:
                continue

            output_path = generate_player_card_from_faceit_csv(nickname)
            print(f"Generated: {nickname} -> {output_path}")


if __name__ == "__main__":
    main()