import os

import requests
from dotenv import load_dotenv


load_dotenv()

LEETIFY_API_KEY = os.getenv("LEETIFY_API_KEY")
BASE_URL = "https://api-public.cs-prod.leetify.com"


def fetch_profile_by_steam64(steam64_id: str) -> dict:
    """
    Fetch a Leetify profile using a Steam64 ID.

    Returns a dictionary with request metadata and payload.
    """
    if not LEETIFY_API_KEY:
        raise ValueError("LEETIFY_API_KEY is missing. Check your .env file.")

    url = f"{BASE_URL}/v3/profile"

    headers = {
        "Authorization": LEETIFY_API_KEY,
        "_leetify_key": LEETIFY_API_KEY,
        "Accept": "application/json",
    }

    params = {
        "steam64_id": steam64_id,
    }

    response = requests.get(
        url,
        headers=headers,
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

    return {
        "status_code": response.status_code,
        "request_url": response.url,
        "payload": payload,
        "error_message": error_message,
    }