"""JUnit output for CI, and the spec-consistency check that keeps the two in step."""

from __future__ import annotations

import re
from pathlib import Path
from xml.etree.ElementTree import Element, fromstring

import pytest
from tests.factories import page, trace

from pagetrace.checks import INVARIANT_IDS
from pagetrace.model import Certainty, Evidence, Finding, Severity
from pagetrace.render.junit import render_junit

SPEC = Path("specs/invariants.md")
CHECKS_DIR = Path("src/pagetrace/checks")


def finding(
    certainty: Certainty,
    invariant: str = "INV-CURSOR-001",
    code: str = "CURSOR_CONTINUATION_MISMATCH",
) -> Finding:
    return Finding(
        code=code,
        invariant=invariant,
        certainty=certainty,
        severity=Severity.ERROR,
        message="Something observable happened.",
        affected_pages=(0, 1),
        evidence=(Evidence("page[0].response.next_cursor", "abc"),),
    )


def parse(xml: str) -> Element:
    return fromstring(xml)


def case(root: Element, invariant: str) -> Element:
    found = root.find(f"./testcase[@name='{invariant}']")
    assert found is not None
    return found


def test_every_invariant_gets_a_testcase() -> None:
    root = parse(render_junit(trace(page(0)), []))
    names = [element.get("name") for element in root.findall("./testcase")]

    assert names == list(INVARIANT_IDS)
    assert root.get("failures") == "0"


def test_a_proven_finding_fails_the_case() -> None:
    root = parse(render_junit(trace(page(0)), [finding(Certainty.PROVEN)]))
    failure = case(root, "INV-CURSOR-001").find("failure")

    assert failure is not None
    assert failure.get("type") == "CURSOR_CONTINUATION_MISMATCH"
    assert root.get("failures") == "1"
    assert failure.text is not None
    assert "page[0].response.next_cursor" in failure.text


def test_a_suspicion_does_not_fail_the_build() -> None:
    """A build that goes red on "this might be a cache" teaches people to ignore the tool."""
    root = parse(render_junit(trace(page(0)), [finding(Certainty.SUSPICIOUS)]))
    element = case(root, "INV-CURSOR-001")

    assert element.find("failure") is None
    assert element.find("system-out") is not None
    assert root.get("failures") == "0"


def test_insufficient_evidence_is_a_skip() -> None:
    root = parse(render_junit(trace(page(0)), [finding(Certainty.INSUFFICIENT_EVIDENCE)]))
    element = case(root, "INV-CURSOR-001")

    assert element.find("skipped") is not None
    assert root.get("skipped") == "1"


def test_a_suspicion_beats_a_skip_on_the_same_invariant() -> None:
    findings = [finding(Certainty.SUSPICIOUS), finding(Certainty.INSUFFICIENT_EVIDENCE)]
    element = case(parse(render_junit(trace(page(0)), findings)), "INV-CURSOR-001")

    assert element.find("skipped") is None
    assert element.find("system-out") is not None


def test_several_findings_on_one_invariant_are_summarized() -> None:
    findings = [finding(Certainty.PROVEN), finding(Certainty.PROVEN)]
    failure = case(parse(render_junit(trace(page(0)), findings)), "INV-CURSOR-001").find("failure")

    assert failure is not None
    message = failure.get("message")
    assert message is not None
    assert "and 1 more" in message


def test_output_is_deterministic_and_carries_no_timestamp() -> None:
    first = render_junit(trace(page(0)), [finding(Certainty.PROVEN)])
    second = render_junit(trace(page(0)), [finding(Certainty.PROVEN)])

    assert first == second
    assert "timestamp" not in first
    assert "hostname" not in first


def test_control_characters_in_evidence_are_escaped() -> None:
    dangerous = Finding(
        code="X",
        invariant="INV-CURSOR-001",
        certainty=Certainty.PROVEN,
        severity=Severity.ERROR,
        message="m",
        affected_pages=(0,),
        evidence=(Evidence("page[0].request.cursor", "a\x1b[31mb"),),
    )
    xml = render_junit(trace(page(0)), [dangerous])

    assert "\\x1b" in xml
    assert "\x1b" not in xml


# ---------------------------------------------------------------- spec consistency


def active_invariants_in_spec() -> list[str]:
    """IDs of the entries in specs/invariants.md whose status is Active."""
    text = SPEC.read_text(encoding="utf-8")
    entries = re.findall(r"^### (INV-[A-Z]+-\d{3}).*?\nStatus: (\w+)", text, re.MULTILINE)
    return [identifier for identifier, status in entries if status == "Active"]


def declared_finding_codes() -> set[str]:
    text = SPEC.read_text(encoding="utf-8")
    return set(re.findall(r"^Finding code: ([A-Z][A-Z0-9_]+)$", text, re.MULTILINE))


def emitted_literals(pattern: str) -> set[str]:
    found: set[str] = set()
    for source in CHECKS_DIR.glob("*.py"):
        found.update(re.findall(pattern, source.read_text(encoding="utf-8")))
    return found


def test_the_registry_matches_the_specification() -> None:
    """Spec drift is caught here rather than by a reader noticing months later."""
    assert sorted(INVARIANT_IDS) == sorted(active_invariants_in_spec())


def test_every_invariant_a_detector_names_is_registered() -> None:
    assert emitted_literals(r'invariant="(INV-[A-Z]+-\d{3})"') <= set(INVARIANT_IDS)


def test_every_finding_code_in_the_spec_is_emitted_by_a_detector() -> None:
    """A code in the contract that no code path can produce is a promise nobody keeps."""
    assert declared_finding_codes() <= emitted_literals(r'code="([A-Z][A-Z0-9_]+)"')


@pytest.mark.parametrize("invariant", INVARIANT_IDS)
def test_each_invariant_has_non_claim_conditions(invariant: str) -> None:
    """The rule that makes PageTrace worth using is written down for every detector."""
    text = SPEC.read_text(encoding="utf-8")
    entry = text.split(f"### {invariant} ")[1].split("\n### ")[0]

    assert "Non-claim conditions:" in entry
    assert "Preconditions" in entry
    assert len(entry.split("Non-claim conditions:")[1].strip()) > 40
