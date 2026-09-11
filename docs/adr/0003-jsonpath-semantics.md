# 0003 Selectors use an RFC 9535 JSONPath implementation

Status: Proposed

## Context

Users point PageTrace at cursors, items, IDs, totals with selectors. A home-grown path language
would accumulate semantics bugs in the exact component users depend on. RFC 9535 standardizes
JSONPath.

## Decision

Selectors are RFC 9535 JSONPath. Use a compliant third-party library; this is the first runtime
dependency and is justified by the concrete failure mode "wrong selector semantics".
Library choice is recorded here when the normalizer is implemented (candidates evaluated on:
RFC 9535 compliance test suite, no `eval`, pure Python, maintenance).

## Consequences

- A selector that yields zero or more than one scalar is INSUFFICIENT_EVIDENCE for that
  observation, never a crash and never a guess.
- The dependency is pinned in `uv.lock` and reviewed by dependency review on every bump.
