# Testing

Methodology: spec-anchored development + acceptance-test-first + property-based testing.
Test-first is mandatory where there is a contract: a new detector, a bug fix, CLI-visible
behavior, an output schema, an edge case, a false-positive fix. Pure internal refactors rely on
the existing suite.

## Layers

| Directory | Purpose | Runs on |
| --------- | ------- | ------- |
| `tests/unit/` | one detector or function; per invariant: positive, negative, boundary, insufficient-evidence | every PR |
| `tests/integration/` | parser -> normalizer -> engine on small traces | every PR |
| `tests/acceptance/` | real CLI: exit code, stdout, stderr, JSON, no traceback, deterministic order | every PR |
| `tests/property/` | Hypothesis generators and mutation operators | PR bounded, nightly extended |
| `tests/fixtures/regressions/` | one oracle per fixed bug | every PR |
| `tests/golden/` | renderer snapshots only (terminal, JSON, JUnit). JSON validated by schema first | every PR |

Each detector test references its invariant ID (`INV-CURSOR-001`) in the test name or docstring
so `spec -> detector -> tests` can be grepped.

## Property-based testing (the main correctness layer)

`tests/property/strategies.py` provides:

- `valid_trace()`: a pagination sequence that is correct by construction. Main property: for every
  generated valid trace, no PROVEN finding is emitted. This attacks false positives directly.
- Mutation operators that break exactly one property: `freeze_cursor`, `insert_cursor_cycle(n)`,
  `duplicate_item`, `skip_page`, `change_next_cursor`, `drop_last_page`,
  `set_has_more_true_on_final_page`, `duplicate_response`, `corrupt_total`. After each mutation:
  the expected detector fires, evidence points at the right pages, unrelated detectors stay silent.
- Cursor cycles of length 1, 2, 3, N; starting at page 0, halfway, and after a long prefix.
- Traces of up to 60 pages are generated per example, never stored as fixtures. Cost at thousands of pages is a benchmark question, not a property one: see docs/performance.md.

Profiles live in `tests/conftest.py`: `pr` (200 examples, derandomized) and `nightly`
(5000 examples, random seeds). Select with `HYPOTHESIS_PROFILE=nightly`.

## Mutation testing

`uv run mutmut run` over `src/pagetrace/` minus the renderers and the argparse wiring, against
the unit tests only: a mutant has to be killed hundreds of times over, and the property suite
costs seconds per run.

mutmut refuses to run on Windows and says so. The nightly job is on ubuntu and calls it
directly. On a Windows machine it needs a Linux container:

```
docker run --rm -v "$PWD":/src:ro python:3.13-slim bash -c '
  pip install -q uv &&
  mkdir /work && cd /src &&
  tar cf - --exclude=./.venv --exclude=./.git . | (cd /work && tar xf -) &&
  cd /work && uv sync --frozen && uv run mutmut run && uv run mutmut results'
```

### Baseline, 2026-09-12

1722 mutants, 1342 killed, 380 survived: **77.9%**. The run takes about six minutes at
46 mutations/second.

The survivors are not 380 holes. Sorted by hand:

| Kind | Count | Verdict |
| ---- | ----: | ------- |
| A string literal inside a finding's `message` | 69 | Expected. Messages are asserted nowhere on purpose: they carry no trace values, and pinning their wording in unit tests would make every copy edit a test edit. The golden snapshots hold the wording instead. |
| A `Finding` field set to `None` (`severity`, `invariant`, `code`) | 77 | An artifact of running against `tests/unit/` only. The golden and JSON-schema tests assert these fields; they are simply not in the selection. |
| `continue` swapped for `break` in a detector loop | 19 | **Real.** No test has two unobservable transitions with a checkable one behind them, so skipping and stopping are indistinguishable. |
| Arithmetic and comparison flips | 27 | **Mostly real.** The insufficient-evidence counters are never asserted with a number, only with a code. |
| Everything else (`normalize`, `inputs`, `selectors` internals) | 188 | Mixed. The Link-header splitters carry most of them: the parser is table-driven on characters, and the tests exercise realistic headers rather than the character classes. |

Policy from here: no regression from 77.9%, then core score >= 85% with equivalent mutants
excluded by hand. Not a PR gate, and `continue-on-error` in CI.

## Fuzzing the parser boundary

Hypothesis-generated malformed input: truncated JSON, invalid UTF-8, deep nesting, huge scalars,
wrong field types, arrays instead of objects, bad base64. Every case must produce exit 2 with a
message and no traceback. Atheris is deferred until parsers become a real attack surface.

## Differential testing

When a faster path replaces a simple one, both must agree on generated input, not on the handful
of shapes a person would think to write down. `tests/property/test_selector_fast_path.py` is the
live example: the single-name selector shortcut is compared against the compiled RFC 9535 query
on generated documents. An optimization may be faster; it may not be different.

## Coverage

Branch coverage, `fail_under = 90` overall, target >= 95% for `checks/`. Coverage is a floor,
not a goal; mutation score answers the real question.

## Commands

```
uv run pytest                                   # PR profile
HYPOTHESIS_PROFILE=nightly uv run pytest -m "" # extended
uv run pytest --cov --cov-branch                # coverage
uv run mutmut run                               # mutation
```
