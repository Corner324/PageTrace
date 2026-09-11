"""The domain model: observations, pages, traces, findings.

Every object here is frozen. Detectors receive only these types, which is why a detector cannot
read an Authorization header even by accident: the model has no field for one.

Vocabulary and the three-valued observation rule are specified in `specs/invariants.md`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

Scalar = str | int | float | bool | None
"""A JSON scalar. `None` means JSON null, which is an observed value, not an absence."""


class Certainty(Enum):
    """What the evidence supports. Never a probability."""

    PROVEN = "PROVEN"
    SUSPICIOUS = "SUSPICIOUS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class Severity(Enum):
    """How much it matters if true. Independent of certainty."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ObservationStatus(Enum):
    """Why a selector did or did not yield a usable value."""

    OBSERVED = "observed"
    NOT_CONFIGURED = "not_configured"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    NOT_SCALAR = "not_scalar"


def canonical_text(value: Scalar) -> str:
    """Canonical text form used for every scalar comparison.

    Global precondition 3 of specs/invariants.md: a query parameter can only carry text, so
    integer 5 and string "5" are the same observation and must never be reported as a mismatch.
    `bool` is checked before `int` because `True` is an `int` in Python.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


@dataclass(frozen=True, slots=True)
class Observation:
    """The result of applying one selector to one request, response, or item."""

    path: str
    status: ObservationStatus
    value: Scalar = None

    @classmethod
    def of(cls, path: str, value: Scalar) -> Observation:
        return cls(path=path, status=ObservationStatus.OBSERVED, value=value)

    @classmethod
    def missing(cls, path: str, status: ObservationStatus) -> Observation:
        if status is ObservationStatus.OBSERVED:  # pragma: no cover - programming error
            raise ValueError("use Observation.of for an observed value")
        return cls(path=path, status=status, value=None)

    @property
    def observed(self) -> bool:
        return self.status is ObservationStatus.OBSERVED

    @property
    def is_null(self) -> bool:
        """Observed, and the observed value is JSON null."""
        return self.observed and self.value is None

    @property
    def is_empty(self) -> bool:
        """Observed, and the value is null or the empty string. Both mean "no continuation"."""
        return self.observed and (self.value is None or self.value == "")

    @property
    def text(self) -> str | None:
        """Canonical text of an observed non-null value, else None."""
        if not self.observed or self.value is None:
            return None
        return canonical_text(self.value)

    @property
    def int_value(self) -> int | None:
        """The observed value as an integer, or None when it is not one.

        A query parameter arrives as text, so "3" is an integer observation and 3 is the same
        observation. `True` is not, even though Python says `isinstance(True, int)`, and neither
        is "3.0": inventing a rounding rule for someone else's page number is a claim.

        Only ASCII digits count. `str.isdigit()` is true for characters `int()` refuses, such as
        the superscript two, and a page number of "\u00b2" must be an observation PageTrace
        cannot use, not a crash on trace content.
        """
        if not self.observed or isinstance(self.value, bool):
            return None
        if isinstance(self.value, int):
            return self.value
        if isinstance(self.value, str):
            text = self.value.strip()
            body = text[1:] if text[:1] in {"-", "+"} else text
            if body.isascii() and body.isdigit():
                return int(text)
        return None

    def same_as(self, other: Observation) -> bool:
        """True when both are observed non-null values with the same canonical text."""
        mine, theirs = self.text, other.text
        return mine is not None and mine == theirs


@dataclass(frozen=True, slots=True)
class ItemIdentity:
    """One item whose id selector resolved to a scalar."""

    page_index: int
    item_index: int
    value: Scalar

    @property
    def text(self) -> str:
        return canonical_text(self.value)

    @property
    def path(self) -> str:
        return f"page[{self.page_index}].items[{self.item_index}].id"


@dataclass(frozen=True, slots=True)
class ItemsObservation:
    """The items array of one response, plus how much of it could be identified."""

    status: ObservationStatus
    count: int | None = None
    identities: tuple[ItemIdentity, ...] = ()
    unidentified: int = 0

    @classmethod
    def missing(cls, status: ObservationStatus) -> ItemsObservation:
        return cls(status=status)

    @property
    def observed(self) -> bool:
        return self.status is ObservationStatus.OBSERVED

    @property
    def fully_identified(self) -> bool:
        return self.observed and self.unidentified == 0


@dataclass(frozen=True, slots=True)
class RawObservation:
    """One request/response pair as read from a trace file, before any selector runs.

    This is the only object that ever holds a response body, and parsers build it with a header
    allowlist already applied. Detectors never see it: `Trace` and `Page` do not reference it.
    """

    index: int
    method: str
    url: str
    query: dict[str, str | list[str]]
    status: int
    headers: dict[str, str]
    body: object = None
    body_present: bool = False

    @property
    def request_context(self) -> dict[str, object]:
        """What a request-side selector is evaluated against."""
        return {"method": self.method, "url": self.url, "query": self.query}


@dataclass(frozen=True, slots=True)
class Page:
    """One request/response pair, normalized. The unit every detector reasons about."""

    index: int
    url: str
    status: int | None = None
    request_cursor: Observation = Observation("request.cursor", ObservationStatus.NOT_CONFIGURED)
    next_cursor: Observation = Observation("response.next_cursor", ObservationStatus.NOT_CONFIGURED)
    page_number: Observation = Observation("request.page", ObservationStatus.NOT_CONFIGURED)
    offset: Observation = Observation("request.offset", ObservationStatus.NOT_CONFIGURED)
    total: Observation = Observation("response.total", ObservationStatus.NOT_CONFIGURED)
    has_more: Observation = Observation("response.has_more", ObservationStatus.NOT_CONFIGURED)
    items: ItemsObservation = ItemsObservation(ObservationStatus.NOT_CONFIGURED)
    fingerprint: str | None = None
    body_present: bool = False

    @property
    def ok(self) -> bool:
        """2xx. Non-2xx bodies are error envelopes and are excluded from body-derived checks."""
        return self.status is not None and 200 <= self.status < 300

    def evidence(self, observation: Observation) -> Evidence:
        """Evidence for one of this page's observations, with the page-qualified path."""
        return Evidence(path=f"page[{self.index}].{observation.path}", value=observation.value)

    @property
    def item_count_evidence(self) -> Evidence:
        """How many items this page returned, as evidence. None when that is not observable."""
        return Evidence(path=f"page[{self.index}].response.items.count", value=self.items.count)


