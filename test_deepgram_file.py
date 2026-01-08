import asyncio
import os
import logging
from deepgram import AsyncDeepgramClient
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestDeepgram")

async def test():
    api_key = os.getenv("DEEPGRAM_API_KEY")
    client = AsyncDeepgramClient(api_key=api_key)
    
    # Options
    options = {
        "model": "nova-2", # Trying nova-2 for stability check
        "language": "en-US",
        "smart_format": True,
        "interim_results": True,
        "encoding": "linear16",
        "sample_rate": 16000,
        "channels": 1,
    }
    
    try:
        # Connect
        logger.info("Connecting...")
        conn_ctx = client.listen.v1.connect(**options)
        dg_connection = await conn_ctx.__aenter__()
        
        open_event = asyncio.Event()

        # Handlers
        def on_open(self, open, **kwargs):
            logger.info(f"OPENED: {open}")
            open_event.set()
            
        def on_message(self, result, **kwargs):
            transcript = result.channel.alternatives[0].transcript
            if transcript:
                logger.info(f"Transcript: {transcript}")
                
        def on_error(self, error, **kwargs):
            logger.error(f"Error: {error}")

        dg_connection.on("Open", on_open)
        dg_connection.on("Results", on_message)
        dg_connection.on("Error", on_error)
        
        # Start Listening?
        if hasattr(dg_connection, 'start_listening'):
            logger.info("Calling start_listening...")
            res = dg_connection.start_listening()
            if asyncio.iscoroutine(res):
                await res
        
        logger.info("Waiting for Open event...")
        try:
            await asyncio.wait_for(open_event.wait(), timeout=5.0)
            logger.info("Connection confirmed open!")
        except asyncio.TimeoutError:
            logger.error("Timed out waiting for Open event.")
            return

        logger.info("Sending audio...")
        with open("test_output.wav", "rb") as f:
            # Skip header (44 bytes for standard WAV)
            data = f.read()[44:] 
            
            # Send in chunks
            CHUNK = 8000
            for i in range(0, len(data), CHUNK):
                chunk = data[i:i+CHUNK]
                logger.info(f"Sending chunk {i} ({len(chunk)} bytes)")
                await dg_connection.send_media(chunk)
                await asyncio.sleep(0.1) # Slower send rate
                
        logger.info("Finished sending. Waiting 5s...")
        await asyncio.sleep(5)
        
        await conn_ctx.__aexit__(None, None, None)
        logger.info("Closed.")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")

asyncio.run(test())
