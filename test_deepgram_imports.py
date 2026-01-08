try:
    from deepgram import LiveTranscriptionEvents
    print("SUCCESS: from deepgram import LiveTranscriptionEvents")
except ImportError:
    print("FAIL: from deepgram import LiveTranscriptionEvents")

try:
    from deepgram.clients.live.v1 import LiveTranscriptionEvents
    print("SUCCESS: from deepgram.clients.live.v1 import LiveTranscriptionEvents")
except ImportError:
    print("FAIL: from deepgram.clients.live.v1 import LiveTranscriptionEvents")

try:
    from deepgram.clients.live.enums import LiveTranscriptionEvents
    print("SUCCESS: from deepgram.clients.live.enums import LiveTranscriptionEvents")
except ImportError:
    print("FAIL: from deepgram.clients.live.enums import LiveTranscriptionEvents")
