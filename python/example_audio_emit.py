"""Demonstrate how to emit audio data to Max using the max-client library.
"""

import time
from pathlib import Path

import soundfile as sf

from python_max import emit, disconnect

WAV = Path(__file__).resolve().parent.parent / "test" / "Automatic_90_Am_GuitarRiff02.wav"
SNIPPET_FRAMES = 44100*10


def emit_audio() -> None:
    """Push a stereo audio as a 2D array to Max"""
    data, sr = sf.read(WAV, frames=SNIPPET_FRAMES, dtype="float64")  # (frames, channels)
    audio = data.T.tolist() if data.ndim > 1 else [data.tolist()]   # [[ch0...], [ch1...]]
    payload = {
        "audio": audio,
        "sr": int(sr),
        "channels": len(audio),
        "frames": len(audio[0]),
    }
    emit("emit_audio", "dict", payload)
    print(f"emitted audio: channels={len(audio)} frames={len(audio[0])} sr={int(sr)}")


def main() -> None:

    emit_audio()

    time.sleep(0.1)
    disconnect()


if __name__ == "__main__":
    main()
