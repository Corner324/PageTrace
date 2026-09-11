# Security and privacy

A HAR or JSONL trace is an untrusted, secret-bearing file. Treat it that way.

## Threat model

| Threat | Mitigation |
| ------ | ---------- |
| Huge file / memory exhaustion | bounded per line and per body; the whole trace is still held in memory, so peak memory grows with the file (see Input limits) |
| Deep JSON | nesting depth limit at the parser |
| Non-JSON tokens (`NaN`, `Infinity`) | rejected at the parser, so no report can carry a value that is not JSON |
| Huge strings | cap extracted and rendered value sizes |
| Terminal escape injection | escape control characters in every rendered value |
| Authorization headers, cookies | header allowlist at parse time: only `link` enters the model |
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

Filenames and operating system error strings are not observations and never pass through
`render.display`, so they are escaped separately: the terminal header escapes the trace name,
and `cli.main` escapes every error on its way to stderr.

## Header allowlist, not a denylist

Parsers keep exactly one response header, `link`, because exactly one is read: the link preset
needs it. Everything else, including `authorization`, `cookie` and `set-cookie`, is dropped
before the model is built. A denylist would leak the next secret header somebody invents; an
allowlist cannot, and an allowlist with an unused entry on it is surface for nothing.

The one place a denylist appears is the opposite direction: `SECRET_QUERY_PARAMETERS` in
`normalize.py` blanks credential-shaped query values before a URL is shown as evidence under
the link preset. That is display of a value the user pointed PageTrace at, where redacting
everything would leave a finding that proves nothing, so the trade runs the other way. An
unusual parameter name is not caught.

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

There is deliberately no cap on the number of records. A parse is bounded per line and per body,
but the normalized trace is held in memory for the whole run, so a large enough capture can still
exhaust RAM. The detectors compare pages with each other, which a per-record streaming pass
cannot do, and rejecting a legitimate trace at an invented ceiling is the worse failure. The cost
is measured in docs/performance.md.

## Reporting

See `SECURITY.md` at the repository root.
