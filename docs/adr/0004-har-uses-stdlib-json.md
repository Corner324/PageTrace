# 0004 HAR parsing uses the standard library, not a streaming parser

Status: Accepted

## Context

`docs/performance.md` anticipated adding `ijson` together with HAR support, because a HAR is a
large nested document and `json.load` builds all of it in memory. The project rule is that a
runtime dependency needs a concrete failure mode it prevents (`docs/engineering-principles.md`
point 5), and the failure mode here has not been measured yet.

## Decision

Parse HAR with `json.loads` from the standard library. Bound what a single entry can cost with
`MAX_BODY_BYTES` and catch `RecursionError` so a nesting bomb is a usage error rather than a
crash. Revisit when a benchmark on a real capture shows the resident memory actually hurting.

## Consequences

- One runtime dependency in the project, not two.
- Peak memory for HAR is roughly the size of the file times the usual parsed-JSON overhead.
  `benchmarks/` measures it; `docs/performance.md` states it as a known limit rather than a
  promise.
- Switching to a streaming parser later changes `inputs/har.py` only: the rest of the pipeline
  already consumes an iterator of raw observations.
- JSONL is unaffected and stays streaming, one bounded line at a time.
