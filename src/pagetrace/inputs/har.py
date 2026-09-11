"""HAR reader. Added at step 19 of the development sequence."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pagetrace.errors import PageTraceError
from pagetrace.model import RawObservation


def read_har(path: Path) -> Iterator[RawObservation]:
    raise PageTraceError(f"{path.name}: HAR input is not implemented yet")
    yield  # pragma: no cover - unreachable, keeps this a generator
