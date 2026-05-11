import os

import requests
from dotenv import load_dotenv


load_dotenv()

STEAM_API_KEY = os.getenv("STEAM_API_KEY")
BASE_URL = "https://api.steampowered.com"


def fetch_player_summary_by_steam64(steam64_id: str) -> dict:
    """
    Fetch public Steam profile summary using Steam64 ID.
    """
    if not STEAM_API_KEY:
        raise ValueError("STEAM_API_KEY is missing. Check your .env file.")

    url = f"{BASE_URL}/ISteamUser/GetPlayerSummaries/v0002/"

    params = {
        "key": STEAM_API_KEY,
        "steamids": steam64_id,
        "format": "json",
    }

    response = requests.get(
        url,
        params=params,
        timeout=30,
    )

    payload = None
    error_message = None

    try:
        payload = response.json()
    except ValueError:
        error_message = response.text

    if response.status_code >= 400:
        error_message = error_message or str(payload)

    players = []

    if payload:
        players = payload.get("response", {}).get("players", [])

    player = players[0] if players else None

    return {
        "status_code": response.status_code,
        "request_url": response.url,
        "payload": payload,
        "player": player,
        "error_message": error_message,
    }