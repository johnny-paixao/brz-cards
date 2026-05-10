import os
from pprint import pprint

import requests
from dotenv import load_dotenv


load_dotenv()

LEETIFY_API_KEY = os.getenv("LEETIFY_API_KEY")

BASE_URL = "https://api-public.cs-prod.leetify.com"


def get_leetify_profile_by_steam64(steam64_id: str) -> dict:
    """
    Fetch a Leetify player profile using Steam64 ID.
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

    print(f"Request URL: {response.url}")
    print(f"Status code: {response.status_code}")

    if response.status_code >= 400:
        print("Response body:")
        print(response.text)
        response.raise_for_status()

    return response.json()


def main() -> None:
    steam64_id = "76561197977881703"

    profile = get_leetify_profile_by_steam64(steam64_id)

    print("\nLeetify profile response:")
    pprint(profile)

    print("\nResumo:")
    print(f"Name: {profile.get('name')}")
    print(f"Leetify ID: {profile.get('id')}")
    print(f"Steam64 ID: {profile.get('steam64_id')}")
    print(f"Privacy mode: {profile.get('privacy_mode')}")
    print(f"Total matches: {profile.get('total_matches')}")
    print(f"Winrate: {profile.get('winrate')}")


if __name__ == "__main__":
    main()