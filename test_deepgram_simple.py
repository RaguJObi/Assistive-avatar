import asyncio
import os
import logging
from deepgram import AsyncDeepgramClient
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestDeepgramDict")

async def test():
    api_key = os.getenv("DEEPGRAM_API_KEY")
    client = AsyncDeepgramClient(api_key=api_key)
    
    options = {
        "model": "nova-2",
        "language": "en-US",
        "smart_format": "true", # Trying string bools
        "interim_results": "true",
        "encoding": "linear16",
        "sample_rate": 16000,
        "channels": 1,
    }
    
    try:
        logger.info("Connecting with options dict...")
        # Try passing as 'options' kwarg? Or just **options?
        # Previous attempt was **options.
        # Let's try passing 'model' etc, but maybe smart_format needs to be bool?
        # I used True (bool) before.
        
        # Let's try NO OPTIONS just generic model.
        conn_ctx = client.listen.v1.connect(model="nova-2")
        
        dg_connection = await conn_ctx.__aenter__()
        
        # Handlers
        def on_open(self, open, **kwargs):
            logger.info(f"OPENED: {open}")
            
        def on_message(self, result, **kwargs):
            transcript = result.channel.alternatives[0].transcript
            if transcript:
                logger.info(f"Transcript: {transcript}")
                
        def on_error(self, error, **kwargs):
            logger.error(f"Error: {error}")

        dg_connection.on("Open", on_open)
        dg_connection.on("Results", on_message)
        dg_connection.on("Error", on_error)
        
        if hasattr(dg_connection, 'start_listening'):
            logger.info("Calling start_listening...")
            res = dg_connection.start_listening()
            if asyncio.iscoroutine(res):
                await res
        
        # Send a bit of audio (silence or noise)
        logger.info("Sending silence...")
        auth_bytes = b'\x00' * 8000
        for _ in range(5):
            await dg_connection.send_media(auth_bytes)
            await asyncio.sleep(0.1)
        
        logger.info("Waiting...")
        await asyncio.sleep(2)
        await conn_ctx.__aexit__(None, None, None)
        
    except Exception as e:
        logger.error(f"Test failed: {e}")

asyncio.run(test())
