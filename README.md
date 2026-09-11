# PageTrace

Offline checker for recorded API pagination traces. Point it at a JSONL or HAR capture and it
tells you what the trace proves about the pagination: cursor mismatches, stalls and cycles,
duplicate items, inconsistent `has_more`, page and offset jumps, totals that do not line up.

The one rule: **never claim more than the trace proves.** Every finding carries a certainty and
the exact observations behind it.

| Certainty | Meaning |
| --------- | ------- |
| `PROVEN` | the trace itself shows it, with the preconditions satisfied |
| `SUSPICIOUS` | consistent with a defect and with an innocent explanation |
| `INSUFFICIENT_EVIDENCE` | the selector or the trace did not supply what the check needs |

Severity is a separate axis. There are no confidence scores.

## Install and run

```bash
uv sync
uv run pagetrace check trace.jsonl
```

A trace is a JSONL file, one request/response pair per line
(see [specs/formats/jsonl-v1.md](specs/formats/jsonl-v1.md)):

```json
{"v": 1, "request": {"url": "https://api.example/items"}, "response": {"status": 200, "body": {"items": [{"id": 1}], "next_cursor": "c2", "has_more": true}}}
```

A browser HAR works too, and usually needs a filter to pick the API calls out of the noise:

```bash
uv run pagetrace check capture.har --url-filter api.example/items
```

## Telling it where to look

Selectors are [RFC 9535](https://www.rfc-editor.org/rfc/rfc9535.html) JSONPath. Each preset
ships defaults; override any of them when your API disagrees:

```bash
uv run pagetrace check trace.jsonl \
  --preset cursor \
  --cursor '$.query.after' \
  --next '$.paging.cursors.after' \
  --items '$.data' \
  --id '$.id' \
  --has-more '$.paging.has_next'
```

Presets: `cursor` (a continuation token), `page` (page numbers), `offset` (offset and limit),
`link` (the HTTP `Link` header with `rel=next`).

A selector that matches nothing, matches twice, or lands on an object does not become a guess.
It becomes `INSUFFICIENT_EVIDENCE`, and the report says which flag to look at.

## Output and exit codes

```bash
uv run pagetrace check trace.jsonl --format json --output report.json
uv run pagetrace check trace.jsonl --format junit --output junit.xml
```

| Code | Meaning |
| ---- | ------- |
| 0 | no proven violations |
| 1 | at least one proven violation |
| 2 | invalid input or configuration |

Suspicions never change the exit code and never fail a JUnit case. A build that goes red on
"this might be a cache" trains people to ignore the tool.

## What it will not tell you

- That pagination never terminates. A finite trace can prove that the sequence revisited a
  state, and that is what it says.
- That records are missing, when the cursor is opaque.
- That the API is at fault when a capture simply ends early.
- Anything about a duplicate item beyond the duplicate itself, unless you have a uniqueness
  contract the trace does not contain.

The full list of what may and may not be claimed is
[specs/invariants.md](specs/invariants.md), which is the most important file here.

## Safety

A HAR holds real credentials. PageTrace keeps an allowlist of exactly two response headers,
never prints bodies, escapes control characters, truncates long values, and has no networking
code at all. See [docs/security.md](docs/security.md).

## Working on it

```bash
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
```

[CONTRIBUTING.md](CONTRIBUTING.md) has the workflow and the definition of done;
[AGENTS.md](AGENTS.md) has the same rules in the form coding agents need.

License: MIT.
