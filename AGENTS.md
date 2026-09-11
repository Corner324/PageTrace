# AGENTS.md

Instructions for coding agents working in this repository. Humans: see CONTRIBUTING.md.

## Commands

```
uv sync                       # install dev environment
uv run ruff check .           # lint
uv run ruff format --check .  # format check (never auto-apply in a PR you did not author)
uv run pyright                # strict type check
uv run pytest                 # unit + integration + acceptance + bounded property tests
uv run pytest --cov --cov-branch --cov-fail-under=90
uv build && uv run --isolated --with dist/*.whl pagetrace --version
```

All of these must pass before you report a task as done. Paste the exact commands you ran.

## Normative sources, in priority order

1. `docs/engineering-principles.md` (the constitution)
2. `specs/invariants.md` (what may be claimed, when)
3. `specs/product.md`, `specs/formats/*`
4. `docs/architecture.md` (dependency direction), `docs/testing.md`, `docs/security.md`
5. Existing tests

If the task conflicts with these, stop and say so. Do not resolve the conflict silently.

## Hard rules

- Never emit a finding stronger than the evidence proves. `PROVEN` needs the invariant's
  preconditions satisfied in the trace; otherwise `SUSPICIOUS` or `INSUFFICIENT_EVIDENCE`.
- Core (`model`, `normalize`, `selectors`, `checks/`) is pure: no I/O, clock, randomness, env.
- Dependency direction is downward only (see `docs/architecture.md`). `checks/` never imports
  `inputs/`, `render/`, `cli`.
- No network code, ever. No HTTP library, even for tests.
- No new runtime dependency without an ADR in `docs/adr/`.
- No new abstraction (plugin, registry class, base class, DI) without a second concrete user.
- Do not weaken, delete or rewrite tests to make an implementation pass. Do not touch tests you
  were not asked to touch.
- Do not change observable behavior outside the task. Every behavior change updates the spec
  and the PR field `Spec impact`.
- Never print or log headers, cookies, or raw bodies. Rendered values are escaped and truncated.
- Scratch files go to `.work/` (gitignored). Never commit plans, transcripts or reasoning.

## Roles

Prompts live in `.claude/agents/`: `verifier`, `implementer`, `reviewer`, `critic`.
Workflow: verifier designs the oracle -> implementer makes the smallest change -> deterministic
checks -> reviewer (fresh context, findings only) -> critic for invariant engine, evidence
model, parser security, schema, release changes -> fixes -> CI -> merge. AI review never
decides merge.

## Done means

See "Definition of Done" in CONTRIBUTING.md. Short version: spec impact stated, oracle exists
before code, negative and insufficient-evidence cases covered, regression test for bug fixes,
all gates green, output deterministic.
