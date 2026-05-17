"""
Collect FACEIT Tracker peak ELO for BRz Cards EXP using Playwright.

This version is more robust for players whose stats are rendered only after
scrolling/lazy loading.

Updates data/brz_faceit_players_enriched.csv with:
- faceit_tracker_highest_elo
- peak_elo_source
- peak_elo_updated_at
- peak_elo_url_nickname

It also writes debug text for players where Highest ELO is not found:
- data/debug/faceit_tracker_text_<nickname>.txt
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import pandas as pd
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_ROOT / "data" / "brz_faceit_players_enriched.csv"
DEBUG_DIR = PROJECT_ROOT / "data" / "debug"

MIN_PLAUSIBLE_ELO = 500
MAX_PLAUSIBLE_ELO = 4000

PAGE_TIMEOUT_MS = 60000
INITIAL_RENDER_WAIT_MS = 7000
SCROLL_WAIT_MS = 1200
BETWEEN_PLAYERS_WAIT_MS = 900
MAX_SCROLL_STEPS = 8

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def parse_int(value, default: int = 0) -> int:
    if value is None:
        return default

    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
            if not value:
                return default
        return int(float(value))
    except Exception:
        return default


def safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def extract_highest_elo_from_text(text: str) -> int | None:
    """
    Extract Highest ELO from rendered FACEIT Tracker page text.

    Supports both:
        Highest ELO: 2180
    and:
        Highest ELO:
        2180
    """
    patterns = [
        r"Highest\s+ELO\s*:?\s*([0-9]{3,5})",
        r"Highest\s+ELO\s*:?\s*\n\s*([0-9]{3,5})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return parse_int(match.group(1))

    return None


def validate_peak(extracted_peak: int | None, current_elo: int) -> tuple[int, str]:
    if not extracted_peak:
        return current_elo, "CURRENT_ELO_FALLBACK_NOT_FOUND"

    if extracted_peak < MIN_PLAUSIBLE_ELO or extracted_peak > MAX_PLAUSIBLE_ELO:
        return current_elo, "CURRENT_ELO_FALLBACK_INVALID_RANGE"

    if current_elo > 0 and extracted_peak < current_elo:
        return current_elo, "CURRENT_ELO_FALLBACK_PEAK_LT_CURRENT"

    return extracted_peak, "FACEIT_TRACKER_PLAYWRIGHT"


def build_candidate_nicknames(row: pd.Series) -> list[str]:
    candidates: list[str] = []

    for col in ["faceit_nickname_official", "faceit_nickname_input"]:
        value = str(row.get(col) or "").strip()
        if value:
            candidates.append(value)

    expanded: list[str] = []

    for value in candidates:
        expanded.extend(
            [
                value,
                value.lower(),
                value.upper(),
            ]
        )

    unique: list[str] = []
    seen = set()

    for value in expanded:
        value = value.strip()
        if not value:
            continue

        if value not in seen:
            unique.append(value)
            seen.add(value)

    return unique


async def get_rendered_text_after_lazy_loading(page) -> str:
    """
    Get body text after initial render and after scrolling.

    Some FACEIT Tracker sections are rendered/lazy-loaded only after scroll.
    We accumulate body text across scroll positions.
    """
    await page.wait_for_timeout(INITIAL_RENDER_WAIT_MS)

    collected_texts: list[str] = []

    async def collect_text() -> str:
        try:
            return await page.locator("body").inner_text(timeout=15000)
        except Exception:
            return ""

    text = await collect_text()
    collected_texts.append(text)

    if "Highest ELO" in text:
        return text

    # Scroll progressively to trigger lazy-loaded stats sections.
    for _ in range(MAX_SCROLL_STEPS):
        try:
            await page.mouse.wheel(0, 1400)
            await page.wait_for_timeout(SCROLL_WAIT_MS)
            text = await collect_text()
            collected_texts.append(text)

            if "Highest ELO" in text:
                return text

        except Exception:
            break

    # Return the largest accumulated text to maximize debug usefulness.
    return max(collected_texts, key=len) if collected_texts else ""


async def fetch_tracker_highest_elo(page, nickname_candidates: list[str]) -> tuple[int | None, str | None, str]:
    """
    Try candidate nickname URLs and extract rendered Highest ELO.

    Returns:
        (highest_elo, nickname_variant_used, rendered_text_for_debug)
    """
    last_text = ""

    for nickname in nickname_candidates:
        encoded_nickname = quote(nickname, safe="")
        url = f"https://faceittracker.net/players/{encoded_nickname}"

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)

            text = await get_rendered_text_after_lazy_loading(page)
            last_text = text

            highest_elo = extract_highest_elo_from_text(text)

            if highest_elo:
                return highest_elo, nickname, text

        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue

    return None, None, last_text


async def main_async() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"File not found: {DATA_PATH}")

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(DATA_PATH)

    required_columns = ["faceit_nickname_official", "cs2_faceit_elo"]
    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        raise RuntimeError(f"Missing required columns: {missing}")

    for col in ["faceit_tracker_highest_elo", "peak_elo_source", "peak_elo_updated_at", "peak_elo_url_nickname"]:
        if col not in df.columns:
            df[col] = ""

    df["faceit_tracker_highest_elo"] = pd.to_numeric(
        df["faceit_tracker_highest_elo"], errors="coerce"
    ).fillna(0).astype(int)

    df["peak_elo_source"] = df["peak_elo_source"].fillna("").astype("object")
    df["peak_elo_updated_at"] = df["peak_elo_updated_at"].fillna("").astype("object")
    df["peak_elo_url_nickname"] = df["peak_elo_url_nickname"].fillna("").astype("object")

    backup_path = DATA_PATH.with_name("brz_faceit_players_enriched_backup_before_tracker_peak_elo_playwright_scroll.csv")
    df.to_csv(backup_path, index=False, encoding="utf-8-sig")
    print(f"[OK] Backup saved to: {backup_path}")

    now = datetime.now(timezone.utc).isoformat()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        page = await browser.new_page(
            user_agent=USER_AGENT,
            viewport={"width": 1440, "height": 2200},
        )

        for idx, row in df.iterrows():
            official_nickname = str(
                row.get("faceit_nickname_official")
                or row.get("faceit_nickname_input")
                or ""
            ).strip()

            current_elo = parse_int(row.get("cs2_faceit_elo"), default=0)
            candidates = build_candidate_nicknames(row)

            if not official_nickname or not candidates:
                print(f"[WARN] {idx + 1}/{len(df)} missing nickname")
                continue

            try:
                extracted_peak, url_nickname, rendered_text = await fetch_tracker_highest_elo(page, candidates)
                final_peak, source = validate_peak(extracted_peak, current_elo)

                df.at[idx, "faceit_tracker_highest_elo"] = int(final_peak)
                df.at[idx, "peak_elo_source"] = str(source)
                df.at[idx, "peak_elo_updated_at"] = str(now)
                df.at[idx, "peak_elo_url_nickname"] = str(url_nickname or "")

                if source == "FACEIT_TRACKER_PLAYWRIGHT":
                    print(
                        f"[OK] {idx + 1}/{len(df)} {official_nickname} | "
                        f"tracker_highest_elo={final_peak} | url_nickname={url_nickname}"
                    )
                else:
                    debug_path = DEBUG_DIR / f"faceit_tracker_text_{safe_filename(official_nickname)}.txt"
                    debug_path.write_text(rendered_text or "", encoding="utf-8")

                    print(
                        f"[WARN] {idx + 1}/{len(df)} {official_nickname} | "
                        f"extracted={extracted_peak} | {source} | "
                        f"fallback_current_elo={final_peak} | debug={debug_path}"
                    )

                await page.wait_for_timeout(BETWEEN_PLAYERS_WAIT_MS)

            except Exception as exc:
                fallback = current_elo

                df.at[idx, "faceit_tracker_highest_elo"] = int(fallback)
                df.at[idx, "peak_elo_source"] = "CURRENT_ELO_FALLBACK_ERROR"
                df.at[idx, "peak_elo_updated_at"] = str(now)
                df.at[idx, "peak_elo_url_nickname"] = ""

                print(
                    f"[ERROR] {idx + 1}/{len(df)} {official_nickname} | {exc} | "
                    f"fallback_current_elo={fallback}"
                )

        await browser.close()

    df["faceit_tracker_highest_elo"] = pd.to_numeric(
        df["faceit_tracker_highest_elo"], errors="coerce"
    ).fillna(0).astype(int)

    df["peak_elo_source"] = df["peak_elo_source"].fillna("").astype(str)
    df["peak_elo_updated_at"] = df["peak_elo_updated_at"].fillna("").astype(str)
    df["peak_elo_url_nickname"] = df["peak_elo_url_nickname"].fillna("").astype(str)

    df.to_csv(DATA_PATH, index=False, encoding="utf-8-sig")

    print(f"[OK] Updated file: {DATA_PATH}")
    print(
        df[
            [
                "faceit_nickname_official",
                "cs2_faceit_elo",
                "faceit_tracker_highest_elo",
                "peak_elo_source",
                "peak_elo_url_nickname",
                "lifetime_faceit_matches",
            ]
        ].to_string(index=False)
    )


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
