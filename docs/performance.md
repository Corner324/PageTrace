# Performance

Engineering targets, not user-facing promises. Measured on the reference Linux CI runner.

## Complexity contract

- Without item duplicate detection: memory ~ O(number of seen pagination states).
- With exact duplicate detection: memory ~ O(unique item IDs).
- Cursor revisit and cycle detection: exact hash map `cursor -> first_seen_page`, O(n) memory.
  Floyd's algorithm is not used: the sequence is already recorded and diagnostics need the
  earlier page number.
- Bloom filters are never a source of a PROVEN finding. At most: candidate screening followed by
  exact verification. Not implemented until a benchmark demands it.

## Budgets

| Input | Budget |
| ----- | ------ |
| 1k pages / 100k IDs | <= 2 s |
| 10k pages / 1M IDs | <= 10 s |
| 10k pages / 1M IDs | <= 512 MiB RSS |
| 100k pages / 5M IDs | stretch: <= 60 s |
| 100k pages / 5M IDs | stretch: <= 2 GiB RSS |

## Corpus (benchmarks/generate.py, to be written)

pages: 1k / 10k / 100k; items per page: 0 / 10 / 100 / 1000; cursor: short / long;
IDs: int / UUID-like / long string; patterns: valid, duplicate-heavy, cycle-heavy, repeated page.

## Gating

PR: small smoke only; block on a stable regression (>20% median slowdown, confirmed by repeats).
Nightly: full corpus. Release: budget regression blocks.

HAR is parsed with the standard library (`docs/adr/0004`). Peak memory is therefore roughly the
file size times the usual parsed-JSON overhead, which is a known limit, not a promise. A
streaming parser is a dependency the project will add when a benchmark shows it is needed, and
it would touch `inputs/har.py` only. JSONL already streams, one bounded line at a time.
