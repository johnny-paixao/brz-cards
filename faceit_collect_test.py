"""
FACEIT CS2 Match-Rounds Collector — Cloudflare Bypass
======================================================
This script successfully bypasses Cloudflare security on FACEIT's internal API
using `curl_cffi` (TLS/JA3 fingerprinted requests) without needing a browser.
It collects detailed CS2 statistics (including faceit_rating and round swings)
for the 3 target players.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import requests
from curl_cffi import requests as curl_requests
from dotenv import load_dotenv

load_dotenv()

FACEIT_API_KEY = os.getenv("FACEIT_API_KEY")
if not FACEIT_API_KEY:
    print("❌ Error: FACEIT_API_KEY not found in .env file.")
    sys.exit(1)

HEADERS_OFFICIAL = {
    "Authorization": f"Bearer {FACEIT_API_KEY}",
    "Accept": "application/json",
}

# The target players to collect
PLAYERS_INPUT = ["JohnnyPanda", "mHc", "-Eragonz-"]

# Known mappings for absolute safety (or fallback if API resolution fails)
KNOWN_IDS = {
    "JohnnyPanda": "50b900e5-261c-42f1-87ac-51bf6000e0ac",
    "mHc": "5e61a4c3-6ce6-49f6-ac80-457804e4cb23",
    "-Eragonz-": "344645a5-6be3-45f7-8d88-a1f0e7dc5a98",
    "Eragonz-": "344645a5-6be3-45f7-8d88-a1f0e7dc5a98",
}


def resolve_player_id(nickname: str) -> str | None:
    """Resolve a player's nickname to a player_id using the official FACEIT API."""
    # Pre-clean or check variations if it fails
    variations = [nickname]
    if nickname == "Eragonz-":
        variations.append("-Eragonz-")
    elif nickname == "-Eragonz-":
        variations.append("Eragonz-")

    for nick in variations:
        url = f"https://open.faceit.com/data/v4/players?nickname={nick}&game=cs2"
        print(f"  🔍 Resolving player_id for '{nick}' via Official API...")
        try:
            resp = requests.get(url, headers=HEADERS_OFFICIAL, timeout=15)
            if resp.status_code == 200:
                pid = resp.json().get("player_id")
                if pid:
                    print(f"  ✅ Resolved successfully: {pid}")
                    return pid
            else:
                print(f"  ⚠️  Resolution attempt for '{nick}' returned status {resp.status_code}")
        except Exception as e:
            print(f"  ❌ Error resolving '{nick}': {e}")

    # Fallback to known IDs dictionary
    fallback_id = KNOWN_IDS.get(nickname)
    if fallback_id:
        print(f"  ℹ️  Using known static player_id fallback: {fallback_id}")
        return fallback_id

    return None


def fetch_match_rounds_internal(player_id: str) -> list:
    """
    Fetch CS2 match rounds from the internal API using curl_cffi.
    This bypasses Cloudflare security directly via TLS fingerprinting.
    """
    url = f"https://www.faceit.com/api/statistics/v1/cs2/players/{player_id}/match-rounds?limit=30"
    print(f"  ⚡ Requesting internal API: {url}")
    
    try:
        # We impersonate Chrome to bypass Cloudflare
        resp = curl_requests.get(url, impersonate="chrome", timeout=20)
        
        if resp.status_code == 200:
            data = resp.json()
            payload = data.get("payload", {})
            cs2_data = payload.get("cs2", {})
            # Look for match_rounds (snake_case) or matchRounds (camelCase)
            rounds = cs2_data.get("match_rounds", cs2_data.get("matchRounds", []))
            print(f"  ✅ Fetched {len(rounds)} matches from internal endpoint.")
            return rounds
        elif resp.status_code == 403:
            print("  ❌ Cloudflare block! Direct curl_cffi was rejected (403 Forbidden).")
            return []
        else:
            print(f"  ⚠️  Internal API returned status {resp.status_code}")
            return []
    except Exception as e:
        print(f"  ❌ Network error during internal API fetch: {e}")
        return []


