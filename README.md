# PageTrace

Offline checker for recorded API pagination traces. Point it at a JSONL (later HAR) capture and
it tells you what the trace proves about the pagination sequence: cursor mismatches, revisits
and cycles, duplicate items, inconsistent `has_more`, page/offset jumps, total mismatches.

The one rule: **never claim more than the trace proves.** Every finding carries a certainty
(`PROVEN`, `SUSPICIOUS`, `INSUFFICIENT_EVIDENCE`) and the exact observations behind it.

Status: pre-alpha. The CLI installs and runs; the analysis engine is not implemented yet.

```
uv sync
uv run pagetrace --version
uv run pytest
```

- What it does and does not do: `specs/product.md`
- The correctness contract: `specs/invariants.md`
- How the code is laid out: `docs/architecture.md`
- How it is tested: `docs/testing.md`
- Working on it with or without AI agents: `CONTRIBUTING.md`, `AGENTS.md`

License: MIT.
