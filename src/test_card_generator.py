from cards.card_generator import generate_player_card_from_faceit_csv


def main() -> None:
    output_path = generate_player_card_from_faceit_csv("JohnnyPanda")

    print(f"Card generated successfully: {output_path}")


if __name__ == "__main__":
    main()