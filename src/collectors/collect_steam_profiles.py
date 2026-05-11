import sys
from pathlib import Path


# Allow imports from the src directory when running this script directly.
SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(SRC_DIR))

from clients.steam_client import fetch_player_summary_by_steam64
from database.bigquery_client import (
    get_active_players_with_steam64,
    update_player_steam_profile,
)


def main() -> None:
    players = get_active_players_with_steam64()

    if not players:
        print("No active players with Steam64 ID found.")
        return

    print(f"Found {len(players)} active player(s) with Steam64 ID.")

    for player in players:
        player_id = player["player_id"]
        display_name = player["display_name"]
        steam64_id = player["steam64_id"]

        print(f"\nCollecting Steam profile for {display_name} ({steam64_id})...")

        response_data = fetch_player_summary_by_steam64(steam64_id)

        status_code = response_data["status_code"]
        steam_player = response_data["player"]
        error_message = response_data["error_message"]

        print(f"Status code: {status_code}")

        if status_code >= 400:
            print(f"Failed to collect Steam profile for {display_name}: {error_message}")
            continue

        if not steam_player:
            print(f"No Steam player data found for {display_name}.")
            continue

        steam_avatar_url = steam_player.get("avatarfull")
        steam_country_code = steam_player.get("loccountrycode")

        update_player_steam_profile(
            player_id=player_id,
            steam_avatar_url=steam_avatar_url,
            steam_country_code=steam_country_code,
        )

        print(f"Player updated: {display_name}")
        print(f"Steam name: {steam_player.get('personaname')}")
        print(f"Avatar full: {steam_avatar_url}")
        print(f"Steam country code: {steam_country_code}")


if __name__ == "__main__":
    main()