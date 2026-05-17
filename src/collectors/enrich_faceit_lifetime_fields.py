"""
Enrich BRz FACEIT players with lifetime fields used by BRz Cards EXP.

Adds/updates these columns in data/brz_faceit_players_enriched.csv:
- highest_lifetime_faceit_elo
- lifetime_faceit_matches

Notes:
- lifetime_faceit_matches is collected from FACEIT /players/{player_id}/stats/cs2.
- highest_lifetime_faceit_elo is collected if FACEIT returns a compatible key.
- If FACEIT does not return highest lifetime ELO, the script falls back to current cs2_faceit_elo.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_ROOT / "data" / "brz_faceit_players_enriched.csv"

API_BASE = "https://open.faceit.com/data/v4"
GAME = "cs2"


def parse_int(value: Any, default: int = 0) -> int:
    """Safely parse integers from FACEIT values."""
    if value is None:
        return default

    try:
        if isinstance(value, str):
            cleaned = value.replace(",", "").replace("%", "").strip()
            if cleaned == "":
                return default
            return int(float(cleaned))

        return int(float(value))
    except Exception:
        return default


def find_first_key(data: dict[str, Any], candidates: list[str]) -> Any:
    """Find first value by candidate key, case-insensitive."""
    if not isinstance(data, dict):
        return None

    lower_map = {str(k).strip().lower(): v for k, v in data.items()}

    for candidate in candidates:
        key = candidate.strip().lower()
        if key in lower_map:
            return lower_map[key]

    return None


def fetch_lifetime_stats(player_id: str, api_key: str) -> dict[str, Any]:
    """Fetch lifetime stats for one player."""
    url = f"{API_BASE}/players/{player_id}/stats/{GAME}"
    headers = {"Authorization": f"Bearer {api_key}"}

    response = requests.get(url, headers=headers, timeout=30)

    if response.status_code == 404:
        return {}

    response.raise_for_status()

    payload = response.json()
    lifetime = payload.get("lifetime", {})

    return lifetime if isinstance(lifetime, dict) else {}


def main() -> None:
    api_key = os.getenv("FACEIT_API_KEY")

    if not api_key:
        raise RuntimeError("FACEIT_API_KEY not found in environment.")

    if not DATA_PATH.exists():
        raise FileNotFoundError(f"File not found: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)

    required_cols = [
        "faceit_nickname_input",
        "faceit_nickname_official",
        "faceit_player_id",
    ]

    missing = [col for col in required_cols if col not in df.columns]

    if missing:
        raise RuntimeError(f"Missing required columns: {missing}")

    # Create or coerce target columns as numeric nullable integers.
    if "highest_lifetime_faceit_elo" not in df.columns:
        df["highest_lifetime_faceit_elo"] = pd.Series([pd.NA] * len(df), dtype="Int64")
    else:
        df["highest_lifetime_faceit_elo"] = pd.to_numeric(
            df["highest_lifetime_faceit_elo"], errors="coerce"
        ).astype("Int64")

    if "lifetime_faceit_matches" not in df.columns:
        df["lifetime_faceit_matches"] = pd.Series([pd.NA] * len(df), dtype="Int64")
    else:
        df["lifetime_faceit_matches"] = pd.to_numeric(
            df["lifetime_faceit_matches"], errors="coerce"
        ).astype("Int64")

    backup_path = DATA_PATH.with_name("brz_faceit_players_enriched_backup_before_lifetime_elo.csv")
    df.to_csv(backup_path, index=False, encoding="utf-8-sig")
    print(f"[OK] Backup saved to: {backup_path}")

    for idx, row in df.iterrows():
        nickname = str(row.get("faceit_nickname_official") or row.get("faceit_nickname_input") or "").strip()
        player_id = str(row.get("faceit_player_id") or "").strip()

        if not player_id:
            print(f"[WARN] {nickname}: missing player_id")
            continue

        try:
            lifetime = fetch_lifetime_stats(player_id, api_key)

            lifetime_matches = parse_int(
                find_first_key(
                    lifetime,
                    [
                        "Matches",
                        "Total Matches",
                        "Lifetime Matches",
                    ],
                ),
                default=0,
            )

            highest_lifetime_elo = parse_int(
                find_first_key(
                    lifetime,
                    [
                        "Highest Elo",
                        "Highest ELO",
                        "Highest FACEIT Elo",
                        "Highest FACEIT ELO",
                        "Max Elo",
                        "Max ELO",
                        "Maximum Elo",
                        "Maximum ELO",
                    ],
                ),
                default=0,
            )

            # FACEIT may not expose highest lifetime ELO in this endpoint.
            # Fallback to current CS2 ELO to avoid EXP becoming zero.
            if highest_lifetime_elo <= 0:
                highest_lifetime_elo = parse_int(row.get("cs2_faceit_elo"), default=0)

            df.loc[idx, "lifetime_faceit_matches"] = lifetime_matches
            df.loc[idx, "highest_lifetime_faceit_elo"] = highest_lifetime_elo

            print(
                f"[OK] {idx + 1}/{len(df)} {nickname} | "
                f"highest_elo={highest_lifetime_elo} | "
                f"lifetime_matches={lifetime_matches}"
            )

            time.sleep(0.15)

        except Exception as exc:
            print(f"[ERROR] {idx + 1}/{len(df)} {nickname} | {exc}")

    df["highest_lifetime_faceit_elo"] = pd.to_numeric(
        df["highest_lifetime_faceit_elo"], errors="coerce"
    ).fillna(0).astype(int)

    df["lifetime_faceit_matches"] = pd.to_numeric(
        df["lifetime_faceit_matches"], errors="coerce"
    ).fillna(0).astype(int)

    df.to_csv(DATA_PATH, index=False, encoding="utf-8-sig")
    print(f"[OK] Updated file: {DATA_PATH}")

    print(
        df[
            [
                "faceit_nickname_official",
                "cs2_faceit_elo",
                "highest_lifetime_faceit_elo",
                "lifetime_faceit_matches",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
