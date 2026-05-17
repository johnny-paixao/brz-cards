import csv
import os
from pathlib import Path
import time

import requests
from dotenv import load_dotenv


load_dotenv()

FACEIT_API_KEY = os.getenv("FACEIT_API_KEY")
FACEIT_API_BASE_URL = "https://open.faceit.com/data/v4"

INPUT_CSV_PATH = Path("data/brz_faceit_players.csv")
OUTPUT_CSV_PATH = Path("data/brz_faceit_players_enriched.csv")


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


def build_enriched_player_row(input_nickname: str, player: dict) -> dict:
    games = player.get("games", {})
    cs2 = games.get("cs2", {})

    return {
        "faceit_nickname_input": input_nickname,
        "faceit_nickname_official": player.get("nickname"),
        "faceit_player_id": player.get("player_id"),
        "country": player.get("country"),
        "steam_id_64": player.get("steam_id_64"),
        "steam_nickname": player.get("steam_nickname"),
        "cs2_skill_level": cs2.get("skill_level"),
        "cs2_faceit_elo": cs2.get("faceit_elo"),
        "cs2_game_player_id": cs2.get("game_player_id"),
        "cs2_game_player_name": cs2.get("game_player_name"),
        "avatar": player.get("avatar"),
        "faceit_url": player.get("faceit_url"),
        "activated_at": player.get("activated_at"),
    }


def main() -> None:
    nicknames = read_faceit_nicknames(INPUT_CSV_PATH)

    print(f"Loaded {len(nicknames)} FACEIT nickname(s).")
    print(f"Input: {INPUT_CSV_PATH}")
    print(f"Output: {OUTPUT_CSV_PATH}")
    print("-" * 80)

    if OUTPUT_CSV_PATH.exists():
        import pandas as pd
        df = pd.read_csv(OUTPUT_CSV_PATH)

        base_cols = [
            "faceit_nickname_input",
            "faceit_nickname_official",
            "faceit_player_id",
            "country",
            "steam_id_64",
            "steam_nickname",
            "cs2_skill_level",
            "cs2_faceit_elo",
            "cs2_game_player_id",
            "cs2_game_player_name",
            "avatar",
            "faceit_url",
            "activated_at",
        ]
        for col in base_cols:
            if col not in df.columns:
                df[col] = None

        for nickname in nicknames:
            player = get_faceit_player_by_nickname(nickname)

            if player is None:
                print(f"[NOT FOUND] {nickname}")
                continue

            row = build_enriched_player_row(nickname, player)

            mask = (df["faceit_nickname_input"].str.lower() == nickname.lower()) | \
                   (df["faceit_nickname_official"].str.lower() == nickname.lower())

            if mask.any():
                idx = df[mask].index[0]
                for key, val in row.items():
                    df.at[idx, key] = val
                print(
                    f"[UPDATED] {row['faceit_nickname_official']} | "
                    f"level={row['cs2_skill_level']} | "
                    f"elo={row['cs2_faceit_elo']}"
                )
            else:
                new_row_df = pd.DataFrame([row])
                df = pd.concat([df, new_row_df], ignore_index=True)
                print(
                    f"[ADDED] {row['faceit_nickname_official']} | "
                    f"level={row['cs2_skill_level']} | "
                    f"elo={row['cs2_faceit_elo']}"
                )
            time.sleep(0.15)

        df.to_csv(OUTPUT_CSV_PATH, index=False, encoding="utf-8-sig")
        print("-" * 80)
        print(f"Updated in-place and saved enriched players base to: {OUTPUT_CSV_PATH}")
        return

    rows = []

    for nickname in nicknames:
        player = get_faceit_player_by_nickname(nickname)

        if player is None:
            print(f"[NOT FOUND] {nickname}")

            rows.append(
                {
                    "faceit_nickname_input": nickname,
                    "faceit_nickname_official": "",
                    "faceit_player_id": "",
                    "country": "",
                    "steam_id_64": "",
                    "steam_nickname": "",
                    "cs2_skill_level": "",
                    "cs2_faceit_elo": "",
                    "cs2_game_player_id": "",
                    "cs2_game_player_name": "",
                    "avatar": "",
                    "faceit_url": "",
                    "activated_at": "",
                }
            )
            continue

        row = build_enriched_player_row(nickname, player)
        rows.append(row)

        print(
            f"[OK] {row['faceit_nickname_official']} | "
            f"level={row['cs2_skill_level']} | "
            f"elo={row['cs2_faceit_elo']} | "
            f"country={row['country']}"
        )
        time.sleep(0.15)

    OUTPUT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "faceit_nickname_input",
        "faceit_nickname_official",
        "faceit_player_id",
        "country",
        "steam_id_64",
        "steam_nickname",
        "cs2_skill_level",
        "cs2_faceit_elo",
        "cs2_game_player_id",
        "cs2_game_player_name",
        "avatar",
        "faceit_url",
        "activated_at",
    ]

    with open(OUTPUT_CSV_PATH, mode="w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("-" * 80)
    print(f"Saved enriched players base to: {OUTPUT_CSV_PATH}")


if __name__ == "__main__":
    main()