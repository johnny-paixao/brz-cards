from cards.card_generator import generate_player_card
from database.bigquery_client import get_latest_player_card


def main() -> None:
    player_name = "Johnny"

    card = get_latest_player_card(player_name)

    if card is None:
        print(f"No card found for player: {player_name}")
        return

    output_path = generate_player_card(
        card_data=card,
        output_path="outputs/cards/johnny_card.png",
    )

    print(f"Card generated successfully: {output_path}")


if __name__ == "__main__":
    main()