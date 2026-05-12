import csv
from pathlib import Path

import pandas as pd


INPUT_CSV_PATH = Path("data/brz_faceit_lifetime_stats.csv")
OUTPUT_CSV_PATH = Path("data/brz_metric_percentiles.csv")


METRICS = [
    "ADR",
    "Average K/D Ratio",
    "Average Headshots %",
    "Win Rate %",
    "Average K/R Ratio",
    "Entry Success Rate",
    "Entry Rate",
    "Utility Damage per Round",
    "Utility Success Rate",
    "Utility Usage per Round",
    "Flash Success Rate",
    "Flashes per Round",
    "Enemies Flashed per Round",
    "1v1 Win Rate",
    "1v2 Win Rate",
    "Total 1v1 Count",
    "Total 1v2 Count",
    "Matches",
    "Total Matches",
    "Current Win Streak",
    "Longest Win Streak",
    "Total Rounds with extended stats",
    "Sniper Kill Rate",
    "Sniper Kill Rate per Round",
    "Total Sniper Kills",
]


def main() -> None:
    if not INPUT_CSV_PATH.exists():
        raise FileNotFoundError(f"Input CSV not found: {INPUT_CSV_PATH}")

    df = pd.read_csv(INPUT_CSV_PATH)

    rows = []

    for metric in METRICS:
        if metric not in df.columns:
            print(f"[SKIP] Column not found: {metric}")
            continue

        values = pd.to_numeric(df[metric], errors="coerce").dropna()

        if values.empty:
            print(f"[SKIP] No numeric values for: {metric}")
            continue

        rows.append(
            {
                "metric": metric,
                "count": int(values.count()),
                "min": round(values.min(), 4),
                "p10": round(values.quantile(0.10), 4),
                "p25": round(values.quantile(0.25), 4),
                "p50": round(values.quantile(0.50), 4),
                "p75": round(values.quantile(0.75), 4),
                "p90": round(values.quantile(0.90), 4),
                "p95": round(values.quantile(0.95), 4),
                "max": round(values.max(), 4),
                "mean": round(values.mean(), 4),
            }
        )

    OUTPUT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_CSV_PATH, mode="w", encoding="utf-8", newline="") as file:
        fieldnames = [
            "metric",
            "count",
            "min",
            "p10",
            "p25",
            "p50",
            "p75",
            "p90",
            "p95",
            "max",
            "mean",
        ]

        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved BRz metric percentiles to: {OUTPUT_CSV_PATH}")
    print()
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()