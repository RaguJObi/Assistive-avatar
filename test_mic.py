import pyaudio
import wave

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 8000
RECORD_SECONDS = 5
WAVE_OUTPUT_FILENAME = "test_output.wav"

audio = pyaudio.PyAudio()

# List devices
print("Available Audio Devices:")
for i in range(audio.get_device_count()):
    dev = audio.get_device_info_by_index(i)
    if dev.get('maxInputChannels') > 0:
        print(f"Index {i}: {dev.get('name')}")

print("-" * 20)
print("Recording for 5 seconds... SPEAK NOW!")

try:
    stream = audio.open(format=FORMAT, channels=CHANNELS,
                        rate=RATE, input=True,
                        frames_per_buffer=CHUNK)
    frames = []

    for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK)
        frames.append(data)
        print(".", end="", flush=True)

    print("\nFinished recording.")
    stream.stop_stream()
    stream.close()
    audio.terminate()

    with wave.open(WAVE_OUTPUT_FILENAME, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
    
    print(f"Saved to {WAVE_OUTPUT_FILENAME}. Please inspect file size > 44 bytes.")

except Exception as e:
    print(f"Error: {e}")
