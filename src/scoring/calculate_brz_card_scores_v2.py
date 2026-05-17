"""
BRz Cards scoring v2.

Current scoring model:
- Uses FACEIT Season 8 as the main performance window.
- Players need at least 20 Season 8 matches to become ACTIVE.
- INACTIVE players receive zeroed stats and do not participate in normalization.
- Stats are normalized against the active BRz community pool.
- Roles are manual and do not affect OVERALL.
- EXP uses FACEIT Tracker highest ELO + lifetime FACEIT matches.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"

SEASON8_STATS_PATH = DATA_DIR / "brz_faceit_season8_stats.csv"
PLAYERS_ENRICHED_PATH = DATA_DIR / "brz_faceit_players_enriched.csv"
MANUAL_ROLES_PATH = DATA_DIR / "brz_manual_roles.csv"
OUTPUT_PATH = DATA_DIR / "brz_card_scores_v2.csv"

MIN_SEASON8_MATCHES = 20
VOLUME_EXPONENT = 0.65
MAX_OVERALL = 99

LEVEL_MULTIPLIER = {
    1: 0.78,
    2: 0.81,
    3: 0.84,
    4: 0.87,
    5: 0.90,
    6: 0.94,
    7: 0.98,
    8: 1.02,
    9: 1.06,
    10: 1.10,
}


COLUMN_ALIASES = {
    "nickname": [
        "faceit_nickname",
        "nickname",
        "Nickname",
        "player_nickname",
        "faceit_nickname_official",
        "faceit_nickname_input",
    ],
    "player_id": [
        "faceit_player_id",
        "player_id",
        "Player ID",
    ],
    "matches": [
        "Matches",
        "matches",
        "season8_matches",
        "Season 8 Matches",
    ],
    "kd": [
        "Average K/D Ratio",
        "K/D Ratio",
        "KD",
        "kd",
        "average_kd_ratio",
    ],
    "kr": [
        "Average K/R Ratio",
        "K/R Ratio",
        "KR",
        "kr",
        "average_kr_ratio",
    ],
    "adr": [
        "ADR",
        "Average ADR",
        "average_adr",
    ],
    "hs": [
        "Headshots %",
        "HS%",
        "HS",
        "headshots_percent",
    ],
    "entry_rate": [
        "Entry Rate",
        "Match Entry Rate",
        "Average Match Entry Rate",
        "entry_rate",
    ],
    "entry_success": [
        "Entry Success Rate",
        "Match Entry Success Rate",
        "Average Match Entry Success Rate",
        "entry_success_rate",
    ],
    "utility_success": [
        "Utility Success Rate",
        "Utility Success Rate per Match",
        "Average Utility Success Rate per Match",
        "utility_success_rate",
    ],
    "utility_damage_round": [
        "Utility Damage per Round",
        "Utility Damage per Round in a Match",
        "Average Utility Damage per Round in a Match",
        "utility_damage_per_round",
    ],
    "enemies_flashed_round": [
        "Enemies Flashed per Round",
        "Enemies Flashed per Round in a Match",
        "Average Enemies Flashed per Round in a Match",
        "enemies_flashed_per_round",
    ],
    "flash_success": [
        "Flash Success Rate",
        "Flash Success Rate per Match",
        "Average Flash Success Rate per Match",
        "flash_success_rate",
    ],
    "utility_usage_round": [
        "Utility Usage per Round",
        "Utility Usage per Round per Match",
        "Average Utility Usage per Round",
        "utility_usage_per_round",
    ],
    "flashes_round": [
        "Flashes per Round",
        "Flashes per Round in a Match",
        "Average Flashes per Round in a Match",
        "flashes_per_round",
    ],
    "win_rate": [
        "Win Rate",
        "Win Rate %",
        "win_rate",
        "winrate",
    ],
    "one_v_one_count": [
        "1v1Count",
        "1v1 Count",
        "one_v_one_count",
        "Total 1v1 Count",
    ],
    "one_v_one_wins": [
        "1v1Wins",
        "1v1 Wins",
        "one_v_one_wins",
        "Total 1v1 Wins",
    ],
    "one_v_two_count": [
        "1v2Count",
        "1v2 Count",
        "one_v_two_count",
        "Total 1v2 Count",
    ],
    "one_v_two_wins": [
        "1v2Wins",
        "1v2 Wins",
        "one_v_two_wins",
        "Total 1v2 Wins",
    ],
    "current_level": [
        "Level",
        "FACEIT Level",
        "Current Level",
        "faceit_level",
        "current_faceit_level",
        "cs2_skill_level",
    ],
    "current_elo": [
        "ELO",
        "Faceit ELO",
        "FACEIT ELO",
        "current_elo",
        "faceit_elo",
        "current_faceit_elo",
        "cs2_faceit_elo",
    ],
    "tracker_highest_elo": [
        "faceit_tracker_highest_elo",
        "tracker_highest_elo",
        "highest_lifetime_faceit_elo",
        "known_peak_elo",
        "brz_peak_elo",
    ],
    "lifetime_matches": [
        "lifetime_faceit_matches",
        "lifetime_matches",
        "Lifetime Matches",
        "FACEIT Lifetime Matches",
        "total_matches",
        "games_lifetime",
        "faceit_lifetime_matches",
        "cs2_lifetime_matches",
    ],
}


def find_column(df: pd.DataFrame, aliases: Iterable[str]) -> str | None:
    columns = {str(col).strip(): col for col in df.columns}

    for alias in aliases:
        if alias in columns:
            return columns[alias]

    lower_columns = {str(col).strip().lower(): col for col in df.columns}

    for alias in aliases:
        key = alias.strip().lower()

        if key in lower_columns:
            return lower_columns[key]

    return None


def get_series(df: pd.DataFrame, key: str, default: float = 0.0) -> pd.Series:
    col = find_column(df, COLUMN_ALIASES[key])

    if col is None:
        return pd.Series([default] * len(df), index=df.index, dtype="float64")

    return pd.to_numeric(df[col], errors="coerce").fillna(default)


def get_text_series(df: pd.DataFrame, key: str, default: str = "") -> pd.Series:
    col = find_column(df, COLUMN_ALIASES[key])

    if col is None:
        return pd.Series([default] * len(df), index=df.index, dtype="object")

    return df[col].fillna(default).astype(str).str.strip()


def normalize_rate(series: pd.Series, active_mask: pd.Series) -> pd.Series:
    active_values = series.where(active_mask)
    max_value = active_values.max(skipna=True)

    if pd.isna(max_value) or max_value <= 0:
        return pd.Series([0.0] * len(series), index=series.index)

    return (series / max_value * 100).clip(lower=0, upper=100).fillna(0)


def normalize_volume(series: pd.Series, active_mask: pd.Series) -> pd.Series:
    active_values = series.where(active_mask)
    max_value = active_values.max(skipna=True)

    if pd.isna(max_value) or max_value <= 0:
        return pd.Series([0.0] * len(series), index=series.index)

    normalized = (series / max_value).clip(lower=0)

    return (normalized.pow(VOLUME_EXPONENT) * 100).clip(lower=0, upper=100).fillna(0)


def weighted_sum(parts: list[tuple[pd.Series, float]]) -> pd.Series:
    result = pd.Series([0.0] * len(parts[0][0]), index=parts[0][0].index)

    for series, weight in parts:
        result = result + series.fillna(0) * weight

    return result


def safe_ratio(wins: pd.Series, attempts: pd.Series) -> pd.Series:
    attempts = attempts.fillna(0)
    wins = wins.fillna(0)

    return pd.Series(
        [
            float(w) / float(a) if float(a) > 0 else 0.0
            for w, a in zip(wins, attempts)
        ],
        index=wins.index,
    )


def clean_role(value: str) -> str:
    role = str(value or "").strip().upper()

    aliases = {
        "SUP": "SUP",
        "SUPPORT": "SUP",
        "AWP": "AWPER",
        "AWPER": "AWPER",
        "ENTRY": "ENTRY",
        "IGL": "IGL",
        "LURK": "LURKER",
        "LURKER": "LURKER",
        "CLUTCH": "CLUTCHER",
        "CLUTCHER": "CLUTCHER",
        "RIFLE": "RIFLER",
        "RIFLER": "RIFLER",
    }

    return aliases.get(role, role if role else "RIFLER")


def load_manual_roles(path: Path) -> dict[str, str]:
    if not path.exists():
        print(f"[WARN] Manual roles file not found: {path}")
        return {}

    roles_df = pd.read_csv(path)

    nick_col = find_column(roles_df, ["faceit_nickname", "nickname", "Nickname", "nickname Face it"])
    role_col = find_column(roles_df, ["role", "ROLE", "Role"])

    if nick_col is None or role_col is None:
        raise ValueError("Manual roles CSV must contain nickname and role columns.")

    result = {}

    for _, row in roles_df.iterrows():
        nickname = str(row[nick_col]).strip()
        role = clean_role(str(row[role_col]).strip())

        if nickname:
            result[nickname.lower()] = role

    return result


def merge_context_data(stats_df: pd.DataFrame, players_df: pd.DataFrame) -> pd.DataFrame:
    stats = stats_df.copy()
    players = players_df.copy()

    stats["_merge_nickname_key"] = get_text_series(stats, "nickname").str.lower()
    players["_merge_nickname_key"] = get_text_series(players, "nickname").str.lower()

    keep_cols = ["_merge_nickname_key"]

    for semantic_key in [
        "player_id",
        "current_level",
        "current_elo",
        "tracker_highest_elo",
        "lifetime_matches",
    ]:
        col = find_column(players, COLUMN_ALIASES[semantic_key])

        if col is not None and col not in keep_cols:
            keep_cols.append(col)

    players_keep = players[keep_cols].drop_duplicates("_merge_nickname_key")

    merged = stats.merge(players_keep, on="_merge_nickname_key", how="left", suffixes=("", "_enriched"))

    for semantic_key in [
        "player_id",
        "current_level",
        "current_elo",
        "tracker_highest_elo",
        "lifetime_matches",
    ]:
        existing_col = find_column(merged, COLUMN_ALIASES[semantic_key])
        canonical = f"__{semantic_key}"

        if existing_col is not None:
            merged[canonical] = merged[existing_col]
        else:
            merged[canonical] = 0

    return merged.drop(columns=["_merge_nickname_key"], errors="ignore")


def calculate_scores() -> pd.DataFrame:
    if not SEASON8_STATS_PATH.exists():
        raise FileNotFoundError(f"Season 8 stats file not found: {SEASON8_STATS_PATH}")

    stats_df = pd.read_csv(SEASON8_STATS_PATH)

    if PLAYERS_ENRICHED_PATH.exists():
        players_df = pd.read_csv(PLAYERS_ENRICHED_PATH)
        df = merge_context_data(stats_df, players_df)
    else:
        print(f"[WARN] Enriched players file not found: {PLAYERS_ENRICHED_PATH}")
        df = stats_df.copy()

        for key in ["player_id", "current_level", "current_elo", "tracker_highest_elo", "lifetime_matches"]:
            df[f"__{key}"] = 0

    manual_roles = load_manual_roles(MANUAL_ROLES_PATH)

    nickname = get_text_series(df, "nickname")
    player_id = get_text_series(df, "player_id")

    matches = get_series(df, "matches")
    kd = get_series(df, "kd")
    kr = get_series(df, "kr")
    adr = get_series(df, "adr")
    hs = get_series(df, "hs")

    entry_rate = get_series(df, "entry_rate")
    entry_success = get_series(df, "entry_success")

    utility_success = get_series(df, "utility_success")
    utility_damage_round = get_series(df, "utility_damage_round")
    enemies_flashed_round = get_series(df, "enemies_flashed_round")
    flash_success = get_series(df, "flash_success")
    utility_usage_round = get_series(df, "utility_usage_round")
    flashes_round = get_series(df, "flashes_round")

    win_rate = get_series(df, "win_rate")

    one_v_one_count = get_series(df, "one_v_one_count")
    one_v_one_wins = get_series(df, "one_v_one_wins")
    one_v_two_count = get_series(df, "one_v_two_count")
    one_v_two_wins = get_series(df, "one_v_two_wins")

    current_level = pd.to_numeric(df.get("__current_level", 0), errors="coerce").fillna(0)
    current_elo = pd.to_numeric(df.get("__current_elo", 0), errors="coerce").fillna(0)
    tracker_highest_elo = pd.to_numeric(df.get("__tracker_highest_elo", 0), errors="coerce").fillna(0)
    lifetime_matches = pd.to_numeric(df.get("__lifetime_matches", 0), errors="coerce").fillna(0)

    # Fallback: if tracker peak is missing, use current ELO to avoid EXP becoming zero.
    known_peak_elo = tracker_highest_elo.where(tracker_highest_elo > 0, current_elo)

    active_mask = matches >= MIN_SEASON8_MATCHES
    status = active_mask.map(lambda is_active: "ACTIVE" if is_active else "INACTIVE")

    kd_score = normalize_rate(kd, active_mask)
    kr_score = normalize_rate(kr, active_mask)
    adr_score = normalize_rate(adr, active_mask)
    hs_score = normalize_rate(hs, active_mask)

    entry_rate_score = normalize_rate(entry_rate, active_mask)
    entry_success_score = normalize_rate(entry_success, active_mask)

    utility_success_score = normalize_rate(utility_success, active_mask)
    utility_damage_round_score = normalize_rate(utility_damage_round, active_mask)
    enemies_flashed_round_score = normalize_rate(enemies_flashed_round, active_mask)
    flash_success_score = normalize_rate(flash_success, active_mask)
    utility_usage_round_score = normalize_rate(utility_usage_round, active_mask)
    flashes_round_score = normalize_rate(flashes_round, active_mask)

    win_rate_score = normalize_rate(win_rate, active_mask)

    season8_matches_volume_score = normalize_volume(matches, active_mask)

    one_v_one_win_rate = safe_ratio(one_v_one_wins, one_v_one_count)
    one_v_two_win_rate = safe_ratio(one_v_two_wins, one_v_two_count)
    clutch_volume = one_v_one_count + one_v_two_count

    one_v_one_win_rate_score = normalize_rate(one_v_one_win_rate, active_mask)
    one_v_two_win_rate_score = normalize_rate(one_v_two_win_rate, active_mask)
    clutch_volume_score = normalize_volume(clutch_volume, active_mask)

    clutch_score = weighted_sum(
        [
            (one_v_one_win_rate_score, 0.50),
            (one_v_two_win_rate_score, 0.30),
            (clutch_volume_score, 0.20),
        ]
    )

    peak_elo_score = normalize_rate(known_peak_elo, active_mask)
    lifetime_matches_volume_score = normalize_volume(lifetime_matches, active_mask)

    aim = weighted_sum(
        [
            (kd_score, 0.35),
            (kr_score, 0.25),
            (adr_score, 0.25),
            (hs_score, 0.15),
        ]
    )

    imp = weighted_sum(
        [
            (adr_score, 0.30),
            (kr_score, 0.25),
            (entry_success_score, 0.20),
            (entry_rate_score, 0.15),
            (clutch_score, 0.10),
        ]
    )

    utl = weighted_sum(
        [
            (utility_success_score, 0.25),
            (utility_damage_round_score, 0.20),
            (enemies_flashed_round_score, 0.20),
            (flash_success_score, 0.15),
            (utility_usage_round_score, 0.10),
            (flashes_round_score, 0.10),
        ]
    )

    performance_consistency = weighted_sum(
        [
            (kd_score, 0.40),
            (kr_score, 0.30),
            (win_rate_score, 0.30),
        ]
    )

    con = weighted_sum(
        [
            (season8_matches_volume_score, 0.65),
            (performance_consistency, 0.35),
        ]
    )

    intelligence = weighted_sum(
        [
            (clutch_score, 0.70),
            (entry_success_score, 0.15),
            (utility_success_score, 0.15),
        ]
    )

    exp = weighted_sum(
        [
            (peak_elo_score, 0.40),
            (lifetime_matches_volume_score, 0.60),
        ]
    )

    base_overall = weighted_sum(
        [
            (aim, 0.25),
            (imp, 0.25),
            (utl, 0.10),
            (con, 0.18),
            (intelligence, 0.12),
            (exp, 0.10),
        ]
    )

    level_multiplier = current_level.round().clip(lower=1, upper=10).astype(int).map(LEVEL_MULTIPLIER).fillna(1.0)
    overall = (base_overall * level_multiplier).clip(lower=0, upper=MAX_OVERALL)

    for series in [
        aim,
        imp,
        utl,
        con,
        intelligence,
        exp,
        base_overall,
        overall,
        clutch_score,
        performance_consistency,
    ]:
        series.loc[~active_mask] = 0

    role = nickname.str.lower().map(manual_roles).fillna("RIFLER")

    output = pd.DataFrame(
        {
            "faceit_nickname": nickname,
            "faceit_player_id": player_id,
            "status": status,
            "role": role,
            "season8_matches": matches.astype(int),
            "current_faceit_level": current_level.fillna(0).astype(int),
            "current_faceit_elo": current_elo.fillna(0).astype(int),
            "faceit_tracker_highest_elo": tracker_highest_elo.fillna(0).astype(int),
            "known_peak_elo": known_peak_elo.fillna(0).astype(int),
            "lifetime_faceit_matches": lifetime_matches.fillna(0).astype(int),
            "AIM": aim.round(2),
            "IMP": imp.round(2),
            "UTL": utl.round(2),
            "CON": con.round(2),
            "INT": intelligence.round(2),
            "EXP": exp.round(2),
            "BASE_OVERALL": base_overall.round(2),
            "FACEIT_LEVEL_MULTIPLIER": level_multiplier.round(2),
            "OVERALL": overall.round(0).astype(int),
            "KD_score": kd_score.round(2),
            "KR_score": kr_score.round(2),
            "ADR_score": adr_score.round(2),
            "HS_score": hs_score.round(2),
            "EntryRate_score": entry_rate_score.round(2),
            "EntrySuccess_score": entry_success_score.round(2),
            "UtilitySuccess_score": utility_success_score.round(2),
            "UtilityDamageRound_score": utility_damage_round_score.round(2),
            "EnemiesFlashedRound_score": enemies_flashed_round_score.round(2),
            "FlashSuccess_score": flash_success_score.round(2),
            "UtilityUsageRound_score": utility_usage_round_score.round(2),
            "FlashesRound_score": flashes_round_score.round(2),
            "WinRate_score": win_rate_score.round(2),
            "Season8MatchesVolume_score": season8_matches_volume_score.round(2),
            "PerformanceConsistency_score": performance_consistency.round(2),
            "OneVOneWinRate_score": one_v_one_win_rate_score.round(2),
            "OneVTwoWinRate_score": one_v_two_win_rate_score.round(2),
            "ClutchVolume_score": clutch_volume_score.round(2),
            "ClutchScore": clutch_score.round(2),
            "PeakElo_score": peak_elo_score.round(2),
            "LifetimeMatchesVolume_score": lifetime_matches_volume_score.round(2),
        }
    )

    output["status_sort"] = output["status"].map({"ACTIVE": 0, "INACTIVE": 1}).fillna(2)

    output = output.sort_values(
        by=["status_sort", "OVERALL", "season8_matches"],
        ascending=[True, False, False],
    ).drop(columns=["status_sort"])

    return output


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    scores = calculate_scores()
    scores.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    active_count = int((scores["status"] == "ACTIVE").sum())
    inactive_count = int((scores["status"] == "INACTIVE").sum())

    print(f"[OK] BRz Card scores generated: {OUTPUT_PATH}")
    print(f"[INFO] Active players: {active_count}")
    print(f"[INFO] Inactive players: {inactive_count}")
    print(f"[INFO] Minimum Season 8 matches: {MIN_SEASON8_MATCHES}")


if __name__ == "__main__":
    main()
