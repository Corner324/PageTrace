# PageTrace: product specification

Status: normative. Changes require a PR with `Spec impact: updated specs/product.md`.

## What PageTrace is

An offline command-line checker for recorded API pagination traces. Input is a trace
(JSONL v1 or HAR). Output is a list of findings about the pagination sequence.

## Constitutional rule

**Never claim more than the trace proves.** See `docs/engineering-principles.md`.

## What it does

- Reads a recorded sequence of request/response pairs.
- Normalizes them into a page stream using a pagination preset and user-supplied selectors
  (cursor, next, items, id, total, has_more, page, offset).
- Runs invariant checks from `specs/invariants.md`.
- Emits findings with an explicit certainty: `PROVEN`, `SUSPICIOUS`, `INSUFFICIENT_EVIDENCE`.
- Renders to terminal, JSON (`specs/formats/report-json-v1.schema.json`), JUnit.

## What it does not do, by design

- Never performs network requests. No HTTP dependency exists in the package.
- Never interprets opaque cursors.
- Never states that pagination "never terminates" from a finite trace. It may prove that the
  recorded sequence revisited a state.
- Never states "missing records" from an opaque-cursor trace alone.
- Never assigns numeric confidence scores.
- Never prints Authorization headers, cookies, or raw bodies.

## CLI contract

```
pagetrace check TRACE
    [--preset {cursor,page,offset,link}]   default: cursor
    [--input-format {auto,jsonl,har}]      default: auto, by file extension
    [--format {terminal,json,junit}]       default: terminal
    [--output PATH]                        default: stdout
    [--cursor SELECTOR]     request-side continuation token
    [--next SELECTOR]       response-side continuation token
    [--page SELECTOR]       request-side page number      (preset page)
    [--offset SELECTOR]     request-side offset           (preset offset)
    [--items SELECTOR]      response-side array of items
    [--id SELECTOR]         item-side identity, relative to one item
    [--total SELECTOR]      response-side declared total
    [--has-more SELECTOR]   response-side continuation flag
    [--url-filter SUBSTRING] keep only requests whose URL contains SUBSTRING
```

Selectors are RFC 9535 JSONPath. Request-side selectors are evaluated against
`{"method","url","query"}`; response-side selectors against the parsed response body; `--id`
against a single item. Request headers are never exposed to selectors. Every selector has a preset default, listed by `--help`.

Exit codes (public contract from the first release):

| Code | Meaning |
| ---- | ------- |
| 0 | nothing both proven and severe |
| 1 | at least one `PROVEN` finding of severity `ERROR` |
| 2 | invalid input or configuration |

Certainty alone does not decide the exit code. A duplicate item across pages is a `PROVEN`
observation whose interpretation the finding itself declines to make; failing a build on it
would be the tool claiming what its own message refuses to. Severity is the axis that says
"this is a defect if true", so exit 1 needs both. `SUSPICIOUS` and `INSUFFICIENT_EVIDENCE`
findings never change the exit code, and neither does a `PROVEN` finding of severity `WARNING`.
All of them are still reported.

Requests using `OPTIONS` or `HEAD` are dropped before analysis: neither can carry a page of
results, and a browser HAR puts a CORS preflight in front of every cross-origin request.

## Public compatibility surface

Finding codes, invariant IDs, CLI flags, exit codes, JSON `schema_version`, JSONL v1 input.
See `docs/compatibility.md`.
