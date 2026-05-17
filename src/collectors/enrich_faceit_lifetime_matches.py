"""
Collect lifetime FACEIT matches for BRz Cards EXP.

Updates data/brz_faceit_players_enriched.csv with:
- lifetime_faceit_matches

Source:
- FACEIT Data API: /players/{player_id}/stats/cs2
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_ROOT / "data" / "brz_faceit_players_enriched.csv"
API_BASE = "https://open.faceit.com/data/v4"
GAME = "cs2"


def parse_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default

    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
            if not value:
                return default
        return int(float(value))
    except Exception:
        return default


def fetch_lifetime_matches(player_id: str, api_key: str) -> int:
    url = f"{API_BASE}/players/{player_id}/stats/{GAME}"
    headers = {"Authorization": f"Bearer {api_key}"}

    response = requests.get(url, headers=headers, timeout=30)

    if response.status_code == 404:
        return 0

    response.raise_for_status()

    data = response.json()
    lifetime = data.get("lifetime", {})

    return parse_int(lifetime.get("Matches"), default=0)


def main() -> None:
    api_key = os.getenv("FACEIT_API_KEY")

    if not api_key:
        raise RuntimeError("FACEIT_API_KEY not found in environment.")

    if not DATA_PATH.exists():
        raise FileNotFoundError(f"File not found: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)

    required_columns = ["faceit_nickname_official", "faceit_player_id"]
    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        raise RuntimeError(f"Missing required columns: {missing}")

    if "lifetime_faceit_matches" not in df.columns:
        df["lifetime_faceit_matches"] = 0

    df["lifetime_faceit_matches"] = pd.to_numeric(
        df["lifetime_faceit_matches"], errors="coerce"
    ).fillna(0).astype(int)

    backup_path = DATA_PATH.with_name("brz_faceit_players_enriched_backup_before_lifetime_matches.csv")
    df.to_csv(backup_path, index=False, encoding="utf-8-sig")
    print(f"[OK] Backup saved to: {backup_path}")

    for idx, row in df.iterrows():
        nickname = str(row.get("faceit_nickname_official") or row.get("faceit_nickname_input") or "").strip()
        player_id = str(row.get("faceit_player_id") or "").strip()

        if not player_id:
            print(f"[WARN] {idx + 1}/{len(df)} {nickname} | missing player_id")
            continue

        try:
            matches = fetch_lifetime_matches(player_id, api_key)
            df.loc[idx, "lifetime_faceit_matches"] = matches

            print(f"[OK] {idx + 1}/{len(df)} {nickname} | lifetime_matches={matches}")

            time.sleep(0.15)

        except Exception as exc:
            print(f"[ERROR] {idx + 1}/{len(df)} {nickname} | {exc}")

    df["lifetime_faceit_matches"] = pd.to_numeric(
        df["lifetime_faceit_matches"], errors="coerce"
    ).fillna(0).astype(int)

    df.to_csv(DATA_PATH, index=False, encoding="utf-8-sig")
    print(f"[OK] Updated file: {DATA_PATH}")


if __name__ == "__main__":
    main()
