import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
CACHE_DIR = BASE_DIR / "data" / "cache" / "faceit_match_stats"


def main() -> None:
    files = list(CACHE_DIR.glob("*.json"))

    if not files:
        raise FileNotFoundError(f"No cached match stats found in {CACHE_DIR}")

    sample_path = files[0]

    with open(sample_path, mode="r", encoding="utf-8") as file:
        payload = json.load(file)

    print(f"\nSample file: {sample_path.name}\n")

    rounds = payload.get("rounds", [])

    for round_data in rounds:
        for team in round_data.get("teams", []):
            for player in team.get("players", []):
                nickname = player.get("nickname")
                player_id = player.get("player_id")
                stats = player.get("player_stats", {})

                print(f"Player: {nickname}")
                print(f"Player ID: {player_id}")
                print("\nAvailable player_stats keys:\n")

                for key in sorted(stats.keys()):
                    print(f"- {key}: {stats.get(key)}")

                return

    print("No player stats found.")


if __name__ == "__main__":
    main()