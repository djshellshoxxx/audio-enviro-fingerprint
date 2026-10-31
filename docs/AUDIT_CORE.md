# Core input, evidence, storage and report audit

Task AEF-102; owner: core audit worker; status: IN_REVIEW. Reviewed the integrated working tree based on `4343f34f509216dbecd4e1dd6c86542fe913d672`, including concurrent uncommitted changes. This is a software contract audit, not scientific validation. The coordinator assigned and integrated the fixes described below in this working tree; no commit was created by this worker.

## Requirements and coverage

Sources: `SPECIFICATIONS.md` (input, integrity, evidence notes/export, error handling) and `SPECIFICATIONS_V2.md` (RIFF/RF64, compressed decode, cancellation, manifest, report provenance). Later additions supersede the initial single-channel-only implementation description.

| Module | Reviewed behavior and evidence | Result |
|---|---|---|
| `audio_io.py` | PCM/float/extensible header validation, declared-container bounds, RF64 ds64, channel preservation, decoded-byte limits, bounded metadata reads | Native resource-limit fix passes focused regression checks; RF64 table finding below |
| `codec_io.py` | First audio stream, decoder provenance, local protocol/demuxer restrictions, sample/channel limits, subprocess timeouts, temporary directory cleanup, decoded-size bound | Exact-size boundary corrected in current working tree; no additional reproducible defect established |
| `integrity.py` | Byte hashing, cancellation loop, atomic export, source/database alias protection, temporary-file cleanup | Hash parameter finding below; atomic export regression coverage exists |
| `report.py` | Canonical finite JSON, manifest body exclusion, original-source rehash before export, evidence verification, cancellation before publication | Existing manifest and export safety tests support documented integrity behavior; no signatures/authenticity promised |
| `case_store.py` | Evidence identity `(path,digest)`, UTC metadata, foreign keys, parameterized SQL, finite note/marker times, append-only marker/reference behavior, marker ownership, strict reference JSON | No additional reproducible defect established within stated single-user local database scope |
| `pipeline.py` | Hash pinned before/after, stage progress/cancellation, result publication only after successful checks, decoder provenance/report sections | Nonregular-source hang below |
| `control.py` | Cancellation exception and callback dispatch | Small explicit contract matches callers; no additional defect established |

## Findings and implemented corrections

### CORE-01 — P2, FIXED: nonregular evidence blocks before input validation

`pipeline.analyze_file` resolves the path and calls `sha256_file` before `load_audio` enforces a regular local file. A named pipe resolves successfully, then blocks at the hashing function's `open`, before any cancellation checkpoint can run. This affects CLI analysis and the GUI worker; setting Cancel cannot release the blocked open.

Reproduced on POSIX with a temporary FIFO named `recording.wav`, invoking `analyze_file(path, musical=False)` in a child Python process. The child exceeded a 0.5-second timeout and was terminated. A normal WAV need not be created or consumed to trigger this defect.

Acceptance: reject a FIFO/nonregular source with a clear `ValueError` before opening it for hashing. Add a POSIX-only subprocess regression with a short timeout (to keep the regression itself safe). Include a regular-file analysis control. Consider the same policy for public hashing/registration and verify paths where relevant; direct access checks cannot eliminate concurrent path replacement races.

### CORE-02 — P2, FIXED: zero hash chunk returns an incorrect evidence digest

`sha256_file(path, chunk_size=0)` reads zero bytes and immediately returns the SHA-256 of the empty string, even for nonempty evidence. A negative chunk size reads the entire file, defeating the documented bounded hashing behavior. The exposed `chunk_size` parameter has no validation.

Reproduced with `b'evidence'`: zero chunk returned `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` instead of the actual file digest. Default callers are unaffected.

Acceptance: require a positive integer chunk size (reject booleans), fail before opening the file for invalid settings, and verify custom positive sizes against `hashlib.sha256`. Preserve cancellation behavior and the 1 MiB default.

