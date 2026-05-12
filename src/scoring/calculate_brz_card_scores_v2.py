try:
    from scoring.competitive_scaling import (
        normalize_adr,
        normalize_kd,
        normalize_hs,
        normalize_entry_success,
        normalize_entry_rate,
    )
except ModuleNotFoundError:
    from competitive_scaling import (
        normalize_adr,
        normalize_kd,
        normalize_hs,
        normalize_entry_success,
        normalize_entry_rate,
    )

from pathlib import Path

import pandas as pd


LIFETIME_STATS_CSV_PATH = Path("data/brz_faceit_lifetime_stats.csv")
PERCENTILES_CSV_PATH = Path("data/brz_metric_percentiles.csv")
OUTPUT_CSV_PATH = Path("data/brz_card_scores_v2.csv")


def safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_percentiles(path: Path) -> dict:
    df = pd.read_csv(path)

    percentiles = {}

    for _, row in df.iterrows():
        metric = row["metric"]
        percentiles[metric] = {
            "min": safe_float(row["min"]),
            "p10": safe_float(row["p10"]),
            "p25": safe_float(row["p25"]),
            "p50": safe_float(row["p50"]),
            "p75": safe_float(row["p75"]),
            "p90": safe_float(row["p90"]),
            "p95": safe_float(row["p95"]),
            "max": safe_float(row["max"]),
            "mean": safe_float(row["mean"]),
        }

    return percentiles


def normalize_by_percentile(value, metric: str, percentiles: dict) -> float:
    """
    Convert a raw FACEIT metric into a 0-100 BRz percentile-based score.

    The idea is:
    - p10 or below => close to 0
    - p50 => around 50
    - p90 or above => around 90+
    - max => 100
    """
    value = safe_float(value)

    if metric not in percentiles:
        return 0.0

    p = percentiles[metric]

    points = [
        (p["min"], 0.0),
        (p["p10"], 10.0),
        (p["p25"], 25.0),
        (p["p50"], 50.0),
        (p["p75"], 75.0),
        (p["p90"], 90.0),
        (p["p95"], 95.0),
        (p["max"], 100.0),
    ]

    # If all values are equal, avoid division by zero.
    if points[0][0] == points[-1][0]:
        return 50.0

    if value <= points[0][0]:
        return 0.0

    if value >= points[-1][0]:
        return 100.0

    for index in range(len(points) - 1):
        x1, y1 = points[index]
        x2, y2 = points[index + 1]

        if x1 <= value <= x2:
            if x2 == x1:
                return y2

            ratio = (value - x1) / (x2 - x1)
            return y1 + ratio * (y2 - y1)

    return 0.0


def weighted_score(parts: list[tuple[float, float]]) -> float:
    """
    Calculate weighted score.

    parts = [
        (normalized_metric_score, weight),
        ...
    ]
    """
    total_weight = sum(weight for _, weight in parts)

    if total_weight == 0:
        return 0.0

    score = sum(value * weight for value, weight in parts) / total_weight
    return round(score, 2)


def recent_results_score(value) -> float:
    """
    Convert FACEIT Recent Results into a 0-100 score.

    Expected CSV format after export:
    "1|0|0|1|0"
    """
    if pd.isna(value) or not str(value).strip():
        return 0.0

    results = str(value).split("|")
    numeric_results = []

    for item in results:
        try:
            numeric_results.append(int(item))
        except ValueError:
            continue

    if not numeric_results:
        return 0.0

    return round((sum(numeric_results) / len(numeric_results)) * 100, 2)