@dataclass(frozen=True, slots=True)
class Trace:
    """A whole recorded pagination run, as PageTrace sees it."""

    pages: tuple[Page, ...]
    preset: str
    source_format: str

    @property
    def page_count(self) -> int:
        return len(self.pages)


@dataclass(frozen=True, slots=True)
class Evidence:
    """One observed fact. Never a conclusion."""

    path: str
    value: Scalar


@dataclass(frozen=True, slots=True)
class Finding:
    """One statement about the trace, with the observations that support it."""

    code: str
    invariant: str
    certainty: Certainty
    severity: Severity
    message: str
    affected_pages: tuple[int, ...] = ()
    evidence: tuple[Evidence, ...] = ()

    @property
    def sort_key(self) -> tuple[int, int, str, str]:
        """Deterministic report order: strongest claims first, then by page, then by ID."""
        certainty_rank = {
            Certainty.PROVEN: 0,
            Certainty.SUSPICIOUS: 1,
            Certainty.INSUFFICIENT_EVIDENCE: 2,
        }[self.certainty]
        first_page = self.affected_pages[0] if self.affected_pages else 1 << 30
        return (certainty_rank, first_page, self.invariant, self.code)


def sort_findings(findings: list[Finding]) -> list[Finding]:
    """Total order over findings. The same trace always renders in the same order."""
    return sorted(findings, key=lambda f: f.sort_key)


def exit_code_for(findings: list[Finding]) -> int:
    """0 unless a violation is both proven and severe (specs/product.md).

    Certainty alone is not enough. A duplicate item across pages is a PROVEN observation whose
    interpretation the finding itself declines to make, and failing a build on it would be the
    tool claiming what its own message refuses to. Severity is what says "this is a defect if
    true", so exit 1 needs both.
    """
    return (
        1
        if any(
            finding.certainty is Certainty.PROVEN and finding.severity is Severity.ERROR
            for finding in findings
        )
        else 0
    )
