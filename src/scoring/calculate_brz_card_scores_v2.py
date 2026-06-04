"""
BRz Cards scoring v2 — Refactored.

Scoring model (post-refactoring):
- Uses FACEIT Season 8 as the main performance window for AIM, UTL, INT, EXP.
- Uses incremental cache (match_rounds) for IMP (accumulating) and CON (sliding 30).
- Players need at least 20 Season 8 matches to become ACTIVE.
- INACTIVE players receive zeroed stats and do not participate in normalization.
- 4 stats use S-Curve normalization (AIM, IMP, UTL, EXP) — relative, floor 50.
- 2 stats are absolute (CON, INT) — can go below 50.
- OVERALL uses continuous CONTEXT_MULTIPLIER (opponent ELO) + rating anchor.
- Roles are manual and do not affect OVERALL.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"

SEASON8_STATS_PATH = DATA_DIR / "brz_faceit_season8_stats.csv"
PLAYERS_ENRICHED_PATH = DATA_DIR / "brz_faceit_players_enriched.csv"
MANUAL_ROLES_PATH = DATA_DIR / "brz_manual_roles.csv"
CACHE_DIR = DATA_DIR / "cache" / "faceit_match_rounds"
OUTPUT_PATH = DATA_DIR / "brz_card_scores_v2.csv"

MIN_SEASON8_MATCHES = 20
MAX_OVERALL = 99

# ---------------------------------------------------------------------------
# Tuning dials — named constants, easy to adjust
# ---------------------------------------------------------------------------

# S-Curve normalization parameters
SCURVE_FLOOR = 50
SCURVE_CEILING = 99
SCURVE_K = 6        # Steepness: higher = more sigmoid spread; lower = more linear

# AIM weights
AIM_W_ADR = 0.42
AIM_W_HS = 0.35
AIM_W_KR = 0.23

# UTL weights
UTL_W_UTIL_SUCCESS = 0.30
UTL_W_UTIL_DAMAGE = 0.22
UTL_W_FLASH_SUCCESS = 0.28
UTL_W_ENEMIES_FLASHED = 0.20

# CON formula coefficients (calibrated for 30-match window)
CON_INTERCEPT = 121
CON_SLOPE = 265
CON_WINDOW = 30      # Sliding window size

# INT weights
INT_W_1V2 = 0.75
INT_W_1V1 = 0.25

# OVERALL stat weights
OVERALL_W_AIM = 0.24
OVERALL_W_IMP = 0.24
OVERALL_W_UTL = 0.10
OVERALL_W_CON = 0.20
OVERALL_W_INT = 0.12
OVERALL_W_EXP = 0.10

# Context multiplier (replaces discrete LEVEL_MULTIPLIER)
CONTEXT_BETA = 0.4    # Exponent for ELO ratio
CONTEXT_CLAMP_LO = 0.80
CONTEXT_CLAMP_HI = 1.12

# Rating anchor strength
RATING_ANCHOR_K = 0.15


# ---------------------------------------------------------------------------
# Column aliases (unchanged from original)
# ---------------------------------------------------------------------------

COLUMN_ALIASES = {
    "nickname": [
        "faceit_nickname",
        "nickname",
        "Nickname",
        "player_nickname",
        "faceit_nickname_official",
        "faceit_nickname_input",
    ],
    "country": [
        "country",
        "Country",
        "country_code",
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
        "Average Headshots %",
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


# ---------------------------------------------------------------------------
# Column resolution helpers (unchanged)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# S-Curve normalization (replaces normalize_rate for relative stats)
# ---------------------------------------------------------------------------

def _sigmoid(z: float, k: float = SCURVE_K) -> float:
    """Logistic sigmoid centered at 0.5."""
    return 1.0 / (1.0 + math.exp(-k * (z - 0.5)))


def normalize_scurve(
    series: pd.Series,
    active_mask: pd.Series,
    floor: float = SCURVE_FLOOR,
    ceiling: float = SCURVE_CEILING,
    k: float = SCURVE_K,
) -> pd.Series:
    """
    S-Curve normalization anchored on the active player pool.

    For each value x in `series`:
    1. Compute linear position t = clamp((x - lo) / (hi - lo), 0, 1)
    2. Apply sigmoid and rescale to [0, 1]
    3. Map to [floor, ceiling]

    Returns floor for all values if pool has no variance.
    INACTIVE players get 0.
    """
    active_values = series[active_mask].dropna()

    if active_values.empty:
        return pd.Series([0.0] * len(series), index=series.index)

    lo = float(active_values.min())
    hi = float(active_values.max())

    if hi == lo:
        return pd.Series(
            [floor if m else 0.0 for m in active_mask],
            index=series.index,
        )

    sig0 = _sigmoid(0.0, k)
    sig1 = _sigmoid(1.0, k)
    denom = sig1 - sig0

    def _apply(x: float) -> float:
        t = max(0.0, min(1.0, (x - lo) / (hi - lo)))
        curve = (_sigmoid(t, k) - sig0) / denom
        return floor + curve * (ceiling - floor)

    result = series.copy().astype("float64")
    for idx in result.index:
        if active_mask.loc[idx] and pd.notna(series.loc[idx]):
            result.loc[idx] = _apply(float(series.loc[idx]))
        else:
            result.loc[idx] = 0.0

    return result


# ---------------------------------------------------------------------------
# Legacy normalization (kept for reference but no longer used for stats)
# ---------------------------------------------------------------------------

def normalize_rate(series: pd.Series, active_mask: pd.Series) -> pd.Series:
    active_values = series.where(active_mask)
    max_value = active_values.max(skipna=True)

    if pd.isna(max_value) or max_value <= 0:
        return pd.Series([0.0] * len(series), index=series.index)

    return (series / max_value * 100).clip(lower=0, upper=100).fillna(0)


# ---------------------------------------------------------------------------
# Weighted sum helper (unchanged)
# ---------------------------------------------------------------------------

def weighted_sum(parts: list[tuple[pd.Series, float]]) -> pd.Series:
    result = pd.Series([0.0] * len(parts[0][0]), index=parts[0][0].index)

    for series, weight in parts:
        result = result + series.fillna(0) * weight

    return result


# ---------------------------------------------------------------------------
# Role helpers (unchanged)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Cache loading — reads per-player match_rounds JSONs
# ---------------------------------------------------------------------------

def load_cache_data(cache_dir: Path) -> dict[str, dict]:
    """
    Load incremental match-rounds cache for all players.

    Returns a dict keyed by player_id with:
    - round_swing_avg: mean of faceit_round_swing_avg across ALL 5v5 matches (IMP — accumulates)
    - ratings_last_30: list of faceit_rating for last 30 5v5 matches sorted by time (CON — sliding)
    - opp_elo_avg: mean of opponent_team_elo_avg across ALL 5v5 matches (OVERALL context)
    - rating_avg: mean of faceit_rating across ALL 5v5 matches (OVERALL anchor)
    """
    cache_data: dict[str, dict] = {}

    if not cache_dir.exists():
        print(f"[WARN] Cache directory not found: {cache_dir}")
        return cache_data

    for filepath in cache_dir.glob("*.json"):
        player_id = filepath.stem

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[WARN] Failed to load cache for {player_id}: {e}")
            continue

        # Handle two cache formats:
        # 1. Raw API format: {"payload": {"cs2": {"match_rounds": [...]}}}
        # 2. Pre-processed flat list: [{match_data}, ...]
        if isinstance(raw, list):
            matches = raw
        elif isinstance(raw, dict):
            try:
                cs2_data = raw["payload"]["cs2"]
                # Handle both snake_case and camelCase keys
                matches = cs2_data.get("match_rounds") or cs2_data.get("matchRounds") or []
            except (KeyError, TypeError):
                print(f"[WARN] Unexpected dict structure for {player_id}, skipping")
                continue
        else:
            print(f"[WARN] Unknown cache format for {player_id}, skipping")
            continue

        # Filter to 5v5 matches only
        # Normalize camelCase keys to snake_case for consistency
        _CAMEL_TO_SNAKE = {
            "gameMode": "game_mode",
            "endTime": "end_time",
            "faceitRoundSwingAvg": "faceit_round_swing_avg",
            "faceitRoundSwingAvgT": "faceit_round_swing_avg_t",
            "faceitRoundSwingAvgCt": "faceit_round_swing_avg_ct",
            "opponentTeamEloAvg": "opponent_team_elo_avg",
            "faceitRating": "faceit_rating",
            "roundsPlayed": "rounds_played",
        }

        def _normalize_match(m: dict) -> dict:
            """Add snake_case aliases for camelCase keys if missing."""
            for camel, snake in _CAMEL_TO_SNAKE.items():
                if snake not in m and camel in m:
                    m[snake] = m[camel]
            return m

        matches = [_normalize_match(m) for m in matches if isinstance(m, dict)]
        matches_5v5 = [m for m in matches if m.get("game_mode") == "5v5"]

        if not matches_5v5:
            continue

        # Sort by end_time descending (most recent first) for sliding window
        matches_5v5.sort(key=lambda m: m.get("end_time", ""), reverse=True)

        # --- IMP: round_swing_avg from ALL 5v5 matches (accumulates) ---
        swing_values = []
        for m in matches_5v5:
            swing = m.get("faceit_round_swing_avg")
            if swing is not None:
                swing_values.append(float(swing))
            else:
                # Fallback: reconstruct general from T/CT weighted by rounds
                swing_t = m.get("faceit_round_swing_avg_t")
                swing_ct = m.get("faceit_round_swing_avg_ct")
                rounds = m.get("rounds_played", 0)
                if swing_t is not None and swing_ct is not None and rounds > 0:
                    # Approximate 50/50 split since we don't have per-side round counts
                    swing_values.append((float(swing_t) + float(swing_ct)) / 2.0)

        round_swing_avg = statistics.mean(swing_values) if swing_values else None

        # --- CON: ratings from last 30 5v5 matches (sliding window) ---
        rating_values_all = []
        for m in matches_5v5:
            rating = m.get("faceit_rating")
            if rating is not None:
                rating_values_all.append(float(rating))

        ratings_last_30 = rating_values_all[:CON_WINDOW]  # Already sorted most recent first

        # --- OVERALL: opponent ELO avg from ALL 5v5 matches ---
        opp_elo_values = []
        for m in matches_5v5:
            opp_elo = m.get("opponent_team_elo_avg")
            if opp_elo is not None:
                opp_elo_values.append(float(opp_elo))

        opp_elo_avg = statistics.mean(opp_elo_values) if opp_elo_values else None

        # --- OVERALL: rating avg from ALL 5v5 matches ---
        rating_avg = statistics.mean(rating_values_all) if rating_values_all else None

        cache_data[player_id] = {
            "round_swing_avg": round_swing_avg,
            "ratings_last_30": ratings_last_30,
            "opp_elo_avg": opp_elo_avg,
            "rating_avg": rating_avg,
        }

    return cache_data


# ---------------------------------------------------------------------------
# Merge context data (unchanged from original)
# ---------------------------------------------------------------------------

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
            enriched_col = f"{existing_col}_enriched"
            if enriched_col in merged.columns:
                merged[canonical] = merged[enriched_col].combine_first(merged[existing_col])
            else:
                merged[canonical] = merged[existing_col]
        else:
            merged[canonical] = 0

    return merged.drop(columns=["_merge_nickname_key"], errors="ignore")


# ---------------------------------------------------------------------------
# CON calculation (absolute — no S-Curve)
# ---------------------------------------------------------------------------

def calculate_con(ratings: list[float]) -> int:
    """
    CON = round(clamp(121 - 265 * CV, 0, 99))

    Where CV = std(ratings) / mean(ratings) for the last 30 matches.
    Uses the FACEIT performance Rating (scale ~0.4–1.7), NOT ELO.
    """
    if len(ratings) < 2:
        return 0

    mean_r = statistics.mean(ratings)

    if mean_r <= 0:
        return 0

    std_r = statistics.pstdev(ratings)  # Population std (we have the full window)
    cv = std_r / mean_r

    raw = CON_INTERCEPT - CON_SLOPE * cv
    clamped = max(0.0, min(99.0, raw))

    return round(clamped)


# ---------------------------------------------------------------------------
# INT calculation (moved inside calculate_scores as it uses pool S-Curve)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def calculate_scores() -> pd.DataFrame:
    if not SEASON8_STATS_PATH.exists():
        raise FileNotFoundError(f"Season 8 stats file not found: {SEASON8_STATS_PATH}")

    stats_df = pd.read_csv(SEASON8_STATS_PATH)

    if PLAYERS_ENRICHED_PATH.exists():
        players_df = pd.read_csv(PLAYERS_ENRICHED_PATH, dtype=object)
        df = merge_context_data(stats_df, players_df)
    else:
        print(f"[WARN] Enriched players file not found: {PLAYERS_ENRICHED_PATH}")
        df = stats_df.copy()

        for key in ["player_id", "current_level", "current_elo", "tracker_highest_elo", "lifetime_matches"]:
            df[f"__{key}"] = 0

    # Load cache data for IMP, CON, and OVERALL
    cache_data = load_cache_data(CACHE_DIR)

    manual_roles = load_manual_roles(MANUAL_ROLES_PATH)

    # -----------------------------------------------------------------------
    # Extract raw series
    # -----------------------------------------------------------------------
    nickname = get_text_series(df, "nickname")
    player_id = get_text_series(df, "player_id")
    country = get_text_series(df, "country", default="BR")

    matches = get_series(df, "matches")

    # AIM fields (Season 8)
    adr = get_series(df, "adr")
    hs = get_series(df, "hs")
    kr = get_series(df, "kr")

    # UTL fields (Season 8)
    utility_success = get_series(df, "utility_success")
    utility_damage_round = get_series(df, "utility_damage_round")
    flash_success = get_series(df, "flash_success")
    enemies_flashed_round = get_series(df, "enemies_flashed_round")

    # INT fields (Season 8)
    one_v_one_count = get_series(df, "one_v_one_count")
    one_v_one_wins = get_series(df, "one_v_one_wins")
    one_v_two_count = get_series(df, "one_v_two_count")
    one_v_two_wins = get_series(df, "one_v_two_wins")

    # EXP fields
    current_elo = pd.to_numeric(df.get("__current_elo", 0), errors="coerce").fillna(0)
    tracker_highest_elo = pd.to_numeric(df.get("__tracker_highest_elo", 0), errors="coerce").fillna(0)
    current_level = pd.to_numeric(df.get("__current_level", 0), errors="coerce").fillna(0)
    lifetime_matches = pd.to_numeric(df.get("__lifetime_matches", 0), errors="coerce").fillna(0)

    # Fallback: if tracker peak is missing, use current ELO
    known_peak_elo = tracker_highest_elo.where(tracker_highest_elo > 0, current_elo)

    # -----------------------------------------------------------------------
    # ACTIVE/INACTIVE mask
    # -----------------------------------------------------------------------
    active_mask = matches >= MIN_SEASON8_MATCHES
    status = active_mask.map(lambda is_active: "ACTIVE" if is_active else "INACTIVE")

    # -----------------------------------------------------------------------
    # Map cache data to DataFrame rows (by player_id)
    # -----------------------------------------------------------------------
    round_swing_series = pd.Series([0.0] * len(df), index=df.index, dtype="float64")
    con_ratings_map: dict[int, list[float]] = {}  # idx -> ratings list
    opp_elo_series = pd.Series([np.nan] * len(df), index=df.index, dtype="float64")
    rating_avg_series = pd.Series([np.nan] * len(df), index=df.index, dtype="float64")

    for idx in df.index:
        pid = str(player_id.loc[idx]).strip()
        if pid in cache_data:
            cd = cache_data[pid]
            if cd["round_swing_avg"] is not None:
                round_swing_series.loc[idx] = cd["round_swing_avg"]
            con_ratings_map[idx] = cd.get("ratings_last_30", [])
            if cd["opp_elo_avg"] is not None:
                opp_elo_series.loc[idx] = cd["opp_elo_avg"]
            if cd["rating_avg"] is not None:
                rating_avg_series.loc[idx] = cd["rating_avg"]
        else:
            con_ratings_map[idx] = []

    # -----------------------------------------------------------------------
    # AIM — S-Curve on each component, then weighted sum
    # -----------------------------------------------------------------------
    adr_norm = normalize_scurve(adr, active_mask)
    hs_norm = normalize_scurve(hs, active_mask)
    kr_norm = normalize_scurve(kr, active_mask)

    aim = weighted_sum([
        (adr_norm, AIM_W_ADR),
        (hs_norm, AIM_W_HS),
        (kr_norm, AIM_W_KR),
    ])

    # -----------------------------------------------------------------------
    # IMP — single field: round_swing from cache (S-Curve)
    # -----------------------------------------------------------------------
    imp = normalize_scurve(round_swing_series, active_mask)

    # -----------------------------------------------------------------------
    # UTL — S-Curve on each component, then weighted sum
    # -----------------------------------------------------------------------
    util_success_norm = normalize_scurve(utility_success, active_mask)
    util_damage_norm = normalize_scurve(utility_damage_round, active_mask)
    flash_success_norm = normalize_scurve(flash_success, active_mask)
    enemies_flashed_norm = normalize_scurve(enemies_flashed_round, active_mask)

    utl = weighted_sum([
        (util_success_norm, UTL_W_UTIL_SUCCESS),
        (util_damage_norm, UTL_W_UTIL_DAMAGE),
        (flash_success_norm, UTL_W_FLASH_SUCCESS),
        (enemies_flashed_norm, UTL_W_ENEMIES_FLASHED),
    ])

    # -----------------------------------------------------------------------
    # CON — absolute formula (no S-Curve), from cache ratings
    # -----------------------------------------------------------------------
    con = pd.Series([0.0] * len(df), index=df.index, dtype="float64")
    for idx in df.index:
        if active_mask.loc[idx]:
            ratings = con_ratings_map.get(idx, [])
            con.loc[idx] = float(calculate_con(ratings))

    # -----------------------------------------------------------------------
    # INT — S-Curve on pure clutch win rates with pool-mean imputation
    # -----------------------------------------------------------------------
    # Calculate raw win rates only where count > 0, otherwise NaN
    winrate_1v1 = pd.Series(np.nan, index=df.index, dtype="float64")
    winrate_1v2 = pd.Series(np.nan, index=df.index, dtype="float64")

    mask_1v1 = (active_mask) & (one_v_one_count > 0)
    mask_1v2 = (active_mask) & (one_v_two_count > 0)

    winrate_1v1.loc[mask_1v1] = one_v_one_wins.loc[mask_1v1] / one_v_one_count.loc[mask_1v1]
    winrate_1v2.loc[mask_1v2] = one_v_two_wins.loc[mask_1v2] / one_v_two_count.loc[mask_1v2]

    # Calculate active pool means for active players with Count > 0
    pool_mean_1v1 = float(winrate_1v1[mask_1v1].mean()) if mask_1v1.any() else 0.0
    pool_mean_1v2 = float(winrate_1v2[mask_1v2].mean()) if mask_1v2.any() else 0.0

    filled_winrate_1v1 = winrate_1v1.copy()
    filled_winrate_1v2 = winrate_1v2.copy()

    # For active players, if they have Count == 0, impute the pool mean
    filled_winrate_1v1.loc[active_mask & (one_v_one_count <= 0)] = pool_mean_1v1
    filled_winrate_1v2.loc[active_mask & (one_v_two_count <= 0)] = pool_mean_1v2

    # Calculate INT bruto using filled win rates
    int_bruto = INT_W_1V2 * filled_winrate_1v2 + INT_W_1V1 * filled_winrate_1v1

    # S-Curve normalization relative to the pool
    intelligence = normalize_scurve(int_bruto, active_mask)

    # Store sub-scores for diagnostics
    int_score_1v1_series = filled_winrate_1v1.fillna(0.0)
    int_score_1v2_series = filled_winrate_1v2.fillna(0.0)

    # -----------------------------------------------------------------------
    # EXP — peak ELO only (S-Curve)
    # -----------------------------------------------------------------------
    exp = normalize_scurve(known_peak_elo, active_mask)

    # -----------------------------------------------------------------------
    # OVERALL — new formula with CONTEXT_MULT + rating anchor
    # -----------------------------------------------------------------------

    # Step 1: base overall
    base_overall = weighted_sum([
        (aim, OVERALL_W_AIM),
        (imp, OVERALL_W_IMP),
        (utl, OVERALL_W_UTL),
        (con, OVERALL_W_CON),
        (intelligence, OVERALL_W_INT),
        (exp, OVERALL_W_EXP),
    ])

    # Step 2: CONTEXT_MULT from opponent ELO
    # E_ref = median of opp_elo_avg among ACTIVE players
    active_opp_elo = opp_elo_series[active_mask].dropna()
    e_ref = float(active_opp_elo.median()) if len(active_opp_elo) > 0 else 1.0

    context_mult = pd.Series([1.0] * len(df), index=df.index, dtype="float64")
    for idx in df.index:
        if active_mask.loc[idx] and pd.notna(opp_elo_series.loc[idx]) and e_ref > 0:
            ratio = float(opp_elo_series.loc[idx]) / e_ref
            raw_mult = ratio ** CONTEXT_BETA
            context_mult.loc[idx] = max(CONTEXT_CLAMP_LO, min(CONTEXT_CLAMP_HI, raw_mult))

    overall_dif = base_overall * context_mult

    # Step 3: Rating anchor
    # Normalize faceit_rating to 0–99 via S-Curve on the pool
    rating_norm = normalize_scurve(rating_avg_series, active_mask)

    overall_final = overall_dif + RATING_ANCHOR_K * (rating_norm - overall_dif)

    overall = overall_final.clip(lower=0, upper=MAX_OVERALL).round(0).astype(int)

    # -----------------------------------------------------------------------
    # Zero out INACTIVE players
    # -----------------------------------------------------------------------
    for series in [
        aim, imp, utl, con, intelligence, exp,
        base_overall, overall_final, overall,
        context_mult, rating_norm,
    ]:
        series.loc[~active_mask] = 0

    # -----------------------------------------------------------------------
    # Roles
    # -----------------------------------------------------------------------
    role = nickname.str.lower().map(manual_roles).fillna("RIFLER")

    # -----------------------------------------------------------------------
    # Build output DataFrame
    # -----------------------------------------------------------------------
    output = pd.DataFrame(
        {
            "faceit_nickname": nickname,
            "faceit_player_id": player_id,
            "country": country,
            "status": status,
            "role": role,
            "season8_matches": matches.astype(int),
            "current_faceit_level": current_level.fillna(0).astype(int),
            "current_faceit_elo": current_elo.fillna(0).astype(int),
            "faceit_tracker_highest_elo": tracker_highest_elo.fillna(0).astype(int),
            "known_peak_elo": known_peak_elo.fillna(0).astype(int),
            "lifetime_faceit_matches": lifetime_matches.fillna(0).astype(int),
            # --- Final stats (integers) ---
            "AIM": aim.round(0).astype(int),
            "IMP": imp.round(0).astype(int),
            "UTL": utl.round(0).astype(int),
            "CON": con.round(0).astype(int),
            "INT": intelligence.round(0).astype(int),
            "EXP": exp.round(0).astype(int),
            "OVERALL": overall,
            # --- OVERALL diagnostic columns ---
            "BASE_OVERALL": base_overall.round(2),
            "CONTEXT_MULT": context_mult.round(4),
            "RATING_NORM": rating_norm.round(2),
            "OPP_ELO_AVG": opp_elo_series.round(0).fillna(0).astype(int),
            # --- AIM component scores ---
            "ADR_norm": adr_norm.round(2),
            "HS_norm": hs_norm.round(2),
            "KR_norm": kr_norm.round(2),
            # --- IMP diagnostic ---
            "RoundSwing_avg": round_swing_series.round(6),
            # --- UTL component scores ---
            "UtilSuccess_norm": util_success_norm.round(2),
            "UtilDamageRound_norm": util_damage_norm.round(2),
            "FlashSuccess_norm": flash_success_norm.round(2),
            "EnemiesFlashedRound_norm": enemies_flashed_norm.round(2),
            # --- CON diagnostic ---
            "CON_raw": con.round(2),
            # --- INT diagnostic ---
            "INT_score_1v1": int_score_1v1_series.round(4),
            "INT_score_1v2": int_score_1v2_series.round(4),
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

    # Print a summary of active player stats for quick validation
    active = scores[scores["status"] == "ACTIVE"]
    if not active.empty:
        for stat in ["AIM", "IMP", "UTL", "CON", "INT", "EXP", "OVERALL"]:
            col = active[stat]
            print(f"[INFO] {stat}: min={col.min()}, max={col.max()}, mean={col.mean():.1f}, median={col.median():.1f}")


if __name__ == "__main__":
    main()
