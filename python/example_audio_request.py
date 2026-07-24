"""Demonstrate how to emit audio data to Max using the max-client library.
"""

import time
from pathlib import Path

import soundfile as sf

from python_max import request, disconnect

WAV = Path(__file__).resolve().parent.parent / "test" / "Automatic_90_Am_GuitarRiff02.wav"
SNIPPET_FRAMES = 44100*10


def request_audio() -> None:
    """Push a stereo audio as a 2D array to Max"""
    data, sr = sf.read(WAV, frames=SNIPPET_FRAMES, dtype="float64")  # (frames, channels)
    audio = data.T.tolist() if data.ndim > 1 else [data.tolist()]   # [[ch0...], [ch1...]]
    payload = {
        "audio": audio,
        "sr": int(sr),
        "channels": len(audio),
        "frames": len(audio[0]),
    }
    result = request("request_audio", "dict", payload)

    result_audio = result.get("audio", [])
    result_channels = result.get("channels", 0)

    print(f"requested audio: channels={result_channels} frames={len(result_audio[0]) if result_audio else 0}")


def main() -> None:

    request_audio()

    time.sleep(0.1)
    disconnect()


if __name__ == "__main__":
    main()
