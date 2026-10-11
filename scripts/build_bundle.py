"""Build the PyInstaller bundle for the current OS (folder by default, --onefile for a single exe)."""
import argparse
import subprocess
import sys

NAME = "AudioEnvironmentFingerprinter"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--onefile", action="store_true", help="build one self-extracting executable")
    args = parser.parse_args()
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
               "--paths", "src", "--collect-submodules", "audio_enviro_fingerprint"]
    try:
        import soundfile  # noqa: F401  (optional codec backend; bundle its native library when present)
        command += ["--hidden-import", "soundfile", "--collect-all", "_soundfile_data"]
    except ImportError:
        print("soundfile not installed; bundle will support PCM/float WAV only", file=sys.stderr)
    if args.onefile:
        command += ["--onefile", "--name", f"{NAME}-standalone"]
    else:
        command += ["--name", NAME]
    command.append("run_app.py")
    print(" ".join(command))
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
