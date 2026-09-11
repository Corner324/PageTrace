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

- Exactly one response header, `link`, reaches the model; request headers never do. Bodies are never rendered, only selected scalars, escaped and truncated.
- Input limits on line length and decoded body size; nesting bombs and invalid UTF-8 are usage
  errors, never tracebacks.
- No networking code or dependency exists in the package.

### Correctness fixes found by review before release

An independent reviewer and an adversarial critic, each starting from the specification rather
than from the implementation, found eleven defects on a suite that was already green. All are
fixed with a regression test naming what the defect used to do
(`tests/unit/test_regressions.py`, `tests/unit/test_link_header.py`).

- The Link header is now parsed per RFC 8288. A relative target is resolved against the request
  URL, a comma inside a quoted parameter no longer splits the header, `rel="next-archive"` is
  no longer read as `next`, and a header that cannot be parsed is reported as missing evidence
  instead of as "the server declared the end".
- A page number of `"²"` used to raise `ValueError` out of the core: `str.isdigit()` is
  true for characters `int()` refuses. Only ASCII digits count now.
- A response body recorded as text used to be handed to the JSONPath engine, which parses a
  string as a JSON document. Malformed text crashed, and text containing JSON was read as
  though it were the response. Only containers are queried now.
- An item identity is no longer interpolated into a finding's message, so terminal escapes in
  an id can no longer reach a terminal or break JUnit XML. Messages never carry trace values.
- `OPTIONS` and `HEAD` requests are dropped before pages are numbered. A browser HAR puts a CORS
  preflight in front of every cross-origin request, and it used to read as a stalled cursor.
- A declared total is no longer compared as PROVEN when a request in the trace failed, or when
  another page declares a total that is not an integer.
- A stall on a second cursor value, and a second run of identical responses after a failed
  request, used to go unreported.
- An offset contract witnessed only after the violation no longer proves it.
- Requests excluded from analysis are reported (INV-TRACE-002). A trace of nothing but failures
  used to produce the same silence as a trace that was fine.
- `exit 1` now requires a finding that is both `PROVEN` and `ERROR`. A duplicate item is a
  proven observation whose meaning the finding itself declines to assert, and failing a build on
  it would be the tool claiming what its message refuses to.

### Correctness fixes found by a second, independent audit

A fresh audit of the whole repository, again starting from the specification, found four more
defects and several documented claims the code did not keep.

- A declared total that changes between pages now reports nothing at all, as INV-TOTAL-001
  requires. It used to emit an insufficient-evidence finding whose message asserted that the
  dataset had moved, which the trace does not show.
- INV-CONT-002 and INV-CURSOR-002 now report missing evidence instead of staying silent when the
  items array, or the request cursor on both sides of a transition, could not be observed.
  Silence there looked like a check that had passed.
- Page-number, offset and total findings no longer interpolate selected values into their
  messages. Every number travels in `evidence`, where it is escaped and truncated
  (global precondition 8).
- `CURSOR_PRESETS` moved to `checks/base.py`; no detector imports another any more.

### Security fixes

- A JSON integer longer than CPython will build (`sys.int_max_str_digits`) used to escape the
  parser as an uncaught `ValueError`. It is a usage error now, like every other bad input.
- `NaN`, `Infinity` and `-Infinity` are rejected at both parsers. CPython accepts them; JSON
  does not, and a report carrying one matched neither the schema nor a strict parser.
- The trace filename in the terminal header, and every error on its way to stderr, are escaped.
  Neither is an observation, so neither passed through `render.display`.

### Contract and release

- The JSON schema now requires the `input` block and its three fields. The renderer always
  wrote them; the schema could not catch their loss.
- The release workflow fails when the tag and `project.version` disagree, and runs the benchmark
  smoke that `docs/performance.md` says a release blocks on.

### Performance

- Single-name selectors are resolved without the JSONPath engine's node machinery, held to the
  same answers by a differential property test. Million-item traces went from 118 s to 28 s.
- Measured numbers, and where they still miss the targets, are in `docs/performance.md`.
