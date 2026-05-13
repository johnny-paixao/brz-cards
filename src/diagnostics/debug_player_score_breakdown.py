import sys
from pathlib import Path

import pandas as pd

SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(SRC_DIR))

from scoring.calculate_brz_card_scores_v2 import (
    LIFETIME_STATS_CSV_PATH,
    PERCENTILES_CSV_PATH,
    load_percentiles,
    calculate_core_scores,
    calculate_role,
)


PLAYER = "FenoNemo"


def main() -> None:
    df = pd.read_csv(LIFETIME_STATS_CSV_PATH)
    percentiles = load_percentiles(PERCENTILES_CSV_PATH)

    player_row = df[df["faceit_nickname"].str.lower() == PLAYER.lower()]

    if player_row.empty:
        raise ValueError(f"Player not found: {PLAYER}")

    row = player_row.iloc[0]

    scores = calculate_core_scores(row, percentiles)
    role, role_scores = calculate_role(row, scores, percentiles)

    print(f"\n=== SCORE BREAKDOWN: {PLAYER} ===\n")

    print("Raw FACEIT values:")
    fields = [
        "Average K/D Ratio",
        "Average Headshots %",
        "ADR",
        "Entry Success Rate",
        "Entry Rate",
        "Utility Success Rate",
        "Utility Damage per Round",
        "Flash Success Rate",
        "Enemies Flashed per Round",
        "Win Rate %",
        "Recent Results",
        "Total 1v1 Count",
        "Total 1v1 Wins",
        "Total 1v2 Count",
        "Total 1v2 Wins",
        "Total Matches",
        "cs2_faceit_elo",
        "cs2_skill_level",
        "Longest Win Streak",
        "Sniper Kill Rate",
        "Sniper Kill Rate per Round",
        "Total Sniper Kills",
    ]

    for field in fields:
        print(f"{field}: {row.get(field)}")

    print("\nNormalized values:")
    for key, value in scores["_normalized"].items():
        print(f"{key}: {value}")

    print("\nFinal BRz stats:")
    for key in ["AIM", "IMP", "UTL", "CON", "CLT", "EXP", "OVERALL"]:
        print(f"{key}: {scores[key]}")

    print(f"\nROLE: {role}")

    print("\nRole scores:")
    for key, value in role_scores.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()