# Changelog

Format: Keep a Changelog. Versioning: SemVer.

The version in `pyproject.toml` is already `0.1.0`. Pushing the tag `v0.1.0` is what builds,
attests and publishes it; until then this entry describes what is on `main`.

## [0.1.0] - unreleased

First release. From this version on, finding codes, invariant IDs, CLI flags, exit codes, the
JSON `schema_version` and the JSONL v1 input format are a public contract
(see `docs/compatibility.md`).

### Added

- `pagetrace check` reads a JSONL v1 trace or a browser HAR and reports what the trace proves
  about its pagination.
- Eleven invariants, each with written preconditions and non-claim conditions in
  `specs/invariants.md`:
  - `INV-CURSOR-001` continuation cursor mismatch
  - `INV-CURSOR-002` request cursor stalled
  - `INV-CURSOR-003` cursor cycle
  - `INV-ITEM-001` duplicate item across pages
  - `INV-RESP-001` identical consecutive responses
  - `INV-PAGE-001` page number does not advance by one
  - `INV-OFFSET-001` offset does not advance by the item count
  - `INV-CONT-001` trace ends after `has_more=true`
  - `INV-CONT-002` empty page while more is declared
  - `INV-TRACE-001` trace ends with an unused continuation token
  - `INV-TOTAL-001` declared total against the items observed
- Four presets: `cursor`, `page`, `offset`, `link` (HTTP `Link` header with `rel=next`).
- Selectors are RFC 9535 JSONPath, in strict mode, with a preset default per flag.
- Three-valued findings: `PROVEN`, `SUSPICIOUS`, `INSUFFICIENT_EVIDENCE`, with severity as an
  independent axis and no confidence scores anywhere.
- Three renderers: terminal, JSON (`specs/formats/report-json-v1.schema.json`), JUnit.
- Exit codes 0, 1, 2. Suspicions never change the exit code and never fail a JUnit case.
- `--url-filter` for picking API calls out of a HAR, with page indexes renumbered so evidence
  refers to the sequence that was analyzed.

### Security

- Response headers are allowlisted to `link` and `content-type`; request headers never reach the
  model. Bodies are never rendered, only selected scalars, escaped and truncated.
- Input limits on line length and decoded body size; nesting bombs and invalid UTF-8 are usage
  errors, never tracebacks.
- No networking code or dependency exists in the package.

### Performance

- Single-name selectors are resolved without the JSONPath engine's node machinery, held to the
  same answers by a differential property test. Million-item traces went from 118 s to 28 s.
- Measured numbers, and where they still miss the targets, are in `docs/performance.md`.
