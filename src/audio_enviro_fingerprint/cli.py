"""Headless command line: analyze, compare, verify-report, benchmark.

    python -m audio_enviro_fingerprint.cli analyze recording.wav --out report.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys

from . import __version__
from .benchmark import format_summary, run_benchmark
from .audio_io import load_audio
from .comparison import compare_fingerprints
from .methods.reverberation import estimate_t20
from .pipeline import DEFAULT_SETTINGS, analyze_file, bundle_report
from .report import verify_report, write_report

CAVEAT = ("Descriptive screening output only: not a location identification, probability of common "
          "origin, or authenticity finding. Thresholds are unvalidated beta defaults.")


def _add_settings(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--channel", type=int, default=0, help="zero-based channel to analyze (default 0)")
    parser.add_argument("--frame-seconds", type=float, default=DEFAULT_SETTINGS["frame_seconds"])
    parser.add_argument("--hop-seconds", type=float, default=DEFAULT_SETTINGS["hop_seconds"])
    parser.add_argument("--threshold", type=float, default=DEFAULT_SETTINGS["transition_threshold"],
                        help="transition candidate threshold (heuristic)")


def _settings(args) -> dict:
    return {"frame_seconds": args.frame_seconds, "hop_seconds": args.hop_seconds,
            "transition_threshold": args.threshold}


def _json_safe(value):
    """Replace non-finite floats (e.g. an undefined AUC) with None for strict JSON output."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _analyze(args) -> int:
    bundle = analyze_file(args.recording, args.channel, _settings(args))
    report = bundle_report(bundle, __version__)
    if args.out:
        write_report(report, args.out)
        print(f"Report written to {args.out}")
    else:
        print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    print(f"Evidence SHA-256: {bundle.sha256}", file=sys.stderr)
    print(f"Fingerprint {bundle.fingerprint.version}: {bundle.fingerprint.fingerprint_hash}", file=sys.stderr)
    print(f"{len(bundle.transitions)} transition candidate(s); {len(bundle.recurrences)} recurrence candidate(s)",
          file=sys.stderr)
    return 0


def _compare(args) -> int:
    first = analyze_file(args.first, args.channel, _settings(args)).fingerprint
    second = analyze_file(args.second, args.channel, _settings(args)).fingerprint
    result = compare_fingerprints({"version": first.version, "features": first.features},
                                  {"version": second.version, "features": second.features})
    if args.json:
        print(json.dumps({"score": result.score, "distance": result.distance, "differences": result.differences,
                          "contributions": result.contributions, "groups": result.groups,
                          "explanation": result.explanation, "caveat": CAVEAT},
                         indent=2, sort_keys=True, allow_nan=False))
        return 0
    print(f"{'feature':<28}{'first':>12}{'second':>12}{'delta':>12}{'norm':>8}{'share':>8}")
    for key, item in sorted(result.differences.items(), key=lambda kv: -result.contributions[kv[0]]):
        print(f"{key:<28}{item['first']:>12.3f}{item['second']:>12.3f}{item['delta']:>+12.3f}"
              f"{item['normalized_delta']:>8.2f}{result.contributions[key]:>8.1%}")
    print(f"\nDescriptive score {result.score:.3f} (distance {result.distance:.3f})")
    print(result.explanation)
    print(CAVEAT)
    return 0


def _verify(args) -> int:
    result = verify_report(args.report, evidence_path=args.evidence)
    for name, check in result["checks"].items():
        print(f"[{'PASS' if check['ok'] else 'FAIL'}] {name}: {check['detail']}")
    print("Report verification " + ("passed" if result["ok"] else "FAILED"))
    return 0 if result["ok"] else 1


def _rt60(args) -> int:
    audio = load_audio(args.impulse_response, args.channel)
    result = estimate_t20(audio.samples, audio.sample_rate)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    else:
        print(f"RT60 (T20 extrapolation): {result['rt60_seconds']:.3f} s; decay slope "
              f"{result['decay_slope_db_per_second']:.1f} dB/s over {result['range_db']:.1f} dB; "
              f"fit RMSE {result['fit_rmse_db']:.2f} dB ({result['method']})")
    print("Experimental: valid only for a measured room impulse response; not an ISO 3382 measurement.",
          file=sys.stderr)
    return 0


def _benchmark(args) -> int:
    result = run_benchmark(seed=args.seed, quick=args.quick)
    if args.json:
        print(json.dumps(_json_safe(result), indent=2, sort_keys=True, allow_nan=False))
    else:
        print(format_summary(result))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aefp", description="Audio Environment Fingerprinter (research beta)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser("analyze", help="analyze one recording and write a report")
    analyze.add_argument("recording")
    analyze.add_argument("--out", help="report JSON path (default: print to stdout)")
    _add_settings(analyze)
    analyze.set_defaults(handler=_analyze)
    compare = commands.add_parser("compare", help="explainable comparison of two recordings")
    compare.add_argument("first")
    compare.add_argument("second")
    compare.add_argument("--json", action="store_true")
    _add_settings(compare)
    compare.set_defaults(handler=_compare)
    verify = commands.add_parser("verify-report", help="recompute report manifest hashes")
    verify.add_argument("report")
    verify.add_argument("--evidence", help="original evidence file to re-hash")
    verify.set_defaults(handler=_verify)
    rt60 = commands.add_parser("rt60", help="experimental Schroeder T20 decay estimate from an impulse response")
    rt60.add_argument("impulse_response")
    rt60.add_argument("--channel", type=int, default=0)
    rt60.add_argument("--json", action="store_true")
    rt60.set_defaults(handler=_rt60)
    bench = commands.add_parser("benchmark", help="run the synthetic software benchmark")
    bench.add_argument("--quick", action="store_true")
    bench.add_argument("--seed", type=int, default=0)
    bench.add_argument("--json", action="store_true")
    bench.set_defaults(handler=_benchmark)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
