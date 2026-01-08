import asyncio
import logging
import time
import queue
import sys
from dotenv import load_dotenv

from utils.audio_utils import AudioStream
from services.stt_service import STTService
from services.rag_engine import RAGEngine
from services.llm_service import LLMService
from services.tts_service import TTSService
from services.vision_service import VisionService

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Main")

class S2SPipeline:
    def __init__(self, loop):
        self.loop = loop
        self.audio_stream = AudioStream()
        self.rag_engine = RAGEngine()
        self.model = LLMService(self.handle_llm_token)
        self.tts = TTSService()
        self.stt = STTService(self.handle_transcription, self.loop)
        
        # Vision Service
        self.vision = VisionService(self.handle_vision_trigger)
        
        self.tts_queue = asyncio.Queue()
        self.playback_queue = queue.Queue()
        
        # Latency Metrics
        self.metrics = {
            "vad_detected": 0,
            "stt_final": 0,
            "ttft": 0, # Time to First Token
            "ttfa": 0  # Time to First Audio
        }
        
        self.is_listening = False
        self.is_speaking = False
    def handle_vision_trigger(self):
        """Called when a face is detected for 2+ seconds."""
        logger.info("Vision Trigger! Scheduling greeting.")
        
        # Verify we aren't already listening/speaking to avoid double trigger
        if self.is_speaking or self.is_listening_active_conversation: 
             # Ideally we check if conversation has started. 
             pass

        # Use call_soon_threadsafe to jump from Vision Thread to Asyncio Loop
        self.loop.call_soon_threadsafe(
            lambda: asyncio.create_task(self.play_greeting())
        )
            
    # Add a flag for 'active conversation' (listening is always true in loop, but we mean semantic listening)
    # For now, simplistic check:
    @property
    def is_listening_active_conversation(self):
        return self.is_speaking # Rough proxy to prevent self-interruption from greeting

    async def play_greeting(self):
        """Plays the welcome message."""
        if self.is_speaking:
            return

        greeting_text = "Hello! Welcome to the IITM Research Park. I am the Director's AI assistant. How can I guide you today?"
        logger.info(f"Greeting User: {greeting_text}")
        
        try:
            audio_generator = self.tts.text_to_audio_stream(greeting_text)
            
            self.is_speaking = True
            # Open output stream if not already handled generally (it's opened in start())
            
            try:
                for audio_chunk in audio_generator:
                     if self.output_stream:
                        self.output_stream.write(audio_chunk)
            finally:
                await asyncio.sleep(1.0)
                self.is_speaking = False
        except Exception as e:
            logger.error(f"Error playing greeting: {e}")

    async def start(self):
        logger.info("Starting S2S Pipeline...")
        
        # Start Output Stream (Running in background thread handled by PyAudio, feed via queue)
        self.output_stream = self.audio_stream.start_output_stream()
        
        # Start STT
        if not await self.stt.start():
            logger.error("Could not start STT. Exiting.")
            return
            
        # Start Vision
        self.vision.start()

        # Start Mic Input
        self.audio_stream.start_input_stream(self.mic_callback)
        
        self.is_listening = True
        logger.info("Listening... (Press Ctrl+C to stop)")
        
        # Start TTS consumer task
        asyncio.create_task(self.process_tts_queue())

        try:
            while self.is_listening:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            self.stop()

    def stop(self):
        self.is_listening = False
        self.vision.stop()
        self.audio_stream.stop_streams()
        asyncio.run_coroutine_threadsafe(self.stt.stop(), self.loop)
        logger.info("Pipeline stopped.")

    def mic_callback(self, in_data, frame_count, time_info, status):
        """Pushes audio to STT"""
        # Echo Cancellation: Don't listen if we are speaking
        if self.is_speaking:
            return (None, 0)
            
        # debug print every ~1 second (assuming 16k rate, 8k chunk = 0.5s)
        print(".", end="", flush=True) 
        asyncio.run_coroutine_threadsafe(self.stt.send_audio(in_data), self.loop)
        return (None, 0) # Continue

    async def handle_transcription(self, is_final, text, confidence=0.0):
        """Called when deepgram returns a transcript"""
        if is_final:
            logger.info(f"User: {text} (Confidence: {confidence:.2f})")
            self.metrics["stt_final"] = time.time()
            self.metrics["stt_confidence"] = confidence
            self.metrics["input_text"] = text
            
            # 1. RAG Search
            self.metrics["rag_start"] = time.time()
            context = self.rag_engine.search(text)
            self.metrics["rag_end"] = time.time()
            if context:
                logger.info(f"RAG Context Found: {context[:50]}...")
            
            # 2. Send to LLM
            logger.info("Sending to LLM...")
            # Reset metrics for new turn
            self.metrics["ttft"] = 0
            self.metrics["ttfa"] = 0
            self.metrics["llm_start"] = time.time()
            self.metrics["llm_tokens"] = 0
            self.metrics["llm_end"] = 0
            
            await self.model.process_text(text, context)

    async def handle_llm_token(self, text):
        """Called when LLM generates a token"""
        if self.metrics["ttft"] == 0:
            self.metrics["ttft"] = time.time()
            latency = (self.metrics["ttft"] - self.metrics["stt_final"]) * 1000
            logger.info(f"Time to First Token (TTFT): {latency:.2f}ms")

        self.metrics["llm_tokens"] += 1
        self.metrics["llm_end"] = time.time() # Continually update last token time

        # Accumulate text for TTS?
        await self.tts_queue.put(text)

    async def process_tts_queue(self):
        """Consumes text from queue and sends to TTS"""
        buffer = ""
        import re
        
        while self.is_listening:
            try:
                # Wait for next chunk
                text_chunk = await self.tts_queue.get()
                buffer += text_chunk
                
                # Check for sentence terminators
                # We want to find the last punctuation mark that ends a sentence.
                # Regex looking for [.!?] followed by space or end of string? 
                # Actually simpler: just split by [.!?] and keep the delimiters.
                
                # If buffer has complex structure: "Hello! How are you. I am fine"
                # We want to send "Hello!" then "How are you."
                # and keep "I am fine" in buffer.
                
                if re.search(r'[.!?]', buffer):
                    # Smart split: Look for punctuation followed by space or end of string
                    parts = re.split(r'([.!?])', buffer)
                    
                    # parts will look like: ['Hello', '!', ' How are you', '.', ' I am fine']
                    # We want to combine them back into sentences.
                    
                    to_speak_list = []
                    remainder = ""
                    
                    # Iterate in pairs (text + punct)
                    for i in range(0, len(parts) - 1, 2):
                        sentence = parts[i] + parts[i+1]
                        to_speak_list.append(sentence)
                    
                    # The last part is the remainder (it didn't have a following punctuation group)
                    remainder = parts[-1]
                    
                    # If the last character of buffer WAS a punctuation, then remainder is empty,
                    # EXCEPT split behavior might leave an empty string at end if separator is at end.
                    # 'Hello.'.split -> ['Hello', '.', '']
                    
                    if remainder.strip() == "":
                        remainder = ""
                    
                    # Now send complete sentences
                    for sentence in to_speak_list:
                        sentence = sentence.strip()
                        if not sentence: continue
                        
                        logger.info(f"Generating TTS for: {sentence}")
                        
                        self.metrics["tts_start"] = time.time()
                        self.metrics["tts_chars"] = len(sentence)
                        
                        audio_generator = self.tts.text_to_audio_stream(sentence)
                        
                        self.is_speaking = True
                        first_chunk = True
                        try:
                            for audio_chunk in audio_generator:
                                if first_chunk:
                                    self.metrics["tts_audio_start"] = time.time()
                                    if self.metrics["ttfa"] == 0:
                                        self.metrics["ttfa"] = time.time()
                                        latency = (self.metrics["ttfa"] - self.metrics["stt_final"]) * 1000
                                        logger.info(f"Time to First Audio (TTFA): {latency:.2f}ms")
                                    first_chunk = False
                                
                                if self.output_stream:
                                    self.output_stream.write(audio_chunk)
                            
                            self.metrics["tts_end"] = time.time()
                            self.print_metrics()
                            
                        finally:
                            # Small breather between sentences is natural
                            await asyncio.sleep(0.5) 
                            self.is_speaking = False
                    
                    # Update buffer with what's left
                    buffer = remainder

            except Exception as e:
                logger.error(f"TTS Consumer Error: {e}")

    def print_metrics(self):
        """Prints a nicely formatted performance report."""
        try:
            rag_lat = (self.metrics.get("rag_end", 0) - self.metrics.get("rag_start", 0)) * 1000
            llm_lat = (self.metrics.get("ttft", 0) - self.metrics.get("llm_start", 0)) * 1000
            tts_lat = (self.metrics.get("tts_audio_start", 0) - self.metrics.get("tts_start", 0)) * 1000
            total_lat = (self.metrics.get("ttfa", 0) - self.metrics.get("stt_final", 0)) * 1000
            
            # Throughput
            llm_dur = self.metrics.get("llm_end", 0) - self.metrics.get("llm_start", 0)
            llm_tps = self.metrics.get("llm_tokens", 0) / llm_dur if llm_dur > 0 else 0
            
            tts_dur = self.metrics.get("tts_end", 0) - self.metrics.get("tts_start", 0)
            tts_cps = self.metrics.get("tts_chars", 0) / tts_dur if tts_dur > 0 else 0
            
            print("\n" + "="*60)
            print(f"📊 PERFORMANCE METRICS REPORT")
            print("="*60)
            print(f"🎤 Input: '{self.metrics.get('input_text', '...')[:50]}...' (Conf: {self.metrics.get('stt_confidence', 0):.2f})")
            print("-" * 60)
            print(f"1. RAG Retrieval    : {rag_lat:8.2f} ms")
            print(f"2. LLM Time to 1st  : {llm_lat:8.2f} ms | Speed: {llm_tps:6.2f} tokens/s")
            print(f"3. TTS Generation   : {tts_lat:8.2f} ms | Speed: {tts_cps:6.2f} chars/s")
            print("-" * 60)
            print(f"⚡ TOTAL LATENCY    : {total_lat:8.2f} ms")
            print("="*60 + "\n")
        except Exception as e:
            logger.error(f"Error printing metrics: {e}")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    pipeline = S2SPipeline(loop)
    
    try:
        loop.run_until_complete(pipeline.start())
    except KeyboardInterrupt:
        logger.info("Stopping...")
        pipeline.stop()