def calculate_core_scores(row: pd.Series, percentiles: dict) -> dict:
    hs = normalize_hs(
        safe_float(row.get("Average Headshots %")),
    )

    kd = normalize_kd(
        safe_float(row.get("Average K/D Ratio")),
    )

    adr = normalize_adr(
        safe_float(row.get("ADR")),
    )

    entry_success = normalize_entry_success(
        safe_float(row.get("Entry Success Rate")),
    )

    entry_rate = normalize_entry_rate(
        safe_float(row.get("Entry Rate")),
    )
    utility_damage = normalize_by_percentile(
        row.get("Utility Damage per Round"),
        "Utility Damage per Round",
        percentiles,
    )
    utility_success = normalize_by_percentile(
        row.get("Utility Success Rate"),
        "Utility Success Rate",
        percentiles,
    )
    flash_success = normalize_by_percentile(
        row.get("Flash Success Rate"),
        "Flash Success Rate",
        percentiles,
    )
    enemies_flashed = normalize_by_percentile(
        row.get("Enemies Flashed per Round"),
        "Enemies Flashed per Round",
        percentiles,
    )
    win_rate = normalize_by_percentile(
        row.get("Win Rate %"),
        "Win Rate %",
        percentiles,
    )
    longest_streak = normalize_by_percentile(
        row.get("Longest Win Streak"),
        "Longest Win Streak",
        percentiles,
    )
    current_form = recent_results_score(row.get("Recent Results"))
    clutch_1v1 = normalize_by_percentile(
        row.get("1v1 Win Rate"),
        "1v1 Win Rate",
        percentiles,
    )
    clutch_1v2 = normalize_by_percentile(
        row.get("1v2 Win Rate"),
        "1v2 Win Rate",
        percentiles,
    )
    matches = normalize_by_percentile(
        row.get("Matches"),
        "Matches",
        percentiles,
    )
    rounds = normalize_by_percentile(
        row.get("Total Rounds with extended stats"),
        "Total Rounds with extended stats",
        percentiles,
    )
    elo = safe_float(row.get("cs2_faceit_elo"))

    # Temporary ELO normalization based on this cohort.
    # Later, we can include ELO in the percentiles file too.
    elo_score = min(max((elo - 800) / (2300 - 800) * 100, 0), 100)

    aim = weighted_score(
        [
            (hs, 0.40),
            (kd, 0.35),
            (adr, 0.25),
        ]
    )

    imp = weighted_score(
        [
            (adr, 0.40),
            (entry_success, 0.35),
            (entry_rate, 0.25),
        ]
    )

    utl = weighted_score(
        [
            (utility_damage, 0.40),
            (flash_success, 0.30),
            (utility_success, 0.30),
        ]
    )

    con = weighted_score(
        [
            (win_rate, 0.50),
            (longest_streak, 0.30),
            (current_form, 0.20),
        ]
    )

    clt = weighted_score(
        [
            (clutch_1v2, 0.70),
            (clutch_1v1, 0.30),
        ]
    )

    exp = weighted_score(
        [
            (matches, 0.50),
            (rounds, 0.30),
            (elo_score, 0.20),
        ]
    )

    overall = weighted_score(
        [
            (aim, 0.18),
            (imp, 0.22),
            (utl, 0.15),
            (con, 0.15),
            (clt, 0.15),
            (exp, 0.15),
        ]
    )

    return {
        "AIM": aim,
        "IMP": imp,
        "UTL": utl,
        "CON": con,
        "CLT": clt,
        "EXP": exp,
        "OVERALL": overall,
        "_normalized": {
            "hs": hs,
            "kd": kd,
            "adr": adr,
            "entry_success": entry_success,
            "entry_rate": entry_rate,
            "utility_damage": utility_damage,
            "utility_success": utility_success,
            "flash_success": flash_success,
            "enemies_flashed": enemies_flashed,
            "win_rate": win_rate,
            "longest_streak": longest_streak,
            "current_form": current_form,
            "clutch_1v1": clutch_1v1,
            "clutch_1v2": clutch_1v2,
            "matches": matches,
            "rounds": rounds,
            "elo_score": elo_score,
        },
    }


