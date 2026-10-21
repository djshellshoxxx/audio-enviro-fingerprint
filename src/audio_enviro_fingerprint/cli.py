"""Headless command line interface for batch screening and report verification."""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .comparison import compare_fingerprints
from .pipeline import analyze_file, full_report
from .recurrence import find_recurrences
from .report import verify_report, write_report
from .spectrogram import spectrogram_png


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="audio-enviro-fingerprint",
                                     description="Explainable acoustic environment screening.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("analyze", help="analyze a WAV and write a verifiable JSON report")
    a.add_argument("wav")
    a.add_argument("-o", "--output", help="report path (default: stdout)")
    a.add_argument("--no-musical", action="store_true", help="skip key/tempo/pitch analysis")
    c = sub.add_parser("compare", help="explainable comparison of two WAV files")
    c.add_argument("first")
    c.add_argument("second")
    r = sub.add_parser("recurrence", help="find where the second recording's environment appears in the first")
    r.add_argument("first")
    r.add_argument("second")
    s = sub.add_parser("spectrogram", help="render a spectrogram PNG")
    s.add_argument("wav")
    s.add_argument("output")
    v = sub.add_parser("verify", help="verify a report manifest and its evidence hash")
    v.add_argument("report")
    return parser


def run(argv: list[str]) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "analyze":
            report = full_report(analyze_file(args.wav, musical=not args.no_musical))
            if args.output:
                write_report(args.output, report)
                print(f"Report written to {args.output} (body sha256 {report['manifest']['body_sha256']})")
            else:
                print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
        elif args.command == "compare":
            x, y = analyze_file(args.first, musical=False), analyze_file(args.second, musical=False)
            fx, fy = x["fingerprint"], y["fingerprint"]
            result = compare_fingerprints({"version": fx.version, "features": fx.features},
                                          {"version": fy.version, "features": fy.features})
            print(result.explanation)
            for key, item in result.differences.items():
                print(f"{key:40s} {item['first']:>12.4f} {item['second']:>12.4f} {item['delta']:+.4f}")
        elif args.command == "recurrence":
            x, y = analyze_file(args.first, musical=False), analyze_file(args.second, musical=False)
            found = find_recurrences(x["analysis"], y["analysis"])
            print(json.dumps([m.to_dict() for m in found], indent=2, allow_nan=False))
        elif args.command == "spectrogram":
            from .audio_io import load_wav
            audio = load_wav(args.wav)
            with open(args.output, "wb") as out:
                out.write(spectrogram_png(audio.samples, audio.sample_rate))
        elif args.command == "verify":
            result = verify_report(args.report)
            print(json.dumps(result))
            return 0 if result["manifest_ok"] and result["evidence_ok"] is not False else 2
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(sys.argv[1:] if argv is None else argv)
