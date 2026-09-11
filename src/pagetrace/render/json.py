"""Machine-readable report.

The shape is a public contract: `specs/formats/report-json-v1.schema.json`. Adding a field is a
minor change, removing or renaming one is breaking (docs/compatibility.md).
"""

from __future__ import annotations

import json
from typing import Any

from pagetrace import __version__
from pagetrace.model import Certainty, Finding, Trace, exit_code_for
from pagetrace.render import display

SCHEMA_VERSION = 1


def build_report(trace: Trace, findings: list[Finding]) -> dict[str, Any]:
    """The report as plain data, so tests can assert on it without parsing text."""
    counts = dict.fromkeys(Certainty, 0)
    for finding in findings:
        counts[finding.certainty] += 1

    return {
        "schema_version": SCHEMA_VERSION,
        "tool": {"name": "pagetrace", "version": __version__},
        "input": {
            "format": trace.source_format,
            "preset": trace.preset,
            "page_count": trace.page_count,
        },
        "summary": {
            "proven": counts[Certainty.PROVEN],
            "suspicious": counts[Certainty.SUSPICIOUS],
            "insufficient_evidence": counts[Certainty.INSUFFICIENT_EVIDENCE],
            "exit_code": exit_code_for(findings),
        },
        "findings": [_finding(finding) for finding in findings],
    }


def _finding(finding: Finding) -> dict[str, Any]:
    return {
        "code": finding.code,
        "invariant": finding.invariant,
        "certainty": finding.certainty.value,
        "severity": finding.severity.value,
        "message": finding.message,
        "affected_pages": list(finding.affected_pages),
        "evidence": [_evidence(item.path, item.value) for item in finding.evidence],
    }


def _evidence(path: str, value: object) -> dict[str, Any]:
    shown = display(value)  # pyright: ignore[reportArgumentType]
    entry: dict[str, Any] = {"path": path, "value": shown.value}
    if shown.truncated:
        entry["truncated"] = True
        entry["length"] = shown.length
    return entry


def render_json(trace: Trace, findings: list[Finding]) -> str:
    """Stable text: fixed key order, two-space indent, one trailing newline, no timestamps."""
    return json.dumps(build_report(trace, findings), indent=2, ensure_ascii=False) + "\n"
