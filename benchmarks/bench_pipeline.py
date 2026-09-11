"""Time normalize plus checks over the generated corpus.

Memory is reported as peak Python allocation from `tracemalloc`, not resident set size: that
needs no dependency and is the number a change to PageTrace can actually move. Budgets live in
`docs/performance.md`; this script only measures and compares.

    uv run python -m benchmarks.bench_pipeline --smoke
    uv run python -m benchmarks.bench_pipeline --json benchmark-results/latest.json
"""

from __future__ import annotations

import argparse
import json
import time
import tracemalloc
from dataclasses import asdict, dataclass
from pathlib import Path

from benchmarks.generate import FULL, SMOKE, Shape, observations
from pagetrace.checks import run_checks
from pagetrace.normalize import SelectorSet, build_trace

# A gross-regression tripwire, not a budget. It sits roughly three times above what the corpus
# actually costs today (docs/performance.md), so it fires on a quadratic mistake and stays quiet
# on the noise of a shared CI runner. Real budgets are in docs/performance.md.
FIXED_SECONDS = 3.0
SECONDS_PER_PAGE = 0.002
SECONDS_PER_ITEM = 0.00006


def tripwire(shape: Shape) -> float:
    items = shape.pages * shape.items_per_page
    return FIXED_SECONDS + shape.pages * SECONDS_PER_PAGE + items * SECONDS_PER_ITEM


@dataclass(frozen=True, slots=True)
class Measurement:
    shape: str
    pages: int
    items: int
    seconds: float
    peak_mib: float
    findings: int


def measure(shape: Shape) -> Measurement:
    selectors = SelectorSet.build("cursor", {})
    raws = list(observations(shape))

    tracemalloc.start()
    started = time.perf_counter()
    trace = build_trace(raws, selectors, "cursor", "jsonl")
    findings = run_checks(trace)
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return Measurement(
        shape=shape.label,
        pages=shape.pages,
        items=shape.pages * shape.items_per_page,
        seconds=round(elapsed, 3),
        peak_mib=round(peak / 1024 / 1024, 1),
        findings=len(findings),
    )


def run(shapes: tuple[Shape, ...], *, enforce: bool) -> list[Measurement]:
    results: list[Measurement] = []
    failures: list[str] = []

    for shape in shapes:
        measurement = measure(shape)
        results.append(measurement)
        print(
            f"{measurement.seconds:7.3f}s {measurement.peak_mib:8.1f} MiB "
            f"{measurement.findings:4d} findings  {measurement.shape}"
        )
        ceiling = tripwire(shape)
        if enforce and measurement.seconds > ceiling:
            failures.append(
                f"{shape.label}: {measurement.seconds}s over the {ceiling:.1f}s tripwire"
            )

    for failure in failures:
        print(f"REGRESSION {failure}")
    if failures:
        raise SystemExit(1)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="the small corpus, for every PR")
    parser.add_argument("--json", type=Path, default=None, help="write measurements here")
    args = parser.parse_args()

    results = run(SMOKE if args.smoke else FULL, enforce=True)

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps([asdict(result) for result in results], indent=2), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