### CORE-03 — P2, FIXED: valid RF64 ancillary size-table entries are ignored

The RF64 parser reads and validates `ds64.tableLength` but discards its entries. Only `ds64.dataSize` is retained. Therefore an ancillary RF64 chunk with a `0xffffffff` size and a valid corresponding ds64 table entry is treated as an enormous ordinary chunk and rejected. The advertised RF64 contract has no documented restriction excluding size-table chunks.

Reproduced with a tiny valid RF64 fixture containing: ds64 with one `(JUNK, 4)` table entry; normal PCM fmt; `JUNK` sentinel-size chunk with four bytes; sentinel-size data chunk with eight bytes and ds64 dataSize=8/sampleCount=4. Loading fails with `WAV chunk exceeds the declared RIFF/RF64 container`.

Acceptance: consume matching table entries for sentinel-sized non-data chunks, retain strict declared-container bounds, and reject missing/truncated table entries. Handle repeated chunk IDs in table order rather than collapsing entries into a dictionary. Test successful decode and ancillary skipping with the fixture above plus repeated IDs and malformed table coverage. If broad RF64 support is intentionally deferred, document the exact restriction consistently instead of implying general support.

## Verified checks and limits

Earlier AEF-001 focused run: 38 tests passed across `test_wav_limits`, `test_numeric_contracts`, `test_input_hardening`, and `test_extended`. It covered native float64 decoded-size accounting for mono/stereo PCM/float, inclusive exact boundary, RF64 main data size, bool/invalid limit validation, early allocation rejection, and ancillary skipping. Coordinator owns a fresh integrated full-suite result; concurrent worker red phases must not be reported as final baseline failures.

Existing cancellation tests cover pre-start and frame/stage cancellation. Decoder and musical stages remain intentionally not immediately interruptible. The native limit bounds final float64 sample bytes, not total process resident memory or temporary decoding/analysis arrays. Full streaming and large field-recording performance validation remain unimplemented, explicitly acknowledged in the specifications.

Field calibration, independent report verifier, crash/recovery validation, signing, access control, encryption, and complete chain-of-custody functionality remain absent or externally dependent. These are documented boundaries rather than claims established by passing unit tests. Review did not assess adversarial filesystem races as a complete security guarantee.

## AEF-102 implementation handoff

CORE-01: `integrity.evidence_stat(path)` rejects nonregular files before opening them and returns `(st_dev, st_ino, st_size, st_mtime_ns, st_ctime_ns)`. Hashing and the pipeline use this regular-file check; direct native WAV entry also rejects nonregular paths. Pipeline results carry `source_stat` captured before the first hash and checked after the final hash. This supports the coordinated GUI/CaseStore verified-registration API without rehashing on Tk. The token detects ordinary file identity/metadata changes; it is not an authenticity proof or a guarantee against adversarial concurrent filesystem replacement.

CORE-02: hashing validates a positive non-bool integer chunk size before any path access and checks pre-start cancellation. Custom valid chunks retain exact-byte digests.

CORE-03: RF64 non-data sentinel chunks consume ds64 table entries sequentially using bounded 12-byte reads. Repeated chunk IDs retain their individual sizes and order. Missing/mismatched entries and resolved sizes outside the declared container are rejected. The previous 512 MiB native decoded-size cap and bounded metadata reads remain intact.

Verification: 50 focused tests passed across `test_core_audit`, `test_wav_limits`, `test_input_hardening`, `test_numeric_contracts`, `test_cancellation`, and `test_core`; `git diff --check` passed. Nine new core-audit tests cover invalid/custom hash chunks, real FIFO subprocess rejection, regular pipeline control, repeated RF64 table IDs, invalid/missing entries, bounded table reads, returned stat tokens, and same-byte file replacement during the final hash. Relevant regressions were observed failing before their fixes. Lead owns fresh integrated full-suite, native packaging, and GUI verification.
