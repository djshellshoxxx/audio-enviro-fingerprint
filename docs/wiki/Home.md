# Audio Environment Fingerprinter Wiki

A local desktop and command-line research workstation for reproducible acoustic-environment screening. It hashes original file bytes separately from the versioned acoustic fingerprint. A cryptographic evidence hash identifies bytes; descriptor similarity does not identify a physical location or establish authenticity.

This wiki consolidates the user/developer navigation from the historical `docs/wiki` and `docs/readme-and-wiki` branches. The current [specification](../SPECIFICATIONS_V2.md), [project status](../../PROJECT_STATUS.md) and [validation protocol](../BENCHMARK_PROTOCOL.md) are authoritative.

## Start here

1. Install with Python 3.10 or newer: `python -m pip install -e .`.
2. Launch `python -m audio_enviro_fingerprint`, then open an audio recording.
3. Review descriptors, transition and recurrence candidates, musical/hum measurements and channels.
4. Save evidence-bound notes, markers and acquisition documentation.
5. Export a report and verify its JSON manifest with the CLI.

## Pages

- [User guide](User-Guide.md)
- [Developer overview](Developer-Overview.md)
- [Code map](Developer-Code-Map.md)
- [Build and test](Developer-Build-and-Test.md)
- [Development conventions](Developer-Conventions.md)
- [Branch reconciliation](../BRANCH_RECONCILIATION.md)

The methods and thresholds are not calibrated on representative field recordings. Output requires examiner review. The manifest detects modification; it is not a digital signature or complete chain of custody.
