from pathlib import Path

import pandas as pd


LIFETIME_STATS_CSV_PATH = Path("data/brz_faceit_season8_stats.csv")
PERCENTILES_CSV_PATH = Path("data/brz_metric_percentiles.csv")
OUTPUT_CSV_PATH = Path("data/brz_card_scores_v2.csv")


def safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(value, maximum))


def norm(value, minimum: float, maximum: float) -> float:
    """
    Normalize a raw value into a 0-100 score using a fixed competitive range.
    """
    value = safe_float(value)

    if maximum == minimum:
        return 0.0

    score = ((value - minimum) / (maximum - minimum)) * 100
    return round(clamp(score), 2)


def weighted_score(parts: list[tuple[float, float]]) -> float:
    total_weight = sum(weight for _, weight in parts)

    if total_weight == 0:
        return 0.0

    score = sum(value * weight for value, weight in parts) / total_weight
    return round(score, 2)



def faceit_level_multiplier(level) -> float:
    level = int(safe_float(level))

    multipliers = {
        1: 0.82,
        2: 0.84,
        3: 0.86,
        4: 0.89,
        5: 0.92,
        6: 0.95,
        7: 0.98,
        8: 1.00,
        9: 1.04,
        10: 1.08,
    }

    return multipliers.get(level, 1.00)


def calculate_final_overall(
    base_overall: float,
    role: str,
    role_scores: dict,
    faceit_level,
) -> float:
    main_role_score = role_scores.get(role, 0.0)

    role_adjusted_overall = weighted_score(
        [
            (base_overall, 0.70),
            (main_role_score, 0.30),
        ]
    )

    final_overall = role_adjusted_overall * faceit_level_multiplier(faceit_level)

    return round(min(final_overall, 99), 2)


