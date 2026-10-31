# Branch reconciliation inventory — 2026-10-30

Baseline: `4343f34f509216dbecd4e1dd6c86542fe913d672` (`main`, local `work`). Remote inventory was first read through the GitHub connector because sandboxed shell Git could not connect to its proxy. The lead subsequently fetched all ten remote refs successfully through the permitted shell execution path. Exact historical tips are available locally for graph consolidation. No remote branches were deleted, rewritten or pushed.

## Complete remote inventory

| Branch | Tip SHA | Relationship to baseline | Disposition |
|---|---|---|---|
| `main` | `4343f34f509216dbecd4e1dd6c86542fe913d672` | baseline | Current integration foundation. |
| `claude/intelligent-darwin-gmqz81` | `5b8a216bdaf92393b91675f804b5ceda309dfe28` | ancestor, confirmed locally | Already integrated: musical/hum, multichannel, spectrogram, reference, markers, CLI/report and frame-return recurrence. |
| `codex/audio-environment-beta` | `ac5d95f5cf9ca52de0a11178213c08702a063c1d` | ancestor, confirmed locally | Already integrated: initial beta source and specifications. |
| `codex/cloud-release-20261022` | `1f30731a1f4d9b4a17d4fd54a46ef53b53d809e0` | ancestor, confirmed locally | Already integrated: release matrix and hardening. |
| `codex/completion-audit` | `ca2baa96055e9bcd35ea139eb27b69ac4f400ee8` | ancestor, confirmed locally | Already integrated: compatible fingerprints, synthetic benchmark, transparent catalog. |
| `claude/epic-johnson-gfxc8f` | `c082f636505e51727f18520a4b13a40251006ac3` | diverged, 3 ahead / 12 behind | Adapted append-only SQL guards to current evidence/acquisition/notes/markers schema; retain current frame recurrence and APIs. Historical chained-reference format is preserved in the branch history, not silently migrated. |
| `claude/magical-allen-bw1af4` | `6ff0f632208582d3ffed76ea4ec2290318593a53` | diverged, 7 ahead / 16 behind | Fingerprint, quality and benchmark ideas already ported. Current marker-edit UI reuses append-only revisions; durable legacy fingerprint/reference ranking and configurable-channel alternatives are superseded/deferred with history retained. |
| `claude/serene-tesla-9uy0dq` | `6e6c8f8fcedf501c83ef656c1e3c7d5909740ee3` | diverged, 3 ahead / 16 behind | Retain current recurrence algorithm. Adapted evidence-bound append-only recurrence-run persistence into the current CaseStore API, with finite JSON and report-history integration. |
| `docs/readme-and-wiki` | `1f249e210a860029ee0eca008137f46efafe8bcf` | diverged, 1 ahead / 11 behind | Consolidated navigation into updated wiki pages; the short historical page names remain as links to current pages. |
| `docs/wiki` | `cb758d2533884ebd3f6e624ce588e9d7fd0cc29a` | diverged, 2 ahead / 11 behind | Ported and updated user/developer pages to current formats, method versions, worker model, four-OS matrix and five usability additions. Automatic external wiki publication remains unperformed. |

The four ancestor checks used `git cat-file -t` and `git merge-base --is-ancestor`. Diverged relationships and ahead/behind counts used GitHub compare responses with the exact baseline and branch-tip SHAs above. Every remote head returned by the branches endpoint is listed.

## Deliberate conflict resolution

The three divergent implementation branches are alternative implementations from an older base, not clean additive feature branches. They replace public APIs and stores in ways incompatible with `SPECIFICATIONS_V2.md` and with the later integrity fixes. Applying their complete trees would lose strict finite input contracts, hardened report/export protection, the current codec provenance path and current musical/spectrogram UI. Their `recurrence-v1` identifiers also refer to incompatible algorithms and JSON shapes; silently treating those as one method would be incorrect.

