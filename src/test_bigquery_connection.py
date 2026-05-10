from database.bigquery_client import get_latest_player_card


def main() -> None:
    player_name = "Johnny"

    card = get_latest_player_card(player_name)

    if card is None:
        print(f"No card found for player: {player_name}")
        return

    print("BRz Card found:")
    print(f"Player: {card['display_name']}")
    print(f"Overall: {card['overall_brz']}")
    print(f"Role: {card['role']}")
    print(f"Tier: {card['tier']}")
    print(f"Aim: {card['aim']}")
    print(f"Impact: {card['impact']}")
    print(f"Utility: {card['utility']}")
    print(f"Consistency: {card['consistency']}")
    print(f"Clutch: {card['clutch']}")
    print(f"Experience: {card['experience']}")
    print(f"Matches analyzed: {card['matches_analyzed']}")
    print(f"Score version: {card['score_version']}")
    print(f"Calculated at: {card['calculated_at']}")


if __name__ == "__main__":
    main()