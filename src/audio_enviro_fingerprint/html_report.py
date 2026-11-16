"""Static, printable view of a manifest-bearing JSON report; no external assets."""
from __future__ import annotations

import hashlib
from html import escape
import json
from pathlib import Path

from .control import check_cancelled
from .integrity import sha256_file, write_export
from .report import SCHEMA, _canonical


def _text(value) -> str:
    return escape(str(value), quote=True)


def _label(value) -> str:
    return _text(str(value).replace('_', ' ').capitalize())


def _value(value) -> str:
    """Render JSON values as nested tables without interpreting any markup."""
    if isinstance(value, dict):
        if not value:
            return '<span class="muted">None recorded</span>'
        rows = ''.join(f'<tr><th scope="row">{_label(k)}</th><td>{_value(v)}</td></tr>'
                       for k, v in value.items())
        return f'<table><tbody>{rows}</tbody></table>'
    if isinstance(value, list):
        if not value:
            return '<span class="muted">None recorded</span>'
        if all(isinstance(item, dict) for item in value):
            columns = list(dict.fromkeys(k for item in value for k in item))
            head = ''.join(f'<th scope="col">{_label(k)}</th>' for k in columns)
            rows = ''.join('<tr>' + ''.join(f'<td>{_value(item.get(k))}</td>' for k in columns) + '</tr>'
                           for item in value)
            return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>'
        return '<ul>' + ''.join(f'<li>{_value(item)}</li>' for item in value) + '</ul>'
    if value is None:
        return '<span class="muted">Unavailable / not run</span>'
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if isinstance(value, float):
        return _text(f'{value:.6g}')
    return _text(value)


def render_html_report(report: dict) -> str:
    """Render a valid report as escaped HTML, retaining its complete JSON record.

    HTML is a readable view, not a signed or independently verifiable document.
    The original JSON record remains the input to the CLI verification command.
    """
    if not isinstance(report, dict) or report.get('schema_version') != SCHEMA:
        raise ValueError('Unsupported or malformed report schema')
    evidence, sections, manifest = (report.get(k) for k in ('evidence', 'sections', 'manifest'))
    if not all(isinstance(value, dict) for value in (evidence, sections, manifest)):
        raise ValueError('Report requires evidence, sections and manifest objects')
    body = {key: value for key, value in report.items() if key != 'manifest'}
    digest = hashlib.sha256(_canonical(body)).hexdigest()
    if manifest.get('algorithm') != 'sha256-canonical-json' or manifest.get('body_sha256') != digest:
        raise ValueError('Report manifest does not match its contents')
    audio = sections.get('audio', {})
    analysis = sections.get('analysis', {})
    if not isinstance(audio, dict) or not isinstance(analysis, dict):
        raise ValueError('Report audio and analysis sections must be objects')
    frames = analysis.get('frames', [])
    if not isinstance(frames, list):
        raise ValueError('Report frame measurements must be a list')
    summary = ''.join(f'<div><span>{label}</span><strong>{_text(audio.get(key, "Unavailable"))}</strong></div>'
                      for key, label in (('duration_seconds', 'Duration (seconds)'),
                                         ('sample_rate', 'Sample rate (Hz)'), ('channels', 'Channels')))
    overview = {key: value for key, value in sections.items() if key not in ('audio', 'analysis')}
    # Full frame records can be large. Keep them available without overwhelming
    # the annotation and candidate summary that an examiner usually needs first.
    analysis_summary = {key: value for key, value in analysis.items() if key != 'frames'}
    sections_html = ''.join(f'<section><h2>{_label(key)}</h2>{_value(value)}</section>'
                            for key, value in overview.items())
    limitations = '<ul>' + ''.join(f'<li>{_text(item)}</li>' for item in report.get('limitations', [])) + '</ul>'
    record = _text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Audio environment analysis report</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;color:#17202b;background:#f4f5f6;margin:0}}main{{max-width:1100px;margin:auto;padding:32px}}
h1{{font-size:28px;margin-bottom:8px}}h2{{font-size:20px;margin-top:0}}h3{{font-size:17px}}header,section,details{{background:white;padding:24px;margin-bottom:16px;border:1px solid #d9dee4;border-radius:6px}}
.summary{{display:flex;gap:32px;flex-wrap:wrap;margin:24px 0}}.summary span,.summary strong{{display:block}}.summary span,.muted{{color:#566272}}
.notice{{border-left:4px solid #ac6921;padding-left:16px}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{text-align:left;vertical-align:top;border-bottom:1px solid #e2e5e9;padding:8px;overflow-wrap:anywhere}}th{{font-weight:600}}td table{{font-size:13px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}}.scroll{{overflow-x:auto}}code{{overflow-wrap:anywhere}}summary{{cursor:pointer;font-weight:600}}
@media print{{body{{background:white}}main{{padding:0;max-width:none}}section,header,details{{border:0;padding:12px 0}}h2{{break-after:avoid}}tr{{break-inside:avoid}}.scroll{{overflow:visible}}}}
</style></head><body><main>
<header><p class="muted">Audio Environment Fingerprinter · {_text(report.get('application_version', ''))}</p>
<h1>Acoustic environment analysis</h1><p class="notice">Research screening aid. Results do not identify a physical location or establish authenticity.</p>
<div class="summary">{summary}</div><h2>Evidence</h2>
<p>Source: <code>{_text(evidence.get('source_path', ''))}</code></p>
<p>Evidence SHA-256: <code>{_text(evidence.get('sha256', ''))}</code></p>
<p>JSON body SHA-256: <code>{digest}</code></p>
<p class="muted">This HTML is a readable view. Use the original JSON report with the verify command to check its manifest and evidence. The manifest is not a digital signature.</p></header>
<section><h2>Limitations</h2>{limitations}</section>
<section><h2>Recording and decoder</h2>{_value(audio)}</section>
{sections_html}
<section><h2>Analysis settings and levels</h2>{_value(analysis_summary)}</section>
<details><summary>Frame measurements ({len(frames)})</summary>{_value(frames)}</details>
<details><summary>Complete JSON report record</summary><pre>{record}</pre></details>
</main></body></html>'''


def write_html_report(path: str | Path, report: dict, *, protected_paths=(), should_cancel=None) -> None:
    """Recheck evidence and atomically export HTML with the JSON export safeguards."""
    check_cancelled(should_cancel)
    payload = render_html_report(report).encode('utf-8')
    check_cancelled(should_cancel)
    source = report['evidence']['source_path']
    if sha256_file(source, should_cancel=should_cancel) != report['evidence']['sha256']:
        raise ValueError('Evidence changed since analysis; reopen a stable copy before export')
    check_cancelled(should_cancel)
    write_export(path, payload, source, protected_paths=protected_paths)