| Legacy surface | Inspected implementation | Current decision / compatible path |
|---|---|---|
| Segment recurrence | Epic uses transition-segment fingerprints plus best earlier match; magical/serene use segment-pair matching. Current implementation matches fixed-scale frame vectors with departure checks and preserves raw feature deltas. | Retain the specified current frame-return algorithm. A future segment method needs a new identifier, separate validation and migration; do not overwrite `recurrence.py`. |
| Comparison / fingerprint | Epic and magical contain older comparison explanations and canonical fingerprint work. | Current `aefp-2` and `comparison-symmetric-v2`, catalog grouping and benchmark preserve the useful compatible work. Retain newer numerical validation. |
| Quality checks | Epic adds independent `methods/quality.py`; magical adds acquisition review. | DC-offset/dropout checks and strict UTC/height/repeat/clipping review are already present in the current reference flow. |
| Reference storage | Epic has `reference_exemplars` with immutable SQL triggers, metadata digest and a chained row digest. Current `reference_records` stores append-only metadata/review tied to evidence. | Installed SQL append-only update/delete/id-replace guards on the current tables, including existing databases without rebuilding rows. Chained hashes remain a separate schema/verification feature; no signed or complete chain-of-custody claim. Avoided parallel incompatible reference tables. |
| Evidence catalog / fingerprints | Magical adds stored fingerprints, evidence listing and reference ranking, with a different schema and positional decoder channel API. | Current catalog compares decoded files deterministically with full pair explanations; current reports carry fingerprints. Any durable reference ranking requires explicit stored-fingerprint/version contracts rather than replacing CaseStore. |
| Marker editing | Magical stores current markers plus a revision table and explicit reasons. Current store already implements append-only marker revisions/tombstones. | Reuse current marker revisions for UI editing; do not migrate to the conflicting table shape. |
| Saved recurrence runs | Serene binds parameters/findings to evidence; magical uses a case-global run table. | Added `save_recurrence_run(evidence_id, parameters, findings)` and `recurrence_runs_for(evidence_id)`. Records use current findings/parameters and are evidence-bound, finite and append-only, rather than legacy segment JSON. |
| Audio decoding | Magical adds soundfile-backed codecs and selected-channel argument. | Retain strict native RIFF/RF64 and optional restricted FFmpeg decoding with provenance and decoded-size limit. Do not confuse its positional `channel` with current positional `max_decoded_bytes`. |
| CLI and reports | Magical uses different commands, `bundle_report`, custom report manifest fields and selected-channel settings. | Keep current CLI command/exit codes and `aefp-report-2` body manifest. Add compatible usability flags instead of replacing existing commands or invalidating reports. |
| Packaging | Legacy branch workflows reflect earlier targets/options. | Keep current four-native-target matrix and non-clobbering publication behavior. |
| Wiki | Initial docs describe PCM only, two tabs, synchronous analysis, `aefp-1`, 15 tests, Windows/Linux only. | Updated and ported the wiki navigation/user/developer structure. Retained the three short historical page paths as consolidated navigation links. Did not ship the stale initial-beta claims or automatic publication workflow. |

## Consolidation acceptance

1. Preserve all ten branch-tip SHAs and the explicit dispositions above.
2. Carry forward compatible unique behavior with current API/schema contracts and regression checks.
3. Do not revive superseded recurrence/store/report implementations under existing method IDs.
4. Update wiki user/developer navigation and link it from the README; leave external wiki publication unperformed unless explicitly part of delivery.
5. Run the integrated suite and record imported/adapted/deferred status honestly. This inventory alone is not a Git ancestry merge and does not claim all unique legacy behavior has been ported.

## Evidence sources

- [All repository branches](https://api.github.com/repos/djshellshoxxx/audio-enviro-fingerprint/branches?per_page=100)
- [Epic comparison](https://github.com/djshellshoxxx/audio-enviro-fingerprint/compare/4343f34f509216dbecd4e1dd6c86542fe913d672...c082f636505e51727f18520a4b13a40251006ac3)
- [Magical comparison](https://github.com/djshellshoxxx/audio-enviro-fingerprint/compare/4343f34f509216dbecd4e1dd6c86542fe913d672...6ff0f632208582d3ffed76ea4ec2290318593a53)
- [Serene comparison](https://github.com/djshellshoxxx/audio-enviro-fingerprint/compare/4343f34f509216dbecd4e1dd6c86542fe913d672...6e6c8f8fcedf501c83ef656c1e3c7d5909740ee3)
- [Wiki documentation branch](https://github.com/djshellshoxxx/audio-enviro-fingerprint/tree/cb758d2533884ebd3f6e624ce588e9d7fd0cc29a/docs/wiki)

## Compatible-port verification

`tests/test_store_immutability.py` adds six regressions: worker-pinned registration without a UI-thread rehash; changed/missing source and malformed digest rejection; append-only update/delete/replacement guards; preexisting database row preservation; and finite, evidence-bound recurrence-run history. The initial new tests failed against missing APIs and mutable records. All six now pass, along with 18 existing core/case checks (`PYTHONPATH=src:tests python -m unittest test_store_immutability test_core test_case_integrity -q`: 24 PASS).

`CaseStore.register_verified_evidence(source_path, evidence_sha256, source_stat)` adapts current worker provenance rather than adding an incompatible legacy store. The token detects ordinary post-analysis file changes and is not an adversarial race guarantee. No source bytes are rewritten.

Graph consolidation is performed by the lead after integration, retaining reviewed superseded branch tips as ancestry without replacing current production files. Final ancestry checks and integrated verification belong in the main work-session/audit record.

Final review also reproduced SQLite `INSERT OR REPLACE` deleting a conflicting logical-key row when no explicit ID was supplied. The CaseStore connection now enables recursive triggers so those implicit deletions fire existing append-only guards. The new evidence/marker logical-key regression first failed and now passes, while repeated registration remains idempotent. These are application-connection safeguards; another database owner can disable PRAGMAs or drop triggers, so no tamper-resistance guarantee is implied.

## Integrated graph verification

All ten remote heads were fetched through normal Git after granting the shell its network access; the custom fetch-equivalent helper was stopped. Compatible ports were committed in `74a1e52`. Five explicit reconciliation merges (`6697170`, `ff0810a`, `bd326a0`, `9b6e7ff`, `da58adc`) preserve the divergent histories while retaining the deliberately reviewed current tree. These use the `ours` merge strategy only after the compatible ports and supersession decisions above; they do not claim every conflicting legacy behavior was implemented.

`git merge-base --is-ancestor <each origin ref> HEAD` passed for all ten fetched heads. The Git tree before and after the five reconciliation merges was identical. No remote branch was deleted or force-updated. Follow-up delivery fixes and records remain descendants of this consolidated graph.
