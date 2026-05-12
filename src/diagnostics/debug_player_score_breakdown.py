import sys
from pathlib import Path

import pandas as pd

SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(SRC_DIR))

from scoring.competitive_scaling import (
    normalize_adr,
    normalize_kd,
    normalize_hs,
    normalize_entry_success,
    normalize_entry_rate,
)

from scoring.calculate_brz_card_scores_v2 import (
    LIFETIME_STATS_CSV_PATH,
    PERCENTILES_CSV_PATH,
    load_percentiles,
    normalize_by_percentile,
    recent_results_score,
    safe_float,
    weighted_score,
)


PLAYER = "DigdiM--"


def main() -> None:
    df = pd.read_csv(LIFETIME_STATS_CSV_PATH)
    percentiles = load_percentiles(PERCENTILES_CSV_PATH)

    row = df[df["faceit_nickname"].str.lower() == PLAYER.lower()]

    if row.empty:
        raise ValueError(f"Player not found: {PLAYER}")

    row = row.iloc[0]

    metrics = {
        "HS": normalize_hs(safe_float(row.get("Average Headshots %"))),
        "KD": normalize_kd(safe_float(row.get("Average K/D Ratio"))),
        "ADR": normalize_adr(safe_float(row.get("ADR"))),
        "Entry Success": normalize_entry_success(safe_float(row.get("Entry Success Rate"))),
        "Entry Rate": normalize_entry_rate(safe_float(row.get("Entry Rate"))),
        "Utility Damage": normalize_by_percentile(row.get("Utility Damage per Round"), "Utility Damage per Round", percentiles),
        "Flash Success": normalize_by_percentile(row.get("Flash Success Rate"), "Flash Success Rate", percentiles),
        "Utility Success": normalize_by_percentile(row.get("Utility Success Rate"), "Utility Success Rate", percentiles),
        "Win Rate": normalize_by_percentile(row.get("Win Rate %"), "Win Rate %", percentiles),
        "Longest Streak": normalize_by_percentile(row.get("Longest Win Streak"), "Longest Win Streak", percentiles),
        "Recent Results": recent_results_score(row.get("Recent Results")),
        "1v1": normalize_by_percentile(row.get("1v1 Win Rate"), "1v1 Win Rate", percentiles),
        "1v2": normalize_by_percentile(row.get("1v2 Win Rate"), "1v2 Win Rate", percentiles),
        "Matches": normalize_by_percentile(row.get("Matches"), "Matches", percentiles),
        "Rounds": normalize_by_percentile(row.get("Total Rounds with extended stats"), "Total Rounds with extended stats", percentiles),
    }

    elo = safe_float(row.get("cs2_faceit_elo"))
    metrics["ELO"] = min(max((elo - 800) / (2300 - 800) * 100, 0), 100)

    scores = {
        "AIM": weighted_score([(metrics["HS"], 0.40), (metrics["KD"], 0.35), (metrics["ADR"], 0.25)]),
        "IMP": weighted_score([(metrics["ADR"], 0.40), (metrics["Entry Success"], 0.35), (metrics["Entry Rate"], 0.25)]),
        "UTL": weighted_score([(metrics["Utility Damage"], 0.40), (metrics["Flash Success"], 0.30), (metrics["Utility Success"], 0.30)]),
        "CON": weighted_score([(metrics["Win Rate"], 0.50), (metrics["Longest Streak"], 0.30), (metrics["Recent Results"], 0.20)]),
        "CLT": weighted_score([(metrics["1v2"], 0.70), (metrics["1v1"], 0.30)]),
        "EXP": weighted_score([(metrics["Matches"], 0.50), (metrics["Rounds"], 0.30), (metrics["ELO"], 0.20)]),
    }

    print(f"\n=== SCORE BREAKDOWN: {PLAYER} ===\n")

    print("Raw values:")
    raw_fields = [
        "ADR",
        "Average K/D Ratio",
        "Average Headshots %",
        "Entry Success Rate",
        "Entry Rate",
        "Utility Damage per Round",
        "Flash Success Rate",
        "Utility Success Rate",
        "Win Rate %",
        "Longest Win Streak",
        "Recent Results",
        "1v1 Win Rate",
        "1v2 Win Rate",
        "Matches",
        "Total Rounds with extended stats",
        "cs2_faceit_elo",
    ]

    for field in raw_fields:
        print(f"{field}: {row.get(field)}")

    print("\nNormalized values:")
    for key, value in metrics.items():
        print(f"{key}: {round(value, 2)}")

    print("\nFinal BRz stats:")
    for key, value in scores.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()