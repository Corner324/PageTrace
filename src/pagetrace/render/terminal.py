"""Human-readable report. Deterministic: no colour, no timestamps, fixed order."""

from __future__ import annotations

from pagetrace.model import Certainty, Finding, Trace, escape_control
from pagetrace.render import display

# A systematic misconfiguration can mismatch every transition. The JSON report keeps all of
# them; a terminal that scrolls for a thousand screens helps nobody.
MAX_SHOWN_PER_CODE = 10


def render_terminal(trace: Trace, findings: list[Finding], source: str) -> str:
    # The trace filename is not an observation, so it never passed through display(); it is
    # still user-supplied text on its way to a terminal.
    header = f"{escape_control(source)}: {trace.page_count} pages, preset {trace.preset}"
    lines = [header, ""]

    if not findings:
        lines.append("No findings. Nothing observable in this trace violates an invariant.")
        lines.append("")
        lines.append(_summary(findings))
        return "\n".join(lines) + "\n"

    shown: dict[str, int] = {}
    hidden: dict[str, int] = {}
    for finding in findings:
        seen = shown.get(finding.code, 0)
        if seen >= MAX_SHOWN_PER_CODE:
            hidden[finding.code] = hidden.get(finding.code, 0) + 1
            continue
        shown[finding.code] = seen + 1
        lines.extend(_finding_lines(finding))
        lines.append("")

    for code, count in sorted(hidden.items()):
        lines.append(f"... and {count} more {code} findings, see the JSON report")
        lines.append("")

    lines.append(_summary(findings))
    return "\n".join(lines) + "\n"


def _finding_lines(finding: Finding) -> list[str]:
    pages = _pages(finding)
    header = f"{finding.certainty.value} {finding.severity.value} {finding.code}"
    lines = [f"{header} [{finding.invariant}]{pages}", f"  {finding.message}"]
    lines.extend(f"  {item.path} = {display(item.value).text}" for item in finding.evidence)
    return lines


def _pages(finding: Finding) -> str:
    if not finding.affected_pages:
        return ""
    if len(finding.affected_pages) == 1:
        return f" page {finding.affected_pages[0]}"
    listed = ", ".join(str(index) for index in finding.affected_pages)
    return f" pages {listed}"


def _summary(findings: list[Finding]) -> str:
    counts = dict.fromkeys(Certainty, 0)
    for finding in findings:
        counts[finding.certainty] += 1
    return (
        f"{counts[Certainty.PROVEN]} proven, "
        f"{counts[Certainty.SUSPICIOUS]} suspicious, "
        f"{counts[Certainty.INSUFFICIENT_EVIDENCE]} insufficient evidence"
    )
