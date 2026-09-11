## Problem

Issue: #

## Spec impact

<!-- none | updated <path>. "none" with an observable behavior change needs a reason. -->

## Invariants touched

<!-- INV-... IDs, or "none" -->

## Oracle

<!-- Which tests/properties fail before this change and pass after. For bug fixes: regression file. -->

## Risk

- [ ] high-risk (invariant engine / evidence model / parser security / schema / release): critic pass done
- [ ] new runtime dependency: ADR linked
- [ ] security/privacy impact considered
- [ ] performance-sensitive: measured

## Checks run locally

```
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
```
