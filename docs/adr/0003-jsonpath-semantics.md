# 0003 Selectors use an RFC 9535 JSONPath implementation

Status: Accepted

## Context

Users point PageTrace at cursors, items, IDs and totals with selectors. A home-grown path
language would accumulate semantics bugs in the exact component users depend on. RFC 9535
standardizes JSONPath, so a compliant library makes selectors portable and their behavior
someone else's tested problem.

Two candidates were installed and probed:

| Candidate | Runtime dependency tree | RFC 9535 |
| --------- | ----------------------- | -------- |
| `jsonpath-rfc9535` | itself + `regex` (C extension) + `iregexp-check` | yes |
| `python-jsonpath` | itself only, pure Python, ships `py.typed` | yes, via `strict=True` |

`regex` would be compiled code pulled in only to support I-Regexp filter functions, which a
cursor or items selector never uses.

## Decision

Depend on `python-jsonpath` and build one module-level `JSONPathEnvironment(strict=True)`.
Strict mode registers no non-standard selectors or filter extensions, so a selector accepted by
PageTrace is accepted by any compliant implementation. This is the project's only runtime
dependency, justified by the concrete failure mode "wrong selector semantics in the component
every finding rests on".

## Consequences

- A selector yielding zero, several, or non-scalar nodes is an explicit not-observed status,
  never a crash and never a guess at the first match.
- A syntax error in a selector is a usage error (exit 2) naming the flag, not a traceback.
- Non-standard convenience syntax is rejected; users get portability instead.
- The dependency is pinned in `uv.lock` and reviewed by dependency review on every bump.
