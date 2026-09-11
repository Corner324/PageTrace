<img src="docs/assets/header.svg" alt="PageTrace" width="880">

# PageTrace

Offline checker for recorded API pagination traces: it reads a capture and reports what the
trace proves about the pagination, without touching the network.

[![CI](https://github.com/OWNER/pagetrace/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/pagetrace/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](docs/compatibility.md)
[![PyPI](https://img.shields.io/badge/pypi-not%20yet%20published-lightgrey.svg)](docs/compatibility.md#releasing)

The repository has no remote yet: the CI badge has nothing to resolve against, the workflows in
`.github/workflows/` have never run, and every number below was measured locally.

## What it does

You record a pagination run - JSONL or a browser HAR - and point PageTrace at the file. It
normalizes the pairs into a page stream, runs eleven invariants over it, and prints findings:
cursor mismatches, stalls, cycles, duplicate items, page and offset jumps, `has_more`
inconsistencies, totals that do not line up. The rule the whole design serves: never claim more
than the trace proves. Every finding says how sure it is and shows the observations behind it.
There are no confidence scores anywhere.

## A real run

```bash
uv run pagetrace check examples/broken-cursor.jsonl
```

```
broken-cursor.jsonl: 3 pages, preset cursor

PROVEN ERROR CURSOR_CONTINUATION_MISMATCH [INV-CURSOR-001] pages 1, 2
  Page 2 was requested with a continuation token that page 1 did not return.
  page[1].response.next_cursor = "eyJvIjo0fQ"
  page[2].request.cursor = "eyJvIjozfQ"

PROVEN WARNING DUPLICATE_ITEM_ACROSS_PAGES [INV-ITEM-001] pages 1, 2
  An item observed on page 1 was observed again on page 2; its identity is in the evidence below. That the same item appears twice is a fact; whether it means overlapping pages depends on a uniqueness contract this trace does not contain.
  page[1].items[0].id = 3
  page[2].items[0].id = 3

2 proven, 0 suspicious, 0 insufficient evidence
```

Exit code 1. `examples/clean-cursor.jsonl` is the same run without the defects, and exits 0.

## Install and run

From a clone, with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv run pagetrace check examples/broken-cursor.jsonl
```

With pip into an environment of your own, or `pipx install .` for a standalone command:

```bash
pip install .
```

Installing from PyPI is not available yet: the release workflow publishes through Trusted
Publishing over OIDC with no token fallback, so nothing can be published until a trusted publisher
is configured for the project and the `pypi` environment
([docs/compatibility.md](docs/compatibility.md)).

## Capturing a trace

A JSONL trace is one JSON object per line, one per request/response pair, in capture order. This
is the first line of `examples/broken-cursor.jsonl`:

```json
{"v": 1, "seq": 0, "request": {"method": "GET", "url": "https://api.example.com/v1/items?limit=2"}, "response": {"status": 200, "headers": {"content-type": "application/json"}, "body": {"items": [{"id": 1, "name": "item-1"}, {"id": 2, "name": "item-2"}], "next_cursor": "eyJvIjoyfQ", "has_more": true, "total": 5}}}
```

`v` and `response.status` are required; `seq` is optional and line order is authoritative. Full
rules: [specs/formats/jsonl-v1.md](specs/formats/jsonl-v1.md). For a HAR: open DevTools, go to
the Network tab, reproduce the pagination, export the request list as HAR. A browser capture
holds every asset the page loaded, so filter it down to the API calls (substitute your own file
and path):

```bash
uv run pagetrace check your-capture.har --url-filter /v1/items
```

`OPTIONS` and `HEAD` requests are dropped before pages are numbered, so a CORS preflight never
looks like a client that failed to advance.

## Presets

Selectors are [RFC 9535](https://www.rfc-editor.org/rfc/rfc9535.html) JSONPath. A preset default
that does not match resolves to "not found" and proves nothing, rather than becoming a guess.

| Preset | Default selectors | Fits |
| ------ | ----------------- | ---- |
| `cursor` (default) | `--cursor $.query.cursor`, `--next $.next_cursor`, `--items $.items`, `--id $.id`, `--total $.total`, `--has-more $.has_more` | APIs that hand back an opaque continuation token |
| `page` | `--page $.query.page`, plus the same items / id / total / has-more defaults | APIs paginated by page number, 0-based or 1-based |
| `offset` | `--offset $.query.offset`, plus the same items / id / total / has-more defaults | APIs taking an offset and a limit |
| `link` | items / id / total / has-more only; continuation comes from the HTTP `Link` header | APIs that advertise `rel="next"` in a Link header (RFC 8288) |

Every default is overridable by flag; `uv run pagetrace check --help` lists them all.

## Certainty, severity, exit codes

| Certainty | Meaning |
| --------- | ------- |
| `PROVEN` | the trace itself shows it, with the preconditions satisfied |
| `SUSPICIOUS` | consistent with a defect and with an innocent explanation |
| `INSUFFICIENT_EVIDENCE` | the selector or the trace did not supply what the check needs |

Severity is the second, independent axis: `ERROR` means a defect if the claim is true, `WARNING`
worth looking at, `INFO` exists so silence can be told apart from a clean result.

| Code | Meaning |
| ---- | ------- |
| 0 | nothing both proven and severe |
| 1 | at least one `PROVEN` finding of severity `ERROR` |
| 2 | invalid input or configuration |

Exit 1 needs both axes. A duplicate item across pages is `PROVEN WARNING` and does not fail a
build: the finding declines to say whether overlapping windows are a bug, so failing on it would
be the tool claiming what its own message refuses to. A build that goes red on "this might be a
cache" trains people to ignore the tool. For CI take the machine formats, not the terminal text:

```bash
uv run pagetrace check examples/broken-cursor.jsonl --format json --output report.json
```

## What it will not tell you

- That pagination never terminates. A finite trace can prove the sequence revisited a state, which
  is what `INV-CURSOR-003` says. A cycle back to the page-0 state after a `null` cursor drops to
  `SUSPICIOUS`, because two concatenated runs look the same.
- That records are missing. `INV-TOTAL-001` compares a declared total against observed identities
  and is never worded as "N records are missing": PageTrace does not know that `total` counts the
  same population, that the dataset held still, or that the same filters applied to both.
- That the API is at fault. `INV-CONT-001` and `INV-TRACE-001` report that the trace ended while
  the server was still offering more, and name neither the API, the client, nor the recorder.
- Anything about a duplicate item beyond the duplicate itself, without a uniqueness contract the
  trace does not contain.
- Anything from a page it could not read. Non-2xx responses are excluded from every body-derived
  check, reported once by `INV-TRACE-002`, so a trace nobody could read never looks clean.
- Anything a selector did not resolve. Matching nothing, matching twice, or landing on an object is
  `INSUFFICIENT_EVIDENCE` naming the flag, never a guess. JSON `null` is a different state: an
  observation meaning "the server declared no continuation".
- That `5` and `"5"` differ - comparison is on the canonical text form, because a query parameter
  can only carry text - or that a truthy `1` or `"true"` means `has_more`. Only a boolean counts.

Every claim and every non-claim condition is in [specs/invariants.md](specs/invariants.md), the
normative contract for the tool.

## Security

A HAR or JSONL trace is an untrusted, secret-bearing file. Parsers keep exactly one response
header, `link`, because exactly one is read; `authorization`, `cookie` and everything else is
dropped before the model is built. Raw bodies never reach a detector or a renderer - `Page` has no
field for them - so only the scalars you selected are displayed, with control characters escaped
and lengths truncated. Input is bounded per line and per decoded body, exceeding a limit is a
usage error rather than a traceback, and the package contains no networking dependency or code
path at all. Threat table and limits: [docs/security.md](docs/security.md).

## Performance

Measured 2026-09-11, one run per shape on a Windows 11 developer machine with CPython 3.12.6;
memory is peak Python allocation from `tracemalloc`. The shape of the numbers is the finding,
not the third digit.

| Shape | Pages | Items | Seconds | Peak MiB |
| ----- | ----: | ----: | ------: | -------: |
| wide | 1 000 | 100 000 | 2.6 | 16.1 |
| very wide | 1 000 | 1 000 000 | 20.9 | 156.8 |
| ten thousand pages | 10 000 | 1 000 000 | 28.3 | 142.8 |
| hundred thousand pages | 100 000 | 5 000 000 | 120.8 | 715.4 |

Three time targets are missed and stay written down as targets: 1k pages / 100k ids wants 2 s and
takes 2.6 s; 10k pages / 1M ids wants 10 s and takes 28.3 s, about 3x over; the 100k pages / 5M
ids stretch target wants 60 s and takes 120.8 s, about 2x over. Both memory targets are met with
room to spare, 142.8 MiB against 512 MiB and 715.4 MiB against 2 GiB. Cost tracks items far more
than pages. Full table and reasoning: [docs/performance.md](docs/performance.md).

## Working on it

```bash
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
```

425 tests pass locally at 98.97% branch coverage (`uv run pytest --cov --cov-branch`), on 3.11,
3.12, 3.13 and 3.14 on Windows. The property suite in `tests/property/` is the main correctness
layer: a valid generated trace must produce no `PROVEN` finding, and each mutation operator must
wake exactly one detector. Mutation testing is configured for `mutmut` but has never been run -
mutmut does not run on Windows, and the nightly Linux job it would come from has never run either.

Before a new detector: an entry in [specs/invariants.md](specs/invariants.md) with its non-claim
conditions, then the test oracle, then the code. [CONTRIBUTING.md](CONTRIBUTING.md) has the
workflow and the definition of done, [AGENTS.md](AGENTS.md) the same for coding agents, and the
rest is in [docs/architecture.md](docs/architecture.md), [docs/testing.md](docs/testing.md),
[docs/compatibility.md](docs/compatibility.md), [docs/adr/](docs/adr/) and
[CHANGELOG.md](CHANGELOG.md). License: MIT, see [LICENSE](LICENSE).
