# Security and privacy

A HAR or JSONL trace is an untrusted, secret-bearing file. Treat it that way.

## Threat model

| Threat | Mitigation |
| ------ | ---------- |
| Huge file / memory exhaustion | streaming parsers; documented input limits |
| Deep JSON | nesting depth limit at the parser |
| Huge strings | cap extracted and rendered value sizes |
| Terminal escape injection | escape control characters in every rendered value |
| Authorization headers, cookies | dropped at parse time; never in the model |
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

## Diagnostic policy

Renderers receive normalized observations, not raw input. The invariant engine physically cannot
access headers or full bodies. This is security by architecture, not by discipline.

## Reporting

See `SECURITY.md` at the repository root.
