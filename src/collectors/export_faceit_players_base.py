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


def get_faceit_player_by_id(player_id: str) -> dict | None:
    url = f"{FACEIT_API_BASE_URL}/players/{player_id}"

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

    import pandas as pd

    # Carrega ou inicializa o DataFrame
    if OUTPUT_CSV_PATH.exists():
        df = pd.read_csv(OUTPUT_CSV_PATH, dtype=object)
    else:
        df = pd.DataFrame(columns=[
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
        ])

    # Garantir que todas as colunas existem
    base_cols = list(df.columns)
    for col in [
        "faceit_nickname_input", "faceit_nickname_official", "faceit_player_id",
        "country", "steam_id_64", "steam_nickname", "cs2_skill_level",
        "cs2_faceit_elo", "cs2_game_player_id", "cs2_game_player_name",
        "avatar", "faceit_url", "activated_at"
    ]:
        if col not in base_cols:
            df[col] = None

    input_changes = {} # Mapeia antigo_nick.lower() -> novo_nick (original case)
    
    for nickname in nicknames:
        player_id = None
        # Tenta achar o registro anterior para obter o player_id imutável
        mask = (df["faceit_nickname_input"].str.lower() == nickname.lower()) | \
               (df["faceit_nickname_official"].str.lower() == nickname.lower())
        
        if mask.any():
            idx = df[mask].index[0]
            player_id = df.at[idx, "faceit_player_id"]
            if pd.isna(player_id) or not str(player_id).strip():
                player_id = None

        player = None
        # Busca prioritária por ID imutável
        if player_id:
            try:
                player = get_faceit_player_by_id(str(player_id).strip())
                if player:
                    print(f"[FETCH BY ID OK] ID={player_id} for input nickname '{nickname}'")
            except Exception as e:
                print(f"[FETCH BY ID FAILED] ID={player_id}: {e}. Retrying by nickname...")

        # Fallback para busca por nickname
        if player is None:
            try:
                player = get_faceit_player_by_nickname(nickname)
            except Exception as e:
                print(f"[FETCH BY NICK ERROR] Nickname '{nickname}': {e}")

        if player is None:
            print(f"[NOT FOUND] {nickname}")
            continue

        official_nickname = player.get("nickname")
        row = build_enriched_player_row(nickname, player)

        # Detectar troca de nickname
        if nickname.lower() != official_nickname.lower():
            print(f"🔥 [NICKNAME CHANGED] Player '{nickname}' is now officially '{official_nickname}'!")
            input_changes[nickname.lower()] = official_nickname
            # Ajustar o input na linha enriquecida também
            row["faceit_nickname_input"] = official_nickname

        # Atualiza ou adiciona no DataFrame
        # A máscara deve buscar pelo ID se soubermos, ou pelo nick
        if player_id:
            mask_id = df["faceit_player_id"] == player_id
        else:
            mask_id = (df["faceit_nickname_input"].str.lower() == nickname.lower()) | \
                      (df["faceit_nickname_official"].str.lower() == nickname.lower())

        if mask_id.any():
            idx = df[mask_id].index[0]
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

    # Grava o CSV enriquecido
    OUTPUT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV_PATH, index=False, encoding="utf-8-sig")
    print("-" * 80)
    print(f"Saved enriched players base to: {OUTPUT_CSV_PATH}")

    # Se houver mudanças de nicks de entrada, reescrevemos o brz_faceit_players.csv original
    if input_changes:
        updated_nicks = []
        for nickname in nicknames:
            low = nickname.lower()
            if low in input_changes:
                updated_nicks.append(input_changes[low])
            else:
                updated_nicks.append(nickname)
        
        with open(INPUT_CSV_PATH, mode="w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["faceit_nickname"])
            for nick in updated_nicks:
                writer.writerow([nick])
        print(f" Sincronizado {len(input_changes)} novos nicknames no arquivo de entrada original: {INPUT_CSV_PATH}")


if __name__ == "__main__":
    main()