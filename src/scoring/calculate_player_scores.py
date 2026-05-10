import sys
from pathlib import Path


# Allow imports from the src directory when running this script directly.
SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(SRC_DIR))

from database.bigquery_client import (
    get_active_players_with_steam64,
    get_latest_leetify_profile_payload,
    get_recent_leetify_match_stats,
    insert_player_card_score,
)
from scoring.score_engine import calculate_brz_card_score


MIN_FACEIT_MATCHES = 10
MATCHES_LIMIT = 100


def main() -> None:
    players = get_active_players_with_steam64()

    if not players:
        print("No active players with Steam64 ID found.")
        return

    print(f"Found {len(players)} active player(s).")

    for player in players:
        player_id = player["player_id"]
        display_name = player["display_name"]

        print(f"\nCalculating BRz card for {display_name}...")

        profile_payload = get_latest_leetify_profile_payload(player_id)

        if not profile_payload:
            print(f"No Leetify profile snapshot found for {display_name}.")
            continue

        matches = get_recent_leetify_match_stats(
            player_id=player_id,
            limit=MATCHES_LIMIT,
            match_source="faceit",
        )

        if len(matches) < MIN_FACEIT_MATCHES:
            print(
                f"Only {len(matches)} FACEIT match(es) found. "
                "Falling back to all Leetify sources."
            )

            matches = get_recent_leetify_match_stats(
                player_id=player_id,
                limit=MATCHES_LIMIT,
                match_source=None,
            )

        if not matches:
            print(f"No matches found for {display_name}.")
            continue

        card_score = calculate_brz_card_score(
            player=player,
            matches=matches,
            profile_payload=profile_payload,
        )

        card_score_id = insert_player_card_score(card_score)

        print(f"Card score inserted: {card_score_id}")
        print(f"Player: {card_score['display_name']}")
        print(f"Overall: {card_score['overall_brz']}")
        print(f"Aim: {card_score['aim']}")
        print(f"Impact: {card_score['impact']}")
        print(f"Utility: {card_score['utility']}")
        print(f"Consistency: {card_score['consistency']}")
        print(f"Clutch: {card_score['clutch']}")
        print(f"Experience: {card_score['experience']}")
        print(f"Role: {card_score['role']}")
        print(f"Tier: {card_score['tier']}")
        print(f"Matches analyzed: {card_score['matches_analyzed']}")
        print(f"Score version: {card_score['score_version']}")


if __name__ == "__main__":
    main()