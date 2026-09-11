# Security and privacy

A HAR or JSONL trace is an untrusted, secret-bearing file. Treat it that way.

## Threat model

| Threat | Mitigation |
| ------ | ---------- |
| Huge file / memory exhaustion | streaming parsers; documented input limits |
| Deep JSON | nesting depth limit at the parser |
| Huge strings | cap extracted and rendered value sizes |
| Terminal escape injection | escape control characters in every rendered value |
| Authorization headers, cookies | header allowlist at parse time: only `link` and `content-type` enter the model |
| API keys / secrets in bodies | raw bodies never rendered; only selected scalars, truncated |
| Malicious JSONPath | RFC 9535 compliant parser; no `eval` |
| Code execution | JSON only; no pickle, no templates, no `eval` |
| Path traversal | output only to the explicitly supplied `--output` path |
| Unexpected network calls | no networking dependency or code path exists |
| Base64 bomb in HAR | bound decoded response size |
| Log leakage | no body or header logging, ever |

## Display policy for values

A cursor or item ID the user selected may be shown, but: control characters escaped, length
truncated, never multiline raw. Prefer `cursor="eyJ..." (37 chars)` over the full value.

## Header allowlist, not a denylist

Parsers keep exactly two response headers: `link` (needed by the `link` preset) and
`content-type`. Everything else, including `authorization`, `cookie` and `set-cookie`, is
dropped before the model is built. A denylist would leak the next secret header somebody
invents; an allowlist cannot.

## Diagnostic policy

Renderers receive normalized observations, not raw input. The invariant engine physically cannot
access headers or full bodies. This is security by architecture, not by discipline.

## Input limits

Defaults in `src/pagetrace/limits.py`, all overridable only in code, never by the trace itself:

| Limit | Default | Enforced in |
| ----- | ------- | ----------- |
| bytes per JSONL line | 64 MiB | `inputs/jsonl.py` |
| JSON nesting depth | CPython recursion limit, `RecursionError` caught | both parsers |
| rendered scalar length | 120 characters, then truncated with the true length shown | `render/` |
| decoded HAR body | 64 MiB | `inputs/har.py` |

Exceeding a limit is a usage error (exit 2) naming the line or entry, never a traceback.

## Reporting

See `SECURITY.md` at the repository root.
