import statistics
from typing import Any


SCORE_VERSION = "v1"

SCORE_WEIGHTS = {
    "aim": 0.28,
    "impact": 0.24,
    "utility": 0.16,
    "consistency": 0.14,
    "clutch": 0.10,
    "experience": 0.08,
}


def clamp(value: float, minimum: float = 0, maximum: float = 100) -> float:
    """
    Keep a value inside a fixed range.
    """
    return max(minimum, min(maximum, value))


def scale_to_100(value: float | int | None, low: float, high: float) -> float:
    """
    Convert a metric to a 0-100 score where higher is better.
    """
    if value is None:
        return 50

    if high == low:
        return 50

    scaled = ((float(value) - low) / (high - low)) * 100
    return clamp(scaled)


def inverse_scale_to_100(value: float | int | None, low: float, high: float) -> float:
    """
    Convert a metric to a 0-100 score where lower is better.

    Example:
    reaction time: lower is better.
    preaim angle/error: lower is better.
    """
    if value is None:
        return 50

    if high == low:
        return 50

    scaled = ((high - float(value)) / (high - low)) * 100
    return clamp(scaled)


def safe_mean(values: list[float]) -> float:
    """
    Calculate mean safely.
    """
    if not values:
        return 0

    return statistics.mean(values)


def safe_std(values: list[float]) -> float:
    """
    Calculate population standard deviation safely.
    """
    if len(values) < 2:
        return 0

    return statistics.pstdev(values)


def calculate_tier(overall: int) -> str:
    """
    Convert overall score into card tier.
    """
    if overall >= 93:
        return "LEGENDARY"

    if overall >= 85:
        return "ELITE"

    if overall >= 75:
        return "GOLD"

    if overall >= 60:
        return "SILVER"

    return "BRONZE"


def infer_role(aim: int, impact: int, utility: int) -> str:
    """
    Infer a simple player role based on strongest attributes.

    This is a first version. Later, we can improve it using entry stats,
    AWP usage, trade behavior and utility patterns.
    """
    if utility >= 75 and utility >= aim - 3 and utility >= impact - 3:
        return "SUPPORT"

    if impact >= 75 and impact >= aim:
        return "ENTRY"

    if aim >= 80:
        return "RIFLER"

    return "RIFLER"


def calculate_aim_score(profile_stats: dict[str, Any]) -> int:
    """
    Calculate Aim based on Leetify profile-level mechanics stats.
    """
    accuracy_enemy_spotted = profile_stats.get("accuracy_enemy_spotted")
    accuracy_head = profile_stats.get("accuracy_head")
    spray_accuracy = profile_stats.get("spray_accuracy")
    reaction_time_ms = profile_stats.get("reaction_time_ms")
    preaim = profile_stats.get("preaim")

    aim = (
        0.30 * scale_to_100(accuracy_enemy_spotted, low=20, high=50)
        + 0.25 * scale_to_100(accuracy_head, low=5, high=25)
        + 0.20 * scale_to_100(spray_accuracy, low=10, high=65)
        + 0.15 * inverse_scale_to_100(reaction_time_ms, low=350, high=800)
        + 0.10 * inverse_scale_to_100(preaim, low=5, high=20)
    )

    return round(clamp(aim))


def calculate_impact_score(matches: list[dict[str, Any]]) -> int:
    """
    Calculate Impact based on recent Leetify rating and match outcomes.
    """
    ratings = [
        float(match["leetify_rating"])
        for match in matches
        if match.get("leetify_rating") is not None
    ]

    outcomes = [
        match.get("team_result")
        for match in matches
        if match.get("team_result") is not None
    ]

    avg_rating = safe_mean(ratings)

    wins = sum(1 for outcome in outcomes if outcome == "win")
    win_rate = wins / len(outcomes) if outcomes else 0.5

    impact = (
        0.70 * scale_to_100(avg_rating, low=-0.08, high=0.08)
        + 0.30 * (win_rate * 100)
    )

    return round(clamp(impact))


