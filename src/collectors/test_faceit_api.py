import os
import requests
from dotenv import load_dotenv


load_dotenv()

FACEIT_API_KEY = os.getenv("FACEIT_API_KEY")

if not FACEIT_API_KEY:
    raise ValueError("FACEIT_API_KEY is missing. Check your .env file.")


headers = {
    "Authorization": f"Bearer {FACEIT_API_KEY}",
    "Accept": "application/json",
}

player_id = "50b900e5-261c-42f1-87ac-51bf6000e0ac"

url = f"https://open.faceit.com/data/v4/players/{player_id}/stats/cs2"

response = requests.get(
    url,
    headers=headers,
    timeout=30,
)

print("Status code:", response.status_code)
print("Response:")
print(response.text)