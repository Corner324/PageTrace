<div align="center">

<img src="https://raw.githubusercontent.com/Corner324/PageTrace/main/docs/assets/header.svg" alt="PageTrace" width="720">

**English** · [Русский](https://github.com/Corner324/PageTrace/blob/main/README.ru.md) · [中文](https://github.com/Corner324/PageTrace/blob/main/README.zh.md)

**Find out what your API pagination did, from a trace you already recorded. No network access.**

[![CI](https://github.com/Corner324/PageTrace/actions/workflows/ci.yml/badge.svg)](https://github.com/Corner324/PageTrace/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pagetrace.svg)](https://pypi.org/project/pagetrace/)
[![Coverage 98.97%](https://img.shields.io/badge/coverage-98.97%25%20branch-brightgreen.svg)](https://github.com/Corner324/PageTrace/blob/main/docs/testing.md)
[![Tests 425](https://img.shields.io/badge/tests-425-brightgreen.svg)](https://github.com/Corner324/PageTrace/blob/main/docs/testing.md)
[![Zero network](https://img.shields.io/badge/network-none-0aa344.svg)](https://github.com/Corner324/PageTrace/blob/main/docs/security.md)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://github.com/Corner324/PageTrace/blob/main/docs/compatibility.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/Corner324/PageTrace/blob/main/LICENSE)

[⚡ Install](#-install) · [🔍 How it works](#-how-it-works) · [🎯 Presets](#-presets) · [🧭 What it will not tell you](#-what-it-will-not-tell-you) · [🔒 Security](#-security) · [📐 Invariants](https://github.com/Corner324/PageTrace/blob/main/specs/invariants.md)

</div>

---

## 💡 Why this exists

A pagination bug can pass every health check you have. Each page comes back `200 OK`, the loop
ends, the logs stay clean, and the export comes up four hundred rows short. You find out weeks
later, when someone compares totals, and by then the capture is long gone.

Integration tests call the live API, so they flake. Logs record each request on its own line,
while the bug sits between two of them: page 3 sent a token that page 2 never returned. You can
spot that by reading a HAR yourself, until the trace grows past a dozen pages.

PageTrace reads the recording you already have and reports what it can prove from it.

| You hear | What PageTrace can tell you from the trace |
| -------- | ------------------------------------------ |
| "The export is missing rows" | whether a page was requested with a token the previous page never returned, whether the request sequence came back to an earlier state, or whether the capture stopped early |
| "The job never finishes" | whether the cursor got stuck on one value or the requests went back to a state they had already visited |
| "We get duplicates downstream" | which item identity appeared on which two pages |
| "Their API is broken" | whether the trace supports blaming either side (often it supports neither) |

> [!IMPORTANT]
> **The rule: PageTrace never claims more than the trace proves.**
> Each finding states its certainty and lists the observations it rests on. The tool has no
> confidence scores. If the trace lacks the evidence for a check, you get
> `INSUFFICIENT_EVIDENCE` along with the name of the flag to set.

Typical uses: a regression test in CI that fails on a proven defect, or an incident where a
colleague's HAR is the only evidence left. It also helps before you integrate with a vendor's
API, when you want findings you can send them without overstating anything.

---

## ⚡ See it in 30 seconds

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

The command exits with 1. The second finding reports a duplicate item and stops there. The trace
contains no uniqueness contract, so PageTrace does not call the duplicate a pagination bug.

`examples/clean-cursor.jsonl` holds the same run without the defects and exits with 0.

---

## 🔍 How it works

<div align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Corner324/PageTrace/main/docs/assets/flow.en.dark.svg">
  <img alt="Recorded trace, parser, normalizer, invariant engine, report. No network call at any step." src="https://raw.githubusercontent.com/Corner324/PageTrace/main/docs/assets/flow.en.light.svg" width="820">
</picture>
</div>

A detector receives normalized observations and nothing else. `Page` has no field for a raw body
or an `authorization` header, so the engine has no way to read them. The module layout is in
[docs/architecture.md](https://github.com/Corner324/PageTrace/blob/main/docs/architecture.md).

---

## ⚡ Install

```bash
pip install pagetrace
```

`pipx install pagetrace` and `uv tool install pagetrace` install it as a standalone command.

To run the examples, clone the repository and use [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv run pagetrace check examples/broken-cursor.jsonl
```

---

## 📼 Record a trace

A JSONL trace has one JSON object per line for each request and response pair, in the order you
captured them:

```json
{"v": 1, "seq": 0, "request": {"method": "GET", "url": "https://api.example.com/v1/items?limit=2"}, "response": {"status": 200, "headers": {"content-type": "application/json"}, "body": {"items": [{"id": 1, "name": "item-1"}, {"id": 2, "name": "item-2"}], "next_cursor": "eyJvIjoyfQ", "has_more": true, "total": 5}}}
```

`v` and `response.status` are required. `seq` is optional, and PageTrace goes by line order. The
full rules are in [specs/formats/jsonl-v1.md](https://github.com/Corner324/PageTrace/blob/main/specs/formats/jsonl-v1.md).

<details>
<summary><b>Or export a HAR from your browser</b>, which works with any API you can open there</summary>

<br>

In DevTools, open the Network tab, page through the results, and save the request list as a HAR.
The file also holds the scripts, images and fonts the page loaded, so filter it to the API calls:

```bash
uv run pagetrace check your-capture.har --url-filter /v1/items
```

PageTrace drops `OPTIONS` and `HEAD` requests before it numbers the pages, so a CORS preflight
does not show up as a client stuck on one page.

</details>

> [!WARNING]
> A HAR file contains live credentials. PageTrace keeps one response header and never prints a
> body, but the file on your disk still has your `Authorization` header in it. Treat it like a
> password and keep it out of public issues.

---

## 🎯 Presets

Selectors use [RFC 9535](https://www.rfc-editor.org/rfc/rfc9535.html) JSONPath. If a preset
default matches nothing, PageTrace records the value as not found and draws no conclusion from it.

| Preset | Default selectors | Fits |
| ------ | ----------------- | ---- |
| `cursor` <sub>default</sub> | `--cursor $.query.cursor` `--next $.next_cursor` `--items $.items` `--id $.id` `--total $.total` `--has-more $.has_more` | APIs that return an opaque continuation token |
| `page` | `--page $.query.page`, plus the same items / id / total / has-more defaults | page numbers, starting at 0 or 1 |
| `offset` | `--offset $.query.offset`, plus the same items / id / total / has-more defaults | an offset and a limit |
| `link` | items / id / total / has-more only; the next page comes from the HTTP `Link` header | `rel="next"` in a Link header (RFC 8288) |

> [!TIP]
> You can override each default with its flag. `uv run pagetrace check --help` lists the defaults
> by preset. When a finding says `INSUFFICIENT_EVIDENCE`, its message names the flag to set.

---

## 📊 Certainty, severity, exit codes

Each finding has two separate ratings. Certainty says how well the trace supports it, and severity
says how much it matters if it is true. Neither one is a probability.

| Certainty | Meaning |
| --------- | ------- |
| `PROVEN` | the trace shows it, and the preconditions hold |
| `SUSPICIOUS` | the trace fits a defect, and it also fits a harmless explanation |
| `INSUFFICIENT_EVIDENCE` | the selector or the trace did not provide what the check needs |

| Exit | Meaning |
| ---- | ------- |
| `0` | no finding is both proven and severe |
| `1` | at least one `PROVEN` finding has severity `ERROR` |
| `2` | invalid input or configuration |

Exit code 1 requires both ratings. A duplicate item across pages is `PROVEN WARNING` and does not
fail the build. The finding stops short of calling the duplicate a bug, and a failed build would
make that claim for it. If your build fails on something that could be a cache artifact, your
team will start ignoring the tool.

In CI, read the JSON output. PageTrace does not promise a stable terminal format:

```bash
uv run pagetrace check examples/broken-cursor.jsonl --format json --output report.json
```

---

## 🧭 What it will not tell you

PageTrace leaves these questions unanswered, even when a trace seems to point at an answer.

- Whether pagination terminates. A finite trace can show that the request sequence returned to an
  earlier state, and `INV-CURSOR-003` reports that. When the cycle returns to the page 0 state
  after a `null` cursor, the finding drops to `SUSPICIOUS`: two runs saved into one file look the
  same.
- Whether records are missing. `INV-TOTAL-001` compares the declared total with the item
  identities it observed, and its message never says "N records are missing". PageTrace cannot
  know whether `total` counts the same set of items, whether the data changed during the capture,
  or whether the same filters applied to both.
- Who is at fault. `INV-CONT-001` and `INV-TRACE-001` report that the trace ended while the server
  still offered more pages. They blame neither the API nor the client nor whoever made the
  recording.
- What a duplicate item means. The finding reports the duplicate. Calling it a bug would take a
  uniqueness contract, and traces do not carry one.
- Anything from a page PageTrace could not read. Checks that read response bodies skip non-2xx
  responses, and `INV-TRACE-002` reports the skipped requests once, so a trace full of errors does
  not pass as clean.
- Anything from a selector that did not resolve. A selector that matches nothing, matches twice or
  points at an object gives `INSUFFICIENT_EVIDENCE` with the flag named. A JSON `null` counts as an
  observation: the server said there is no next page.
- Whether `5` and `"5"` differ. PageTrace compares values as text, because a query parameter can
  only carry text. It also does not read `1` or `"true"` as `has_more`; only a JSON boolean counts.

[specs/invariants.md](https://github.com/Corner324/PageTrace/blob/main/specs/invariants.md) lists
the claims of all eleven invariants and the conditions under which each detector stays silent. The
tool follows that file as its contract.

---

## 🔒 Security

Treat a HAR or JSONL trace as untrusted input that contains secrets. The parsers keep one response
header, `link`, because the link preset reads it. They drop `authorization`, `cookie` and the rest
before building the model. Detectors and renderers never receive raw bodies, so the report shows
only the values you selected, with control characters escaped and long values truncated.
PageTrace caps line length and decoded body size, reports an oversized input as a usage error
instead of a traceback, and contains no networking code or dependency. The threat table and
limits are in [docs/security.md](https://github.com/Corner324/PageTrace/blob/main/docs/security.md).

---

## 📈 Performance

Measured on 2026-09-11 on a Windows 11 developer machine with CPython 3.12.6, one run per shape.
Memory is the peak Python allocation reported by `tracemalloc`. A second run would shift the last
digit, so read the table for proportions.

| Shape | Pages | Items | Seconds | Peak MiB |
| ----- | ----: | ----: | ------: | -------: |
| wide | 1 000 | 100 000 | 2.6 | 16.1 |
| very wide | 1 000 | 1 000 000 | 20.9 | 156.8 |
| ten thousand pages | 10 000 | 1 000 000 | 28.3 | 142.8 |
| hundred thousand pages | 100 000 | 5 000 000 | 120.8 | 715.4 |

> [!NOTE]
> PageTrace misses three time targets, and the project keeps them as targets. 1k pages / 100k ids
> should take 2 s and takes 2.6 s. 10k / 1M should take 10 s and takes 28.3 s, about 3x over. The
> 100k / 5M stretch target is 60 s, and the run took 120.8 s, about 2x over. Peak memory stayed
> under both limits: 142.8 MiB against 512 MiB, and 715.4 MiB against 2 GiB. The full table and
> analysis are in [docs/performance.md](https://github.com/Corner324/PageTrace/blob/main/docs/performance.md).

---

## 🛠 Contributing

```bash
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
```

All 425 tests pass locally with 98.97% branch coverage on Python 3.11, 3.12, 3.13 and 3.14 on
Windows. The property suite in `tests/property/` carries most of the correctness checking: no
generated valid trace may produce a `PROVEN` finding, and each mutation operator must trigger
exactly one detector. The mutation score against the unit tests was 77.9% on 2026-09-12, and
[docs/testing.md](https://github.com/Corner324/PageTrace/blob/main/docs/testing.md) sorts the
surviving mutants by hand. mutmut does not run on Windows, so that run used a Linux container.

A new detector starts with an entry in
[specs/invariants.md](https://github.com/Corner324/PageTrace/blob/main/specs/invariants.md) that
lists its non-claim conditions. The test oracle comes next, and the code last.
[CONTRIBUTING.md](https://github.com/Corner324/PageTrace/blob/main/CONTRIBUTING.md) describes the
workflow and the definition of done, and [AGENTS.md](https://github.com/Corner324/PageTrace/blob/main/AGENTS.md)
gives coding agents the same rules. For more, see
[docs/architecture.md](https://github.com/Corner324/PageTrace/blob/main/docs/architecture.md),
[docs/testing.md](https://github.com/Corner324/PageTrace/blob/main/docs/testing.md),
[docs/compatibility.md](https://github.com/Corner324/PageTrace/blob/main/docs/compatibility.md),
[docs/adr/](https://github.com/Corner324/PageTrace/tree/main/docs/adr/) and
[CHANGELOG.md](https://github.com/Corner324/PageTrace/blob/main/CHANGELOG.md).

<div align="center">

**MIT** · [LICENSE](https://github.com/Corner324/PageTrace/blob/main/LICENSE)

</div>