def calculate_utility_score(profile_stats: dict[str, Any]) -> int:
    """
    Calculate Utility based on Leetify profile-level utility stats.
    """
    flash_duration = profile_stats.get("flashbang_hit_foe_avg_duration")
    foes_per_flash = profile_stats.get("flashbang_hit_foe_per_flashbang")
    flash_to_kill = profile_stats.get("flashbang_leading_to_kill")
    he_damage = profile_stats.get("he_foes_damage_avg")
    utility_on_death = profile_stats.get("utility_on_death_avg")
    team_flash = profile_stats.get("flashbang_hit_friend_per_flashbang")

    utility = (
        0.22 * scale_to_100(flash_duration, low=1.0, high=4.0)
        + 0.22 * scale_to_100(foes_per_flash, low=0.2, high=1.0)
        + 0.18 * scale_to_100(flash_to_kill, low=0.5, high=3.0)
        + 0.18 * scale_to_100(he_damage, low=2.0, high=12.0)
        + 0.10 * inverse_scale_to_100(utility_on_death, low=80, high=400)
        + 0.10 * inverse_scale_to_100(team_flash, low=0.0, high=0.8)
    )

    return round(clamp(utility))


def calculate_consistency_score(matches: list[dict[str, Any]]) -> int:
    """
    Calculate Consistency based on stability of Leetify rating.
    """
    ratings = [
        float(match["leetify_rating"])
        for match in matches
        if match.get("leetify_rating") is not None
    ]

    if not ratings:
        return 50

    rating_std = safe_std(ratings)

    positive_matches = sum(1 for rating in ratings if rating >= 0)
    positive_match_rate = positive_matches / len(ratings)

    consistency = (
        0.65 * inverse_scale_to_100(rating_std, low=0.015, high=0.08)
        + 0.35 * (positive_match_rate * 100)
    )

    return round(clamp(consistency))


def calculate_experience_score(
    profile_payload: dict[str, Any],
    matches_analyzed: int,
) -> int:
    """
    Calculate Experience using total Leetify matches and recent analyzed matches.
    """
    total_matches = profile_payload.get("total_matches") or 0

    experience = (
        0.70 * scale_to_100(total_matches, low=50, high=3000)
        + 0.30 * scale_to_100(matches_analyzed, low=10, high=100)
    )

    return round(clamp(experience))


def calculate_brz_card_score(
    player: dict[str, Any],
    matches: list[dict[str, Any]],
    profile_payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Calculate BRz player card score from Leetify profile and match stats.
    """
    profile_stats = profile_payload.get("stats", {})

    aim = calculate_aim_score(profile_stats)
    impact = calculate_impact_score(matches)
    utility = calculate_utility_score(profile_stats)
    consistency = calculate_consistency_score(matches)

    # Temporary clutch proxy.
    # Later, we should replace this with real 1vX/clutch data if available.
    clutch = round(clamp((0.60 * impact) + (0.40 * consistency)))

    experience = calculate_experience_score(
        profile_payload=profile_payload,
        matches_analyzed=len(matches),
    )

    overall = round(
        SCORE_WEIGHTS["aim"] * aim
        + SCORE_WEIGHTS["impact"] * impact
        + SCORE_WEIGHTS["utility"] * utility
        + SCORE_WEIGHTS["consistency"] * consistency
        + SCORE_WEIGHTS["clutch"] * clutch
        + SCORE_WEIGHTS["experience"] * experience
    )

    role = infer_role(
        aim=aim,
        impact=impact,
        utility=utility,
    )

    tier = calculate_tier(overall)

    return {
        "player_id": player["player_id"],
        "display_name": player["display_name"],
        "overall_brz": overall,
        "aim": aim,
        "impact": impact,
        "utility": utility,
        "consistency": consistency,
        "clutch": clutch,
        "experience": experience,
        "role": role,
        "tier": tier,
        "matches_analyzed": len(matches),
        "score_version": SCORE_VERSION,
    }