import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("DEEPGRAM_API_KEY")

print(f"Key: {api_key[:5]}...{api_key[-5:] if api_key else 'None'}")

url = "https://api.deepgram.com/v1/projects"
headers = {
    "Authorization": f"Token {api_key}",
    "Content-Type": "application/json"
}

try:
    print(f"Requesting {url}...")
    response = requests.get(url, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
