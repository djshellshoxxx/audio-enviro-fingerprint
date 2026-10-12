"""Assert a smoke report carries the expected cross-platform fingerprint hash.

The smoke WAV is generated deterministically by make_smoke_wav.py, so every OS,
Python and NumPy build must produce exactly this aefp-2 fingerprint hash.
"""
import json
import sys

EXPECTED_FINGERPRINT_SHA256 = "f4fd15474d26f782c10f81bc7f5e4cef74fb345400270920603b8d13560b8342"


def main(path: str) -> int:
    with open(path, encoding="utf-8") as handle:
        actual = json.load(handle)["manifest"]["fingerprint_sha256"]
    if actual != EXPECTED_FINGERPRINT_SHA256:
        print(f"Fingerprint not reproducible: got {actual}, expected {EXPECTED_FINGERPRINT_SHA256}")
        return 1
    print(f"Fingerprint reproducible: {actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
