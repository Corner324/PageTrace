# Feature specs

Create `specs/features/<slug>.md` only when a change introduces a new detector, changes public
semantics or a format, spans several PRs, or has contested edge cases. Simple bug fixes live in
the issue plus tests.

Template:

```
# <feature>
Issue: #
Spec impact: which normative file changes
Problem:
Proposed behavior:
Acceptance criteria:
Edge cases and insufficient-evidence cases:
Open questions:
```

When done: durable rules move into `product.md` / `invariants.md`, architectural choices into an
ADR, and this file may be deleted.