def validate_match_data(matches: list) -> bool:
    """Validate that every match contains non-null faceitRating and faceitRoundSwingAvg."""
    if not matches:
        return False
        
    for i, match in enumerate(matches):
        # The internal payload uses snake_case keys (e.g. faceit_rating, faceit_round_swing_avg)
        # We check both snake_case and camelCase to be resilient
        rating = match.get("faceit_rating") or match.get("faceitRating")
        swing = match.get("faceit_round_swing_avg") or match.get("faceitRoundSwingAvg")
        
        if rating is None:
            print(f"  ❌ Match {i} is missing rating (ID: {match.get('match_id') or match.get('matchId')})")
            return False
        if swing is None:
            print(f"  ❌ Match {i} is missing round swing (ID: {match.get('match_id') or match.get('matchId')})")
            return False
            
    return True


def main():
    print("=" * 70)
    print("   FACEIT CS2 INTERNAL STATS COLLECTOR — NO BROWSER CLOUDFLARE BYPASS")
    print("=" * 70)
    
    retrieved_time = datetime.now(timezone.utc).isoformat()
    result_data = {
        "retrieved_at": retrieved_time,
        "players": {}
    }
    
    # We want exactly these nicknames in the final JSON output
    target_nicks = ["JohnnyPanda", "mHc", "Eragonz-"]
    
    for nickname in target_nicks:
        print(f"\n🎮 Processing player: {nickname}")
        print("-" * 50)
        
        # 1. Resolve player ID
        player_id = resolve_player_id(nickname)
        if not player_id:
            print(f"❌ Failed to resolve player_id for {nickname}")
            result_data["players"][nickname] = {
                "player_id": None,
                "match_count": 0,
                "matches": []
            }
            continue
            
        # 2. Fetch matches using our Cloudflare bypass
        matches = fetch_match_rounds_internal(player_id)
        
        # 3. Save raw data
        result_data["players"][nickname] = {
            "player_id": player_id,
            "match_count": len(matches),
            "matches": matches
        }
        
        # 4. Wait ~2 seconds between requests to be polite
        if nickname != target_nicks[-1]:
            print("  ⏳ Waiting 2 seconds before next request...")
            time.sleep(2)
            
    # Save to faceit_test.json in root directory
    output_path = "faceit_test.json"
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Saved raw results successfully to: {output_path}")
    except Exception as e:
        print(f"\n❌ Error saving output JSON file: {e}")

    # Validation & Table Summary
    print("\n" + "=" * 70)
    print("   COLLECTION SUMMARY & VALIDATION")
    print("=" * 70)
    
    print(f"{'Nickname':<15} | {'Player ID':<38} | {'Matches':<8} | {'Validation':<10}")
    print("-" * 70)
    
    all_players_valid = True
    for nickname, info in result_data["players"].items():
        pid = info["player_id"] or "N/A"
        count = info["match_count"]
        matches = info["matches"]
        
        # Run validations: resolved id, count > 0, and non-null ratings
        id_ok = info["player_id"] is not None
        count_ok = count > 0
        data_valid = validate_match_data(matches) if count_ok else False
        
        val_status = "✅ PASS" if (id_ok and count_ok and data_valid) else "❌ FAIL"
        if val_status == "❌ FAIL":
            all_players_valid = False
            
        print(f"{nickname:<15} | {pid:<38} | {count:<8} | {val_status}")
        
        # Show detail of missing stats if failed
        if count_ok and not data_valid:
            print(f"   ⚠️ Warning: Some matches for {nickname} are missing faceitRating or faceitRoundSwingAvg.")

    print("=" * 70)
    
    if all_players_valid:
        print("\n🎉 SUCCESS: All player profiles collected, validated, and saved successfully!")
    else:
        print("\n⚠️ WARNING: One or more player collections did not pass validation checks.")


if __name__ == "__main__":
    main()