def recent_win_pct(value) -> float:
    """
    Convert FACEIT Recent Results into win percentage.

    Expected CSV format:
    "1|0|1|1|0"
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


def load_percentiles(path: Path) -> dict:
    """
    Keep percentile support only for role-specific signals like AWPER volume,
    where relative comparison inside the BRz pool is still useful.
    """
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
            return round(y1 + ratio * (y2 - y1), 2)

    return 0.0


def calculate_core_scores(row: pd.Series, percentiles: dict) -> dict:
    kd_raw = safe_float(row.get("Average K/D Ratio"))
    hs_raw = safe_float(row.get("Average Headshots %"))
    adr_raw = safe_float(row.get("ADR"))

    entry_success_raw = safe_float(row.get("Entry Success Rate"))
    entry_rate_raw = safe_float(row.get("Entry Rate"))

    utility_success_raw = safe_float(row.get("Utility Success Rate"))
    utility_damage_raw = safe_float(row.get("Utility Damage per Round"))
    flash_success_raw = safe_float(row.get("Flash Success Rate"))
    enemies_flashed_raw = safe_float(row.get("Enemies Flashed per Round"))

    win_rate_raw = safe_float(row.get("Win Rate %"))
    recent_pct_raw = recent_win_pct(row.get("Recent Results"))

    total_1v1_count = safe_float(row.get("Total 1v1 Count"))
    total_1v1_wins = safe_float(row.get("Total 1v1 Wins"))
    total_1v2_count = safe_float(row.get("Total 1v2 Count"))
    total_1v2_wins = safe_float(row.get("Total 1v2 Wins"))
    total_matches = safe_float(row.get("Total Matches"))

    faceit_elo = safe_float(row.get("cs2_faceit_elo"))
    skill_level = safe_float(row.get("cs2_skill_level"))
    longest_streak = safe_float(row.get("Longest Win Streak"))

    clutch_1v1_rate = (
        total_1v1_wins / total_1v1_count
        if total_1v1_count > 0
        else safe_float(row.get("1v1 Win Rate"))
    )

    clutch_1v2_rate = (
        total_1v2_wins / total_1v2_count
        if total_1v2_count > 0
        else safe_float(row.get("1v2 Win Rate"))
    )

    clutch_volume_rate = (
        (total_1v1_count + total_1v2_count) / total_matches
        if total_matches > 0
        else 0.0
    )

    kd = norm(kd_raw, 0.50, 1.50)
    hs = norm(hs_raw, 20, 70)
    adr = norm(adr_raw, 50, 100)

    entry_success = norm(entry_success_raw, 0.30, 0.60)
    entry_rate = norm(entry_rate_raw, 0.05, 0.25)

    utility_success = norm(utility_success_raw, 0.20, 0.60)
    utility_damage = norm(utility_damage_raw, 3, 10)
    flash_success = norm(flash_success_raw, 0.30, 0.70)
    enemies_flashed = norm(enemies_flashed_raw, 0.20, 0.80)

    win_rate = norm(win_rate_raw, 40, 58)
    current_form = norm(recent_pct_raw, 30, 80)

    clutch_1v1 = norm(clutch_1v1_rate, 0.30, 0.75)
    clutch_1v2 = norm(clutch_1v2_rate, 0.10, 0.45)
    clutch_volume = norm(clutch_volume_rate, 0.10, 1.50)

    if total_1v1_count < 10:
        clutch_1v1 = weighted_score([(clutch_1v1, 0.50), (50, 0.50)])

    if total_1v2_count < 5:
        clutch_1v2 = weighted_score([(clutch_1v2, 0.50), (50, 0.50)])

    elo_score = norm(faceit_elo, 800, 2400)
    skill_level_score = norm(skill_level, 1, 10)
    total_matches_score = norm(total_matches, 0, 2000)
    longest_streak_score = norm(longest_streak, 1, 15)

    aim = weighted_score(
        [
            (kd, 0.40),
            (hs, 0.35),
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
            (utility_success, 0.30),
            (utility_damage, 0.25),
            (flash_success, 0.25),
            (enemies_flashed, 0.20),
        ]
    )

    con = weighted_score(
        [
            (kd, 0.35),
            (win_rate, 0.30),
            (total_matches_score, 0.20),
            (skill_level_score, 0.15),
        ]
    )
    clt = weighted_score(
        [
            (clutch_1v1, 0.50),
            (clutch_1v2, 0.30),
            (clutch_volume, 0.20),
        ]
    )

    exp = weighted_score(
        [
            (elo_score, 0.40),
            (skill_level_score, 0.30),
            (total_matches_score, 0.20),
            (longest_streak_score, 0.10),
        ]
    )

    overall = weighted_score(
        [
            (aim, 0.25),
            (imp, 0.20),
            (utl, 0.15),
            (con, 0.20),
            (clt, 0.10),
            (exp, 0.10),
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
            "kd": kd,
            "hs": hs,
            "adr": adr,
            "entry_success": entry_success,
            "entry_rate": entry_rate,
            "utility_success": utility_success,
            "utility_damage": utility_damage,
            "flash_success": flash_success,
            "enemies_flashed": enemies_flashed,
            "win_rate": win_rate,
            "current_form": current_form,
            "clutch_1v1": clutch_1v1,
            "clutch_1v2": clutch_1v2,
            "clutch_volume": clutch_volume,
            "elo_score": elo_score,
            "skill_level_score": skill_level_score,
            "total_matches_score": total_matches_score,
            "longest_streak": longest_streak_score,
        },
    }


def invert_score(value: float) -> float:
    return round(100 - value, 2)


def calculate_role(row: pd.Series, scores: dict, percentiles: dict) -> tuple[str, dict]:
    n = scores["_normalized"]

    kd_raw = safe_float(row.get("Average K/D Ratio"))
    entry_rate_raw = safe_float(row.get("Entry Rate"))
    entry_success_raw = safe_float(row.get("Entry Success Rate"))
    utility_usage_raw = safe_float(row.get("Utility Usage per Round"))
    flashes_per_round_raw = safe_float(row.get("Flashes per Round"))
    enemies_flashed_raw = safe_float(row.get("Enemies Flashed per Round"))
    win_rate_raw = safe_float(row.get("Win Rate %"))
    sniper_kill_rate_per_round_raw = safe_float(row.get("Sniper Kill Rate per Round"))
    clutch_1v1_rate_raw = safe_float(row.get("1v1 Win Rate"))
    clutch_1v2_rate_raw = safe_float(row.get("1v2 Win Rate"))
    total_1v2_count = safe_float(row.get("Total 1v2 Count"))

    sniper_kill_rate_per_round = norm(sniper_kill_rate_per_round_raw, 0.02, 0.28)
    kd = norm(kd_raw, 0.50, 2.00)

    entry_rate = norm(entry_rate_raw, 0.10, 0.30)
    entry_success = norm(entry_success_raw, 0.30, 0.70)

    utility_usage = norm(utility_usage_raw, 0.30, 1.50)
    flashes_per_round = norm(flashes_per_round_raw, 0.30, 1.50)
    enemies_flashed = norm(enemies_flashed_raw, 0.30, 2.00)

    win_rate = norm(win_rate_raw, 45, 68)

    clutch_1v1 = norm(clutch_1v1_rate_raw, 0.30, 0.78)
    clutch_1v2 = norm(clutch_1v2_rate_raw, 0.10, 0.45)

    aim_role = norm(scores["AIM"], 40, 100)
    imp_role = norm(scores["IMP"], 40, 100)
    utl_role = norm(scores["UTL"], 30, 100)
    con_role = norm(scores["CON"], 40, 100)
    clt_role = norm(scores["CLT"], 30, 100)
    exp_role = norm(scores["EXP"], 40, 100)

    awper_score = weighted_score(
        [
            (sniper_kill_rate_per_round, 0.55),
            (aim_role, 0.25),
            (kd, 0.20),
        ]
    )

    entry_score = weighted_score(
        [
            (entry_rate, 0.50),
            (entry_success, 0.30),
            (imp_role, 0.20),
        ]
    )

    sup_score = weighted_score(
        [
            (utility_usage, 0.30),
            (flashes_per_round, 0.30),
            (utl_role, 0.25),
            (enemies_flashed, 0.15),
        ]
    )

    igl_score = weighted_score(
        [
            (win_rate, 0.40),
            (con_role, 0.35),
            (exp_role, 0.25),
        ]
    )

    lurker_score = weighted_score(
        [
            (clutch_1v1, 0.35),
            (clt_role, 0.25),
            (invert_score(norm(entry_rate_raw, 0.05, 0.25)), 0.25),
            (kd, 0.15),
        ]
    )

    clutcher_score = weighted_score(
        [
            (clt_role, 0.40),
            (clutch_1v2, 0.35),
            (clutch_1v1, 0.25),
        ]
    )

    if total_1v2_count < 5:
        clutcher_score = round(clutcher_score * 0.70, 2)

    rifler_score = weighted_score(
        [
            (aim_role, 0.35),
            (imp_role, 0.35),
            (con_role, 0.30),
        ]
    )

    role_scores = {
        "IGL": igl_score,
        "AWPER": awper_score,
        "ENTRY": entry_score,
        "SUP": sup_score,
        "LURKER": lurker_score,
        "RIFLER": rifler_score,
        "CLUTCHER": clutcher_score,
    }

        # Minimum eligibility gates by role.
    # These gates prevent the system from assigning a specialized role
    # when the player does not show the minimum real signal for that role.

    if sniper_kill_rate_per_round_raw < 0.07:
        role_scores["AWPER"] = 0.0

    if entry_rate_raw < 0.20 or entry_success_raw < 0.45:
        role_scores["ENTRY"] = 0.0

    if entry_rate_raw < 0.20 or entry_success_raw < 0.45:
        role_scores["ENTRY"] = 0.0

    if role_scores["ENTRY"] < 65:
        role_scores["ENTRY"] = 0.0

    if scores["UTL"] < 50:
        role_scores["SUP"] = 0.0

    if scores["CLT"] < 55:
        role_scores["CLUTCHER"] = 0.0

    if entry_rate_raw > 0.18:
        role_scores["LURKER"] = 0.0

    if role_scores["IGL"] < 68:
        role_scores["IGL"] = 0.0

    # Minimum eligibility gates by role.
    # These gates prevent forced specialized roles when the real signal is weak.
    if sniper_kill_rate_per_round_raw < 0.07:
        role_scores["AWPER"] = 0.0

    if entry_rate_raw < 0.18:
        role_scores["ENTRY"] = 0.0

    if scores["UTL"] < 50:
        role_scores["SUP"] = 0.0

    if scores["CLT"] < 55:
        role_scores["CLUTCHER"] = 0.0

    if entry_rate_raw > 0.18:
        role_scores["LURKER"] = 0.0

    if role_scores["IGL"] < 68:
        role_scores["IGL"] = 0.0

    max_role = max(role_scores, key=role_scores.get)
    max_score = role_scores[max_role]

    specialized_scores = {
        role: score
        for role, score in role_scores.items()
        if role != "RIFLER"
    }

    best_specialized_role = max(specialized_scores, key=specialized_scores.get)
    best_specialized_score = specialized_scores[best_specialized_role]
    rifler_score = role_scores["RIFLER"]



    # Strong identity priority.
    # AWPER should win close disputes if sniper signal is real and score is strong.
    if (
        role_scores["AWPER"] >= 60
        and sniper_kill_rate_per_round_raw >= 0.07
        and role_scores["ENTRY"] - role_scores["AWPER"] <= 8
    ):
        return "AWPER", role_scores

    # RIFLER is the anchor role.
    # If no specialized role is clearly strong, use RIFLER.
    if best_specialized_score < 55:
        return "RIFLER", role_scores

    # If RIFLER is very close to the best specialized role, keep RIFLER.
    # This avoids over-classifying balanced players.
    if (
        rifler_score >= best_specialized_score - 5
        and best_specialized_score < 70
    ):
        return "RIFLER", role_scores

    return max_role, role_scores
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

    lurker_penalty = 15 if n["entry_rate"] >= 75 else 0
    lurker_score = max(lurker_base - lurker_penalty, 0)

    igl_score = weighted_score(
        [
            (scores["EXP"], 0.30),
            (n["total_matches_score"], 0.20),
            (n["utility_success"], 0.20),
            (n["win_rate"], 0.15),
            (n["flash_success"], 0.10),
            (n["longest_streak"], 0.05),
        ]
    )

    if scores["EXP"] < 60:
        igl_score *= 0.75

    role_scores = {
        "IGL": round(igl_score, 2),
        "AWPER": awper_score,
        "ENTRY": entry_score,
        "SUP": sup_score,
        "LURKER": lurker_score,
        "RIFLER": rifler_score,
        "CLUTCHER": clutcher_score,
    }

    max_role = max(role_scores, key=role_scores.get)
    max_score = role_scores[max_role]

    if max_score < 65:
        return "RIFLER", role_scores

    entry_score = role_scores["ENTRY"]
    sup_score = role_scores["SUP"]

    if (
        entry_score >= 80
        and sup_score >= entry_score
        and sup_score - entry_score <= 3
    ):
        return "ENTRY", role_scores

    igl_score = role_scores["IGL"]

    if (
        igl_score >= 68
        and max_role in ["AWPER", "ENTRY"]
        and max_score - igl_score <= 3
    ):
        return "IGL", role_scores

    if max_role == "IGL" and igl_score < 68:
        non_igl_roles = {
            role: score
            for role, score in role_scores.items()
            if role != "IGL"
        }

        max_role = max(non_igl_roles, key=non_igl_roles.get)
        max_score = non_igl_roles[max_role]

    rifler_score = role_scores["RIFLER"]

    specialized_roles = {
        role: score
        for role, score in role_scores.items()
        if role != "RIFLER"
    }

    best_specialized_role = max(specialized_roles, key=specialized_roles.get)
    best_specialized_score = specialized_roles[best_specialized_role]

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

        final_overall = calculate_final_overall(
            base_overall=scores["OVERALL"],
            role=role,
            role_scores=role_scores,
            faceit_level=row.get("cs2_skill_level"),
        )

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
                "BASE_OVERALL": scores["OVERALL"],
                "OVERALL": final_overall,
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