def calculate_role(row: pd.Series, scores: dict, percentiles: dict) -> tuple[str, dict]:
    n = scores["_normalized"]

    sniper_kill_rate = normalize_by_percentile(
        row.get("Sniper Kill Rate"),
        "Sniper Kill Rate",
        percentiles,
    )
    sniper_kill_rate_per_round = normalize_by_percentile(
        row.get("Sniper Kill Rate per Round"),
        "Sniper Kill Rate per Round",
        percentiles,
    )
    total_1v1_count = normalize_by_percentile(
        row.get("Total 1v1 Count"),
        "Total 1v1 Count",
        percentiles,
    )
    total_1v2_count = normalize_by_percentile(
        row.get("Total 1v2 Count"),
        "Total 1v2 Count",
        percentiles,
    )
    utility_usage = normalize_by_percentile(
        row.get("Utility Usage per Round"),
        "Utility Usage per Round",
        percentiles,
    )

    entry_score = weighted_score(
        [
            (n["entry_rate"], 0.45),
            (n["entry_success"], 0.35),
            (n["adr"], 0.20),
        ]
    )

    sup_score = weighted_score(
        [
            (n["utility_success"], 0.30),
            (n["flash_success"], 0.25),
            (n["enemies_flashed"], 0.20),
            (n["utility_damage"], 0.15),
            (utility_usage, 0.10),
        ]
    )

    awper_score = weighted_score(
        [
            (sniper_kill_rate_per_round, 0.60),
            (sniper_kill_rate, 0.25),
            (n["kd"], 0.15),
        ]
    )

    clutcher_score = weighted_score(
        [
            (n["clutch_1v2"], 0.40),
            (n["clutch_1v1"], 0.30),
            (total_1v2_count, 0.15),
            (total_1v1_count, 0.15),
        ]
    )

    rifler_score = weighted_score(
        [
            (n["kd"], 0.30),
            (n["adr"], 0.25),
            (n["hs"], 0.20),
            (n["entry_success"], 0.15),
            (n["win_rate"], 0.10),
        ]
    )

    lurker_base = weighted_score(
        [
            (n["clutch_1v1"], 0.30),
            (n["kd"], 0.25),
            (n["adr"], 0.20),
            (n["entry_success"], 0.15),
            (n["win_rate"], 0.10),
        ]
    )

    # Penalize lurker if player has very high entry rate.
    lurker_penalty = 15 if n["entry_rate"] >= 75 else 0
    lurker_score = max(lurker_base - lurker_penalty, 0)

    matches_score = normalize_by_percentile(
        row.get("Matches"),
        "Matches",
        percentiles,
    )

    igl_score = weighted_score(
        [
            (scores["EXP"], 0.30),
            (matches_score, 0.20),
            (n["utility_success"], 0.20),
            (n["win_rate"], 0.15),
            (n["flash_success"], 0.10),
            (n["longest_streak"], 0.05),
        ]
    )

    # Safety rule: do not infer IGL if experience is too low.
    if scores["EXP"] < 60:
        igl_score *= 0.75

    role_scores = {
        "IGL": igl_score,
        "AWPER": awper_score,
        "ENTRY": entry_score,
        "SUP": sup_score,
        "LURKER": lurker_score,
        "RIFLER": rifler_score,
        "CLUTCHER": clutcher_score,
    }

    max_role = max(role_scores, key=role_scores.get)
    max_score = role_scores[max_role]

    # If no role is strong enough, use RIFLER as fallback.
    if max_score < 65:
        return "RIFLER", role_scores

    # If ENTRY is elite and almost tied with SUP, prioritize ENTRY.
    # This avoids classifying aggressive impact players as support only because
    # their utility score is also very high.
    if (
        entry_score >= 80
        and sup_score >= entry_score
        and sup_score - entry_score <= 3
    ):
        return "ENTRY", role_scores
    

    igl_score = role_scores["IGL"]

