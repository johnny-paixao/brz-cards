import csv
import json
import os
import time
from pathlib import Path

import requests


BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_MATCHES_CSV_PATH = BASE_DIR / "data" / "brz_faceit_season8_match_ids.csv"
PLAYERS_CSV_PATH = BASE_DIR / "data" / "brz_faceit_players_enriched.csv"
OUTPUT_CSV_PATH = BASE_DIR / "data" / "brz_faceit_season8_stats.csv"
CACHE_DIR = BASE_DIR / "data" / "cache" / "faceit_match_stats"

FACEIT_API_BASE_URL = "https://open.faceit.com/data/v4"

CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_api_key() -> str:
    api_key = os.getenv("FACEIT_API_KEY")

    if not api_key:
        raise RuntimeError(
            "FACEIT_API_KEY not found. Set it in your environment before running this script."
        )

    return api_key


def faceit_get(endpoint: str, params: dict | None = None) -> dict:
    url = f"{FACEIT_API_BASE_URL}{endpoint}"

    headers = {
        "Authorization": f"Bearer {get_api_key()}",
        "Accept": "application/json",
    }

    response = requests.get(url, headers=headers, params=params, timeout=30)

    if response.status_code == 429:
        print("[RATE LIMIT] Waiting 60 seconds...")
        time.sleep(60)
        response = requests.get(url, headers=headers, params=params, timeout=30)

    response.raise_for_status()
    return response.json()


