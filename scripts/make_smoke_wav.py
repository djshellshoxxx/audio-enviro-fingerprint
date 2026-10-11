"""Write a deterministic 16-bit PCM WAV with a mid-file spectral change for smoke tests."""
import math
import sys
import wave

RATE = 8000


def main(path: str) -> None:
    frames = bytearray()
    for n in range(RATE * 12):
        freq = 220 if n < RATE * 6 else 1800
        value = int(0.2 * 32767 * math.sin(2 * math.pi * freq * n / RATE))
        frames += value.to_bytes(2, "little", signed=True)
    with wave.open(path, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(bytes(frames))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "smoke.wav")
