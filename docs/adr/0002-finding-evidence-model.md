# 0002 Finding and evidence model: discrete certainty, no scores

Status: Proposed

## Context

The tool's value is refusing to over-claim. A numeric confidence invites false precision and
hides which precondition was missing.

## Decision

`Finding = (code, invariant, certainty, severity, message, affected_pages, evidence[])`.
Certainty is one of `PROVEN`, `SUSPICIOUS`, `INSUFFICIENT_EVIDENCE`; severity is one of `INFO`,
`WARNING`, `ERROR`. The two axes are independent. Evidence is a list of `(path, value)` facts
observed in the trace; conclusions are never stored as evidence. No probability fields exist.

## Consequences

- Every detector must state its non-claim conditions in `specs/invariants.md`.
- Exit code depends only on the presence of PROVEN findings.
- Renderers can show "why" without re-running analysis.
