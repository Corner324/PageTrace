# JSONL trace format, version 1

Status: Draft. Becomes normative with the first detector.

One JSON object per line, one object per request/response pair, in capture order.

```json
{"v": 1, "seq": 0, "request": {"method": "GET", "url": "https://api.example/items?cursor=abc", "query": {"cursor": "abc"}, "headers": {}}, "response": {"status": 200, "headers": {}, "body": {"items": [{"id": 1}], "next": "def", "has_more": true}}}
```

Rules:

- `v` is required and must equal `1`. Unknown `v` is a usage error (exit 2).
- `response.status` is required. Without it PageTrace cannot tell a page of results from an
  error envelope, and global precondition 4 of `specs/invariants.md` could not be enforced.
- `seq` is optional; when present it must be strictly increasing. Line order is authoritative.
- `request.headers` is ignored entirely. Request-side selectors see `{method, url, query}`.
- `response.headers` is filtered against an allowlist of exactly one name, `link`, used by the
  link preset. Everything else is dropped at parse time. See `docs/security.md`.
- `request.query` may be omitted; the parser then derives it from `request.url`. When both are
  present, the explicit `query` object wins.
- `response.body` is parsed JSON, or absent. A body that is not JSON is simply absent: it
  carries no observations, and recording that something unreadable was there would be a field
  nothing reads.
- Selectors (`--cursor`, `--items`, ...) are RFC 9535 JSONPath expressions evaluated against
  `request` or `response` objects as documented per flag.

Limits (docs/security.md): max line length, max nesting depth, max decoded body size. Exceeding a
limit is a usage error with the offending `seq`/line number and never a traceback.