# IGL should win close disputes against AWPER or ENTRY only when
# the IGL score is strong enough. This avoids weak IGL inference.
    if (
        igl_score >= 68
        and max_role in ["AWPER", "ENTRY"]
        and max_score - igl_score <= 3
    ):
        return "IGL", role_scores

    # If IGL is the highest score but not strong enough, do not let it win.
    # Recalculate the best role excluding IGL.
    if max_role == "IGL" and igl_score < 68:
        non_igl_roles = {
            role: score
            for role, score in role_scores.items()
            if role != "IGL"
        }

        max_role = max(non_igl_roles, key=non_igl_roles.get)
        max_score = non_igl_roles[max_role]



    specialized_roles = {
        role: score
        for role, score in role_scores.items()
        if role != "RIFLER"
    }

    best_specialized_role = max(specialized_roles, key=specialized_roles.get)
    best_specialized_score = specialized_roles[best_specialized_role]

    # RIFLER is the generic role.
    # If a specialized role is close to RIFLER, prefer the specialized identity.
    if (
        max_role == "RIFLER"
        and rifler_score - best_specialized_score <= 10
    ):
        return best_specialized_role, role_scores

    return max_role, role_scores


def main() -> None:
    if not LIFETIME_STATS_CSV_PATH.exists():
        raise FileNotFoundError(f"Input CSV not found: {LIFETIME_STATS_CSV_PATH}")

    if not PERCENTILES_CSV_PATH.exists():
        raise FileNotFoundError(f"Percentiles CSV not found: {PERCENTILES_CSV_PATH}")

    df = pd.read_csv(LIFETIME_STATS_CSV_PATH)
    percentiles = load_percentiles(PERCENTILES_CSV_PATH)

    output_rows = []

    for _, row in df.iterrows():
        scores = calculate_core_scores(row, percentiles)
        role, role_scores = calculate_role(row, scores, percentiles)

        output_rows.append(
            {
                "faceit_nickname": row.get("faceit_nickname"),
                "faceit_player_id": row.get("faceit_player_id"),
                "country": row.get("country"),
                "steam_id_64": row.get("steam_id_64"),
                "cs2_skill_level": row.get("cs2_skill_level"),
                "cs2_faceit_elo": row.get("cs2_faceit_elo"),

                "Sniper Kill Rate": row.get("Sniper Kill Rate"),
                "Sniper Kill Rate per Round": row.get("Sniper Kill Rate per Round"),
                "Total Sniper Kills": row.get("Total Sniper Kills"),

                "AIM": scores["AIM"],
                "IMP": scores["IMP"],
                "UTL": scores["UTL"],
                "CON": scores["CON"],
                "CLT": scores["CLT"],
                "EXP": scores["EXP"],
                "OVERALL": scores["OVERALL"],
                "ROLE": role,
                "IGL_SCORE": role_scores["IGL"],
                "AWPER_SCORE": role_scores["AWPER"],
                "ENTRY_SCORE": role_scores["ENTRY"],
                "SUP_SCORE": role_scores["SUP"],
                "LURKER_SCORE": role_scores["LURKER"],
                "RIFLER_SCORE": role_scores["RIFLER"],
                "CLUTCHER_SCORE": role_scores["CLUTCHER"],
            }
        )

    output_df = pd.DataFrame(output_rows)

    output_df = output_df.sort_values(
        by="OVERALL",
        ascending=False,
    )

    OUTPUT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(OUTPUT_CSV_PATH, index=False, encoding="utf-8")

    print(f"Saved BRz Card Scores v2 to: {OUTPUT_CSV_PATH}")
    print()
    print(
        output_df[
            [
                "faceit_nickname",
                "cs2_skill_level",
                "cs2_faceit_elo",
                "AIM",
                "IMP",
                "UTL",
                "CON",
                "CLT",
                "EXP",
                "OVERALL",
                "ROLE",
                "IGL_SCORE",
                "AWPER_SCORE",
                "ENTRY_SCORE",
                "SUP_SCORE",
                "LURKER_SCORE",
                "RIFLER_SCORE",
                "CLUTCHER_SCORE",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()