def safe_float(value, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    with open(path, mode="r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def get_match_stats(match_id: str) -> dict:
    cache_path = CACHE_DIR / f"{match_id}.json"

    if cache_path.exists():
        with open(cache_path, mode="r", encoding="utf-8") as file:
            return json.load(file)

    payload = faceit_get(f"/matches/{match_id}/stats")

    with open(cache_path, mode="w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    time.sleep(0.25)
    return payload


def find_player_stats(payload: dict, faceit_player_id: str) -> dict | None:
    rounds = payload.get("rounds", [])

    for round_data in rounds:
        for team in round_data.get("teams", []):
            for player in team.get("players", []):
                if player.get("player_id") == faceit_player_id:
                    return player

    return None


def init_player_aggregate(player: dict) -> dict:
    return {
        "faceit_nickname": (
            player.get("faceit_nickname_official")
            or player.get("faceit_nickname_input")
            or ""
        ),
        "faceit_player_id": player.get("faceit_player_id"),
        "country": player.get("country"),
        "steam_id_64": player.get("steam_id_64"),
        "cs2_skill_level": player.get("cs2_skill_level"),
        "cs2_faceit_elo": player.get("cs2_faceit_elo"),

        "matches": 0,
        "wins": 0,

        "kills": 0,
        "deaths": 0,
        "assists": 0,
        "headshots": 0,
        "damage": 0,

        "entry_count": 0,
        "entry_wins": 0,
        "utility_damage": 0,
        "utility_count": 0,
        "utility_successes": 0,
        "flash_count": 0,
        "flash_successes": 0,
        "enemies_flashed": 0,

        "clutch_1v1_count": 0,
        "clutch_1v1_wins": 0,
        "clutch_1v2_count": 0,
        "clutch_1v2_wins": 0,

        "sniper_kills": 0,

        "adr_values": [],
        "kd_values": [],
        "kr_values": [],
        "hs_pct_values": [],
        "entry_rate_values": [],
        "entry_success_values": [],
        "utility_damage_per_round_values": [],
        "utility_success_rate_values": [],
        "utility_usage_per_round_values": [],
        "flash_success_rate_values": [],
        "flashes_per_round_values": [],
        "enemies_flashed_per_round_values": [],
        "sniper_kill_rate_values": [],
        "sniper_kill_rate_per_round_values": [],

        "recent_results": [],
    }


def add_metric_value(agg: dict, key: str, value) -> None:
    parsed = safe_float(value, None)

    if parsed is None:
        return

    agg[key].append(parsed)


def update_aggregate(agg: dict, player_stats: dict) -> None:
    stats = player_stats.get("player_stats", {})

    result = safe_int(stats.get("Result"))
    winner = safe_int(stats.get("Winner"))
    won = 1 if result == 1 or winner == 1 else 0

    agg["matches"] += 1
    agg["wins"] += won
    agg["recent_results"].append(str(won))

    agg["kills"] += safe_int(stats.get("Kills"))
    agg["deaths"] += safe_int(stats.get("Deaths"))
    agg["assists"] += safe_int(stats.get("Assists"))
    agg["headshots"] += safe_int(stats.get("Headshots"))
    agg["damage"] += safe_int(stats.get("Damage"))

    agg["entry_count"] += safe_int(stats.get("Entry Count"))
    agg["entry_wins"] += safe_int(stats.get("Entry Wins"))

    agg["utility_damage"] += safe_int(stats.get("Utility Damage"))
    agg["utility_count"] += safe_int(stats.get("Utility Count"))
    agg["utility_successes"] += safe_int(stats.get("Utility Successes"))

    agg["flash_count"] += safe_int(stats.get("Flash Count"))
    agg["flash_successes"] += safe_int(stats.get("Flash Successes"))
    agg["enemies_flashed"] += safe_int(stats.get("Enemies Flashed"))

    agg["clutch_1v1_count"] += safe_int(stats.get("1v1Count"))
    agg["clutch_1v1_wins"] += safe_int(stats.get("1v1Wins"))
    agg["clutch_1v2_count"] += safe_int(stats.get("1v2Count"))
    agg["clutch_1v2_wins"] += safe_int(stats.get("1v2Wins"))

    agg["sniper_kills"] += safe_int(stats.get("Sniper Kills"))

    add_metric_value(agg, "adr_values", stats.get("ADR"))
    add_metric_value(agg, "kd_values", stats.get("K/D Ratio"))
    add_metric_value(agg, "kr_values", stats.get("K/R Ratio"))
    add_metric_value(agg, "hs_pct_values", stats.get("Headshots %"))

    add_metric_value(agg, "entry_rate_values", stats.get("Match Entry Rate"))
    add_metric_value(agg, "entry_success_values", stats.get("Match Entry Success Rate"))

    add_metric_value(
        agg,
        "utility_damage_per_round_values",
        stats.get("Utility Damage per Round in a Match"),
    )
    add_metric_value(
        agg,
        "utility_success_rate_values",
        stats.get("Utility Success Rate per Match"),
    )
    add_metric_value(
        agg,
        "utility_usage_per_round_values",
        stats.get("Utility Usage per Round"),
    )

    add_metric_value(
        agg,
        "flash_success_rate_values",
        stats.get("Flash Success Rate per Match"),
    )
    add_metric_value(
        agg,
        "flashes_per_round_values",
        stats.get("Flashes per Round in a Match"),
    )
    add_metric_value(
        agg,
        "enemies_flashed_per_round_values",
        stats.get("Enemies Flashed per Round in a Match"),
    )

    add_metric_value(
        agg,
        "sniper_kill_rate_values",
        stats.get("Sniper Kill Rate per Match"),
    )
    add_metric_value(
        agg,
        "sniper_kill_rate_per_round_values",
        stats.get("Sniper Kill Rate per Round"),
    )


def div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def current_win_streak(results: list[str]) -> int:
    streak = 0

    for result in reversed(results):
        if result == "1":
            streak += 1
        else:
            break

    return streak


def longest_win_streak(results: list[str]) -> int:
    best = 0
    current = 0

    for result in results:
        if result == "1":
            current += 1
            best = max(best, current)
        else:
            current = 0

    return best


def build_output_row(agg: dict) -> dict:
    matches = agg["matches"]
    kills = agg["kills"]
    deaths = agg["deaths"]
    headshots = agg["headshots"]

    recent_last_5 = agg["recent_results"][-5:]

    # Prefer FACEIT per-match calculated fields for season averages.
    # They are more reliable than reconstructing round-based metrics from fields
    # that may be missing or zero in the match stats payload.
    adr = avg(agg["adr_values"])
    kd = avg(agg["kd_values"]) if agg["kd_values"] else div(kills, deaths)
    kr = avg(agg["kr_values"])
    hs_pct = avg(agg["hs_pct_values"]) if agg["hs_pct_values"] else div(headshots, kills) * 100

    entry_rate = avg(agg["entry_rate_values"])
    entry_success = avg(agg["entry_success_values"])

    utility_damage_per_round = avg(agg["utility_damage_per_round_values"])
    utility_success_rate = avg(agg["utility_success_rate_values"])
    utility_usage_per_round = avg(agg["utility_usage_per_round_values"])

    flash_success_rate = avg(agg["flash_success_rate_values"])
    flashes_per_round = avg(agg["flashes_per_round_values"])
    enemies_flashed_per_round = avg(agg["enemies_flashed_per_round_values"])

    sniper_kill_rate = avg(agg["sniper_kill_rate_values"])
    sniper_kill_rate_per_round = avg(agg["sniper_kill_rate_per_round_values"])

    return {
        "faceit_nickname": agg["faceit_nickname"],
        "faceit_player_id": agg["faceit_player_id"],
        "country": agg["country"],
        "steam_id_64": agg["steam_id_64"],
        "cs2_skill_level": agg["cs2_skill_level"],
        "cs2_faceit_elo": agg["cs2_faceit_elo"],

        "Average K/D Ratio": round(kd, 2),
        "ADR": round(adr, 2),
        "Average Headshots %": round(hs_pct, 2),
        "Win Rate %": round(div(agg["wins"], matches) * 100, 2),

        "Matches": matches,
        "Total Matches": matches,
        "Wins": agg["wins"],
        "Recent Results": "|".join(recent_last_5),

        "Current Win Streak": current_win_streak(agg["recent_results"]),
        "Longest Win Streak": longest_win_streak(agg["recent_results"]),
        "Average K/R Ratio": round(kr, 2),

        "Entry Success Rate": round(entry_success, 4),
        "Entry Rate": round(entry_rate, 4),
        "Total Entry Count": agg["entry_count"],
        "Total Entry Wins": agg["entry_wins"],

        "Utility Damage per Round": round(utility_damage_per_round, 2),
        "Utility Success Rate": round(utility_success_rate, 4),
        "Utility Usage per Round": round(utility_usage_per_round, 4),

        "Flash Success Rate": round(flash_success_rate, 4),
        "Flashes per Round": round(flashes_per_round, 4),
        "Enemies Flashed per Round": round(enemies_flashed_per_round, 4),

        "Total Utility Damage": agg["utility_damage"],
        "Total Enemies Flashed": agg["enemies_flashed"],
        "Total Flash Successes": agg["flash_successes"],
        "Total Flash Count": agg["flash_count"],

        "1v1 Win Rate": round(div(agg["clutch_1v1_wins"], agg["clutch_1v1_count"]), 4),
        "1v2 Win Rate": round(div(agg["clutch_1v2_wins"], agg["clutch_1v2_count"]), 4),
        "Total 1v1 Count": agg["clutch_1v1_count"],
        "Total 1v1 Wins": agg["clutch_1v1_wins"],
        "Total 1v2 Count": agg["clutch_1v2_count"],
        "Total 1v2 Wins": agg["clutch_1v2_wins"],

        "Sniper Kill Rate": round(sniper_kill_rate, 4),
        "Sniper Kill Rate per Round": round(sniper_kill_rate_per_round, 4),
        "Total Sniper Kills": agg["sniper_kills"],

        "Total Damage": agg["damage"],
        "Total Rounds with extended stats": 0,
        "Total Kills with extended stats": kills,
    }


def main() -> None:
    players = load_csv(PLAYERS_CSV_PATH)
    match_rows = load_csv(INPUT_MATCHES_CSV_PATH)

    player_by_id = {
        player.get("faceit_player_id"): player
        for player in players
        if player.get("faceit_player_id")
    }

    aggregates = {
        player_id: init_player_aggregate(player)
        for player_id, player in player_by_id.items()
    }

    print(f"Loaded {len(players)} player(s).")
    print(f"Loaded {len(match_rows)} Season 8 match row(s).")
    print("-" * 80)

    for index, match_row in enumerate(match_rows, start=1):
        match_id = match_row.get("match_id")
        player_id = match_row.get("faceit_player_id")
        nickname = match_row.get("faceit_nickname")

        if not match_id or not player_id:
            continue

        try:
            payload = get_match_stats(match_id)
            player_stats = find_player_stats(payload, player_id)

            if not player_stats:
                print(f"[MISS] {index}/{len(match_rows)} {nickname} | match={match_id}")
                continue

            update_aggregate(aggregates[player_id], player_stats)

            if index % 25 == 0:
                print(f"[OK] {index}/{len(match_rows)} processed")

        except Exception as error:
            print(f"[ERROR] {index}/{len(match_rows)} {nickname} | match={match_id} | {error}")

    output_rows = [
        build_output_row(agg)
        for agg in aggregates.values()
    ]

    OUTPUT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(output_rows[0].keys())

    with open(OUTPUT_CSV_PATH, mode="w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print("-" * 80)
    print(f"Saved Season 8 aggregated stats to: {OUTPUT_CSV_PATH}")
    print(f"Total players: {len(output_rows)}")


if __name__ == "__main__":
    main()