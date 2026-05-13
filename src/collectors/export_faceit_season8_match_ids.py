import csv
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_CSV_PATH = BASE_DIR / "data" / "brz_faceit_players_enriched.csv"
OUTPUT_CSV_PATH = BASE_DIR / "data" / "brz_faceit_season8_match_ids.csv"

GAME_ID = "cs2"
SEASON_8_START = datetime(2026, 4, 22, tzinfo=timezone.utc)
SEASON_8_START_UNIX = int(SEASON_8_START.timestamp())

FACEIT_API_BASE_URL = "https://open.faceit.com/data/v4"


def get_api_key() -> str:
    api_key = os.getenv("FACEIT_API_KEY")

    if not api_key:
        raise RuntimeError(
            "FACEIT_API_KEY not found. Set it in your environment before running this script."
        )

    return api_key


def faceit_get(endpoint: str, params: dict | None = None) -> dict:
    url = f"{FACEIT_API_BASE_URL}{endpoint}"

    headers = {
        "Authorization": f"Bearer {get_api_key()}",
        "Accept": "application/json",
    }

    response = requests.get(url, headers=headers, params=params, timeout=30)

    if response.status_code == 429:
        print("[RATE LIMIT] Waiting 60 seconds...")
        time.sleep(60)
        response = requests.get(url, headers=headers, params=params, timeout=30)

    response.raise_for_status()
    return response.json()


def load_players() -> list[dict]:
    if not INPUT_CSV_PATH.exists():
        raise FileNotFoundError(f"Input CSV not found: {INPUT_CSV_PATH}")

    with open(INPUT_CSV_PATH, mode="r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def get_player_history_since(player_id: str) -> list[dict]:
    matches = []
    offset = 0
    limit = 100

    while True:
        payload = faceit_get(
            f"/players/{player_id}/history",
            params={
                "game": GAME_ID,
                "from": SEASON_8_START_UNIX,
                "offset": offset,
                "limit": limit,
            },
        )

        items = payload.get("items", [])

        if not items:
            break

        matches.extend(items)

        if len(items) < limit:
            break

        offset += limit
        time.sleep(0.25)

    return matches


def main() -> None:
    players = load_players()
    output_rows = []

    print(f"Loaded {len(players)} player(s).")
    print(f"Season 8 cutoff UTC: {SEASON_8_START.isoformat()}")
    print("-" * 80)

    for index, player in enumerate(players, start=1):
        nickname = (
            player.get("faceit_nickname_official")
            or player.get("faceit_nickname_input")
            or player.get("faceit_nickname")
            or player.get("nickname")
            or ""
        )

        player_id = (
            player.get("faceit_player_id")
            or player.get("player_id")
            or ""
        )

        if not player_id:
            print(f"[SKIP] {nickname}: missing player_id")
            continue

        try:
            matches = get_player_history_since(player_id)

            print(
                f"[{index}/{len(players)}] {nickname} | "
                f"player_id={player_id} | season8_matches={len(matches)}"
            )

            for match in matches:
                output_rows.append(
                    {
                        "faceit_nickname": nickname,
                        "faceit_player_id": player_id,
                        "match_id": match.get("match_id"),
                        "game_id": match.get("game_id"),
                        "finished_at": match.get("finished_at"),
                        "started_at": match.get("started_at"),
                        "competition_name": match.get("competition_name"),
                        "match_type": match.get("match_type"),
                        "game_mode": match.get("game_mode"),
                        "max_players": match.get("max_players"),
                        "teams_size": match.get("teams_size"),
                    }
                )

        except Exception as error:
            print(f"[ERROR] {nickname}: {error}")

        time.sleep(0.35)

    OUTPUT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_CSV_PATH, mode="w", encoding="utf-8", newline="") as file:
        fieldnames = [
            "faceit_nickname",
            "faceit_player_id",
            "match_id",
            "game_id",
            "finished_at",
            "started_at",
            "competition_name",
            "match_type",
            "game_mode",
            "max_players",
            "teams_size",
        ]

        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print("-" * 80)
    print(f"Saved Season 8 match IDs to: {OUTPUT_CSV_PATH}")
    print(f"Total rows: {len(output_rows)}")


if __name__ == "__main__":
    main()