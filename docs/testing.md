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
- Large traces (thousands of pages) are generated, never stored as fixtures.

Profiles live in `tests/conftest.py`: `pr` (200 examples, derandomized) and `nightly`
(5000 examples, random seeds). Select with `HYPOTHESIS_PROFILE=nightly`.

## Mutation testing

`uv run mutmut run` over `checks/`, `normalize.py`, `model.py`, against the unit tests only: a
mutant has to be killed hundreds of times over, and the property suite costs seconds per run.

**mutmut does not run on Windows** (it says so and exits). The nightly job on Linux is therefore
the only place mutation numbers come from, and the maintainer cannot reproduce them locally on a
Windows machine. That is a known gap, not a claim that the numbers were checked by hand.

Policy: establish a baseline first, then "no regression from baseline", then core score >= 85%
with equivalent mutants excluded by hand. Not a PR gate, and `continue-on-error` until the
baseline exists.

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
