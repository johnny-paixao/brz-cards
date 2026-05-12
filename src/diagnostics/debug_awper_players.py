import pandas as pd

INPUT_FILE = "data/brz_card_scores_v2.csv"

df = pd.read_csv(INPUT_FILE)

columns = [
    "faceit_nickname",
    "cs2_skill_level",
    "cs2_faceit_elo",
    "Sniper Kill Rate",
    "Sniper Kill Rate per Round",
    "Total Sniper Kills",
    "Average K/D Ratio",
    "ADR",
    "AWPER_SCORE",
    "ROLE"
]

available_columns = [c for c in columns if c in df.columns]

awp_df = df[available_columns].copy()

awp_df = awp_df.sort_values(
    by="AWPER_SCORE",
    ascending=False
)

print("\n=== BRZ AWPER DIAGNOSTIC ===\n")
print(awp_df.to_string(index=False))