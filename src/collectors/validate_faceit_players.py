import csv
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv()

FACEIT_API_KEY = os.getenv("FACEIT_API_KEY")
FACEIT_API_BASE_URL = "https://open.faceit.com/data/v4"

CSV_PATH = Path("data/brz_faceit_players.csv")


if not FACEIT_API_KEY:
    raise ValueError("FACEIT_API_KEY is missing. Check your .env file.")


HEADERS = {
    "Authorization": f"Bearer {FACEIT_API_KEY}",
    "Accept": "application/json",
}


def get_faceit_player_by_nickname(nickname: str) -> dict | None:
    url = f"{FACEIT_API_BASE_URL}/players"

    response = requests.get(
        url,
        headers=HEADERS,
        params={"nickname": nickname},
        timeout=30,
    )

    if response.status_code == 404:
        return None

    if response.status_code != 200:
        raise RuntimeError(
            f"FACEIT API error for nickname '{nickname}' "
            f"({response.status_code}): {response.text}"
        )

    return response.json()


def read_faceit_nicknames(csv_path: Path) -> list[str]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    nicknames = []

    with open(csv_path, mode="r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if "faceit_nickname" not in reader.fieldnames:
            raise ValueError(
                "CSV must contain a column named 'faceit_nickname'."
            )

        for row in reader:
            nickname = row["faceit_nickname"].strip()

            if nickname:
                nicknames.append(nickname)

    return nicknames


def main() -> None:
    nicknames = read_faceit_nicknames(CSV_PATH)

    print(f"Loaded {len(nicknames)} FACEIT nickname(s) from {CSV_PATH}")
    print("-" * 80)

    found_count = 0
    not_found_count = 0

    for nickname in nicknames:
        player = get_faceit_player_by_nickname(nickname)

        if player is None:
            not_found_count += 1
            print(f"[NOT FOUND] {nickname}")
            continue

        found_count += 1

        games = player.get("games", {})
        cs2 = games.get("cs2", {})

        print(
            f"[FOUND] {nickname} -> "
            f"official={player.get('nickname')} | "
            f"player_id={player.get('player_id')} | "
            f"level={cs2.get('skill_level')} | "
            f"elo={cs2.get('faceit_elo')} | "
            f"country={player.get('country')}"
        )

    print("-" * 80)
    print(f"Found: {found_count}")
    print(f"Not found: {not_found_count}")
    print("Validation complete.")


if __name__ == "__main__":
    main()