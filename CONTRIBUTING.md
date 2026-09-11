# Contributing

## Setup

```
uv sync
uv run pytest
```

## Workflow

```
ISSUE (problem + scope)
  -> SPEC IMPACT (none / updated <path>; "none" for a behavior change needs a reason)
  -> INVARIANT ENTRY in specs/invariants.md for a new detector
  -> ACCEPTANCE CRITERIA
  -> VERIFICATION DESIGN: examples, counterexamples, properties, false-positive cases
  -> FAILING TEST / PROPERTY (where a contract exists)
  -> SMALLEST COHERENT IMPLEMENTATION
  -> LOCAL GATES: ruff, format, pyright, pytest, bounded PBT
  -> FRESH-CONTEXT REVIEW (findings only)
  -> ADVERSARIAL CRITIC for high-risk changes
  -> FIXES -> FULL CI -> SQUASH MERGE TO main
```

High-risk: invariant engine, evidence model, parser security, schema compatibility, release
mechanics, performance-sensitive algorithms.

## Pre-commit checklist (in order, stop at the first failure)

```
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -x
git diff --staged
```

## Definition of Done

- issue and scope stated;
- `Spec impact` filled; spec updated for behavior changes;
- acceptance criteria written;
- at least one negative or edge case;
- new invariant has an insufficient-evidence case;
- bug fix has a regression test in `tests/fixtures/regressions/` or `tests/unit/`;
- property test added, or a one-line reason why not applicable;
- no finding claims more than its evidence;
- output deterministic;
- ruff, format, pyright strict, pytest, bounded PBT, branch coverage, compatibility matrix,
  wheel/sdist build and installed-wheel smoke all green;
- new runtime dependency has an ADR;
- security/privacy impact considered;
- performance-sensitive change measured;
- review findings resolved;
- CHANGELOG updated when user-visible behavior changed.

Not part of Done: "the reviewer agent said LGTM".

## Commits and branches

`main` + short-lived branches, squash merge. Conventional commit subjects
(`feat:`, `fix:`, `spec:`, `docs:`, `test:`, `ci:`, `chore:`).
