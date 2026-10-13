# Research notes and source register

Updated: 2026-10-08. This is an initial, scoped research record for the beta slice, not the complete literature review required before a forensic-grade release. No location-identification claim is made from the present measurements.

## Findings that constrain the implementation

### Integrity and forensic workflow

SWGDE's digital audio authentication guidance treats evidence integrity, provenance, a defined examination plan, systematic and repeatable testing, documentation of procedures and decision criteria, and interpretation across applicable analyses as core practice. It cautions against relying on a single analysis and against conclusions expressed as absolute certainty. The application therefore stores a byte-level SHA-256 of the source separately from its derived acoustic fingerprint, never rewrites evidence, records the analysis version, and labels output as candidate or descriptive.

### Room decay measurements

ISO 3382-1 describes measurement procedures, equipment, coverage, data evaluation, and reporting of reverberation time and related room-acoustic parameters in performance spaces, including parameters derived from impulse responses. A normal evidentiary recording is not automatically a suitable impulse response. The beta's isolated Schroeder reverse-integrated decay-slope routine is experimental, only accepts an impulse-response-like signal, and is not represented as conforming to ISO 3382. A future acquisition wizard must specify source signal, microphone, geometry, calibration, background level, and repeatability before presenting standardized room parameters.

The foundational Schroeder integrated-impulse-response method and later work discuss noise and truncation effects in decay curves. The beta's simple -5 to -25 dB regression does not estimate or remove a background-noise tail, so its result is experimental and should not be used as a standardized measurement without protocol and validation.

### Environment signatures and comparison

Zhao and Malik's environment-signature work studies reverberation and background noise as separate environmental cues and identifies distortions and artifacts as confounders. This supports a modular, feature-visible comparison and the explicit separation of acoustic measurements from cryptographic evidence integrity. Published results on particular datasets do not validate this application's thresholds or generalize automatically to arbitrary microphones, rooms, codecs, noise suppression, or environments.

### Validation and statistical interpretation

NIST's 2025 validation guidance emphasizes collecting and using validation data to characterize methods and their limits. NIST's evidential-statistics work separately addresses calibration of likelihood-ratio systems and case-specific performance. The app therefore keeps the current score descriptive and uncalibrated; converting it into evidential weight would require relevant datasets, a defined proposition framework, calibration, and independent validation.

### Three distinct identifiers and interpretations

1. **Evidence SHA-256** covers the exact original bytes and can show whether a file's bytes later differ.
2. **Versioned acoustic fingerprint** is a canonicalized set of selected measured features for comparison; its hash identifies that exact feature record and algorithm version.
3. **Location conclusion** is a scientific interpretation requiring suitable reference samples, discrimination from alternatives, validation, and uncertainty analysis. The current beta does not make such a conclusion.

## Candidate methods and maturity

| Method | Beta status | Validation limit |
|---|---|---|
| File SHA-256 | Implemented | Unit tested against the standard library digest; does not establish provenance or chain of custody by itself. |
| Frame RMS / noise distribution | Implemented | Descriptive frame-amplitude statistics; p10 is not a measured noise floor. No speech/noise separation and not a calibrated sound-pressure level. |
| Spectral centroid, flatness, fixed-band power | Implemented | Synthetic tone regression tests; sensitive to source content, microphone response, codec, and processing. |
| Adjacent-frame transition candidates | Implemented | Synthetic step-change test; threshold is a heuristic, no forensic sensitivity/specificity study. |
| Fingerprint comparison | Implemented | Transparent feature differences; displayed score is uncalibrated and is not a likelihood ratio or probability. |
| Schroeder decay slope | Experimental isolated routine | Requires a suitable impulse response; synthetic regression test only; not an ISO 3382 workflow. |
| Acoustic recurrence within/across recordings | Deferred | Needs segmentation, calibrated matching, recurrence decision rules, and representative validation data. |
| Controlled known-location exemplars | Deferred | Requires a documented acquisition protocol, session metadata, repeat samples, and location governance. |
| ENF, scene classification, event recognition, spatial analysis, device confounders | Deferred | Each needs an independent research dossier, implementation, validation record, and result view. |

## Source register

1. SWGDE, **Best Practices for Digital Audio Authentication**, document 15-A-001. Primary practice guidance; scope and limitations must be read with the current revision. https://www.swgde.org/documents/published-complete-listing/15-a-001-swgde-best-practices-for-digital-audio-authentication/
2. SWGDE, **Best Practices for Forensic Audio** document collection. https://www.swgde.org/documents/published-by-committee/audio/
3. ISO 3382-1:2009, **Acoustics — Measurement of room acoustic parameters — Part 1: Performance spaces**. ISO identifies this edition as current after review/confirmation in 2021. https://www.iso.org/standard/40979.html
4. H. Zhao and H. Malik, “Audio Recording Location Identification Using Acoustic Environment Signature,” *IEEE Transactions on Information Forensics and Security*, 8(11), 1746–1759 (2013), DOI: 10.1109/TIFS.2013.2278843.
5. H. Zhao et al., “Audio Splicing Detection and Localization Using Environmental Signature,” arXiv:1411.7084 (2014). Preprint; not treated as independent validation of this software. https://arxiv.org/abs/1411.7084
6. ENFSI, **Best Practice Manual for Digital Audio Authenticity Analysis**, FSA-BPM-002, 2022 edition PDF. https://enfsi.eu/wp-content/uploads/2022/12/FSA-BPM-002_BPM-for-Digital-Audio-Authenticity-Analysis.pdf
7. NIST, **Validation in Forensic Science: Guiding Principles for the Collection and Use of Validation Data**, NIST IR 8589 (2025), DOI: 10.6028/NIST.IR.8589. https://doi.org/10.6028/NIST.IR.8589
8. M. R. Schroeder, “New Method of Measuring Reverberation Time,” *Journal of the Acoustical Society of America*, 37(3), 409–412 (1965), DOI: 10.1121/1.1909343. Follow-on research must address noise and impulse-response truncation before adopting a robust estimator.
9. H. Malik, “Acoustic Environment Identification and Its Applications to Audio Forensics,” *IEEE Transactions on Information Forensics and Security*, 8(11), 1827–1837 (2013), DOI: 10.1109/TIFS.2013.2280888.
10. User-supplied master directive additionally cites work on ENF and KL-divergence environment comparison. Their techniques require separate dossiers and are not implemented; source/version metadata and independent validation will be added before development.

## Research backlog

- Verify current official editions and document revision metadata for SWGDE and ENFSI guidance.
- Retrieve and review foundational papers, follow-on work, and independent replications for every technique before implementation.
- Build a source-to-claim ledger that records exact claims, limitations, datasets, and reproduction status.
- Acquire or construct lawful, documented benchmark data with same-room repeats, cross-room negatives, device variation, codec/processing confounders, transitions, and known edits.
- Set decision thresholds only from preregistered validation, report uncertainty, and version all material algorithm changes.

