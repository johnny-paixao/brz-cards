import sys
from pathlib import Path


# Allow imports from the src directory when running this script directly.
SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(SRC_DIR))

from clients.leetify_client import fetch_profile_by_steam64
from database.bigquery_client import (
    get_active_players_with_steam64,
    insert_api_snapshot,
    update_player_leetify_profile,
    upsert_leetify_recent_matches,
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

        print(f"\nCollecting Leetify profile for {display_name} ({steam64_id})...")

        response_data = fetch_profile_by_steam64(steam64_id)

        status_code = response_data["status_code"]
        request_url = response_data["request_url"]
        payload = response_data["payload"]
        error_message = response_data["error_message"]

        snapshot_id = insert_api_snapshot(
            player_id=player_id,
            source="leetify",
            endpoint="/v3/profile",
            request_url=request_url,
            payload=payload,
            status_code=status_code,
            error_message=error_message,
        )

        print(f"Snapshot saved: {snapshot_id}")
        print(f"Status code: {status_code}")

        if status_code >= 400 or not payload:
            print(f"Failed to collect {display_name}: {error_message}")
            continue

        update_player_leetify_profile(
            player_id=player_id,
            steam64_id=payload.get("steam64_id"),
            leetify_profile_id=payload.get("id"),
            leetify_name=payload.get("name"),
        )

        recent_matches = payload.get("recent_matches", [])

        processed_matches = upsert_leetify_recent_matches(
            player_id=player_id,
            matches=recent_matches,
            raw_snapshot_id=snapshot_id,
        )

        print(f"Player updated: {display_name}")
        print(f"Recent matches processed: {processed_matches}")


if __name__ == "__main__":
    main()