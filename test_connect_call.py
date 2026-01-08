from deepgram import DeepgramClient
import os
from dotenv import load_dotenv

load_dotenv()
client = DeepgramClient(api_key=os.getenv("DEEPGRAM_API_KEY"))

try:
    print("Calling client.listen.v1.connect()...")
    res = client.listen.v1.connect()
    print(f"Result type: {type(res)}")
    print(f"Result dir: {dir(res)}")
except Exception as e:
    print(f"Error calling connect(): {e}")
