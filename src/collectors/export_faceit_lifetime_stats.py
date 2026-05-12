import csv
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv()

FACEIT_API_KEY = os.getenv("FACEIT_API_KEY")
FACEIT_API_BASE_URL = "https://open.faceit.com/data/v4"

INPUT_CSV_PATH = Path("data/brz_faceit_players_enriched.csv")
OUTPUT_CSV_PATH = Path("data/brz_faceit_lifetime_stats.csv")


if not FACEIT_API_KEY:
    raise ValueError("FACEIT_API_KEY is missing. Check your .env file.")


HEADERS = {
    "Authorization": f"Bearer {FACEIT_API_KEY}",
    "Accept": "application/json",
}


LIFETIME_FIELDS = [
    "Average K/D Ratio",
    "ADR",
    "Average Headshots %",
    "Win Rate %",
    "Matches",
    "Total Matches",
    "Wins",
    "Recent Results",
    "Current Win Streak",
    "Longest Win Streak",
    "Average K/R Ratio",
    "Entry Success Rate",
    "Entry Rate",
    "Total Entry Count",
    "Total Entry Wins",
    "Utility Damage per Round",
    "Utility Success Rate",
    "Utility Usage per Round",
    "Flash Success Rate",
    "Flashes per Round",
    "Enemies Flashed per Round",
    "Total Utility Damage",
    "Total Enemies Flashed",
    "Total Flash Successes",
    "Total Flash Count",
    "1v1 Win Rate",
    "1v2 Win Rate",
    "Total 1v1 Count",
    "Total 1v1 Wins",
    "Total 1v2 Count",
    "Total 1v2 Wins",
    "Sniper Kill Rate",
    "Sniper Kill Rate per Round",
    "Total Sniper Kills",
    "Total Damage",
    "Total Rounds with extended stats",
    "Total Kills with extended stats",
]


def read_enriched_players(csv_path: Path) -> list[dict]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with open(csv_path, mode="r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def get_faceit_lifetime_stats(player_id: str) -> dict | None:
    url = f"{FACEIT_API_BASE_URL}/players/{player_id}/stats/cs2"

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )

    if response.status_code == 404:
        return None

    if response.status_code != 200:
        raise RuntimeError(
            f"FACEIT API error for player_id '{player_id}' "
            f"({response.status_code}): {response.text}"
        )

    data = response.json()
    return data.get("lifetime", {})


def build_lifetime_row(player: dict, lifetime: dict | None) -> dict:
    row = {
        "faceit_nickname": player.get("faceit_nickname_official"),
        "faceit_player_id": player.get("faceit_player_id"),
        "country": player.get("country"),
        "steam_id_64": player.get("steam_id_64"),
        "cs2_skill_level": player.get("cs2_skill_level"),
        "cs2_faceit_elo": player.get("cs2_faceit_elo"),
    }

    lifetime = lifetime or {}

    for field in LIFETIME_FIELDS:
        value = lifetime.get(field, "")

        if isinstance(value, list):
            value = "|".join(value)

        row[field] = value

    return row


def main() -> None:
    players = read_enriched_players(INPUT_CSV_PATH)

    print(f"Loaded {len(players)} enriched player(s).")
    print(f"Input: {INPUT_CSV_PATH}")
    print(f"Output: {OUTPUT_CSV_PATH}")
    print("-" * 80)

    rows = []

    for index, player in enumerate(players, start=1):
        nickname = player.get("faceit_nickname_official")
        player_id = player.get("faceit_player_id")

        if not player_id:
            print(f"[SKIP] {nickname} has no faceit_player_id.")
            rows.append(build_lifetime_row(player, None))
            continue

        lifetime = get_faceit_lifetime_stats(player_id)
        row = build_lifetime_row(player, lifetime)
        rows.append(row)

        print(
            f"[{index}/{len(players)}] {nickname} | "
            f"level={row.get('cs2_skill_level')} | "
            f"elo={row.get('cs2_faceit_elo')} | "
            f"ADR={row.get('ADR')} | "
            f"KD={row.get('Average K/D Ratio')} | "
            f"WR={row.get('Win Rate %')}"
        )

    fieldnames = [
        "faceit_nickname",
        "faceit_player_id",
        "country",
        "steam_id_64",
        "cs2_skill_level",
        "cs2_faceit_elo",
        *LIFETIME_FIELDS,
    ]

    OUTPUT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_CSV_PATH, mode="w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("-" * 80)
    print(f"Saved lifetime stats to: {OUTPUT_CSV_PATH}")


if __name__ == "__main__":
    main()