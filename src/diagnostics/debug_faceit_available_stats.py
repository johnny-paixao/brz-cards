import pandas as pd
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
CSV_PATH = BASE_DIR / "data" / "brz_faceit_lifetime_stats.csv"


def main() -> None:
    df = pd.read_csv(CSV_PATH)

    print("\n=== FACEIT AVAILABLE STATS ===\n")

    for column in df.columns:
        non_null_count = df[column].notna().sum()
        sample_values = df[column].dropna().astype(str).head(3).tolist()

        print(f"{column}")
        print(f"  preenchidos: {non_null_count}/{len(df)}")
        print(f"  exemplos: {sample_values}")
        print()


if __name__ == "__main__":
    main()