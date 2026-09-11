"""JUnit XML for CI. Contract: specs/formats/junit.md.

One testcase per invariant, so a CI run shows what was checked and not only what went wrong.
Proven violations fail. Suspicions do not: a build that goes red on "this might be a cache"
teaches people to ignore the tool.
"""

from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement, tostring

from pagetrace.checks import INVARIANT_IDS
from pagetrace.model import Certainty, Finding, Severity, Trace
from pagetrace.render import display


def render_junit(trace: Trace, findings: list[Finding]) -> str:
    """Deterministic XML: fixed order, no timestamps, no host names."""
    by_invariant: dict[str, list[Finding]] = {invariant: [] for invariant in INVARIANT_IDS}
    for finding in findings:
        by_invariant.setdefault(finding.invariant, []).append(finding)

    suite = Element("testsuite", name="pagetrace")
    failures = 0
    skipped = 0

    for invariant, found in by_invariant.items():
        proven = [f for f in found if f.certainty is Certainty.PROVEN]
        unproven = [f for f in found if f.certainty is Certainty.SUSPICIOUS]
        missing = [f for f in found if f.certainty is Certainty.INSUFFICIENT_EVIDENCE]

        case = SubElement(
            suite,
            "testcase",
            classname=f"pagetrace.{trace.preset}",
            name=invariant,
        )
        severe = [f for f in proven if f.severity is Severity.ERROR]
        if severe:
            failures += 1
            failure = SubElement(
                case,
                "failure",
                message=_summary(severe),
                type=severe[0].code,
            )
            failure.text = _detail(severe)
        elif missing and not unproven and not proven:
            skipped += 1
            SubElement(case, "skipped", message=_summary(missing))

        noted = unproven + [f for f in proven if f.severity is not Severity.ERROR]
        if noted:
            note = SubElement(case, "system-out")
            note.text = _detail(noted)

    suite.set("tests", str(len(by_invariant)))
    suite.set("failures", str(failures))
    suite.set("skipped", str(skipped))
    suite.set("errors", "0")

    return '<?xml version="1.0" encoding="utf-8"?>\n' + tostring(suite, encoding="unicode") + "\n"


def _summary(findings: list[Finding]) -> str:
    first = findings[0]
    if len(findings) == 1:
        return f"{first.code}: {first.message}"
    return f"{first.code} and {len(findings) - 1} more: {first.message}"


def _detail(findings: list[Finding]) -> str:
    lines: list[str] = []
    for finding in findings:
        pages = ", ".join(str(index) for index in finding.affected_pages)
        lines.append(f"{finding.certainty.value} {finding.code} pages [{pages}]")
        lines.append(f"  {finding.message}")
        lines.extend(f"  {item.path} = {display(item.value).text}" for item in finding.evidence)
    return "\n".join(lines)
