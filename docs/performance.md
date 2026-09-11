# Performance

## Complexity contract

- Without item duplicate detection: memory ~ O(number of seen pagination states).
- With exact duplicate detection: memory ~ O(unique item IDs).
- Cursor revisit and cycle detection: exact hash map `cursor -> first_seen_page`, O(n) memory.
  Floyd's algorithm is not used: the sequence is already recorded, and diagnostics need the
  earlier page number.
- Bloom filters are never a source of a PROVEN finding. At most: candidate screening followed by
  exact verification. Not implemented, and not needed by any measurement so far.

## Measured, 2026-09-11

One run per shape, `benchmarks/bench_pipeline.py`, on the maintainer's Windows 11 machine with
CPython 3.12.6. Memory is peak Python allocation from `tracemalloc`, not resident set size.
These are single measurements on a developer machine, not a distribution and not the reference
Linux runner; treat the shape of the numbers as the finding, not the third digit.

| Shape | Pages | Items | Seconds | Peak MiB |
| ----- | ----: | ----: | ------: | -------: |
| empty pages | 1 000 | 0 | 0.2 | 1.3 |
| small | 1 000 | 10 000 | 0.4 | 1.9 |
| wide | 1 000 | 100 000 | 2.6 | 16.1 |
| very wide | 1 000 | 1 000 000 | 20.9 | 156.8 |
| uuid ids | 1 000 | 100 000 | 2.0 | 12.3 |
| long string ids | 1 000 | 100 000 | 2.0 | 12.3 |
| duplicate heavy | 1 000 | 100 000 | 2.4 | 16.6 |
| cycle heavy | 1 000 | 10 000 | 0.4 | 1.9 |
| ten thousand pages | 10 000 | 1 000 000 | 28.3 | 142.8 |
| hundred thousand pages | 100 000 | 5 000 000 | 120.8 | 715.4 |

Cost tracks items far more than pages: a thousand pages of a thousand items costs about as much
as ten thousand pages of a hundred. Reading item identities is the hot path, which is why
`selectors.py` resolves a single-name selector without the JSONPath engine's node machinery
(the differential test in `tests/property/test_selector_fast_path.py` holds the two to the same
answers). That change alone took the million-item shapes from 118s to 28s.

## Targets, and the gap

| Input | Target | Measured | Met |
| ----- | -----: | -------: | --- |
| 1k pages / 100k ids | <= 2 s | 2.6 s | close, no |
| 10k pages / 1M ids | <= 10 s | 28.3 s | no, about 3x over |
| 10k pages / 1M ids | <= 512 MiB | 142.8 MiB | yes |
| 100k pages / 5M ids | <= 60 s (stretch) | 120.8 s | no, about 2x over |
| 100k pages / 5M ids | <= 2 GiB (stretch) | 715.4 MiB | yes |

Memory is comfortable. Time is not, on traces of a million items and up. This is written down
rather than quietly relaxed: the targets stay as targets, and nothing in the README promises
them to users. The next thing to try, when it matters to somebody, is cutting the per-item
object allocation in the items path, not adding a dependency.

## Corpus

`benchmarks/generate.py` builds it in memory; nothing large is committed. Pages 1k / 10k / 100k;
items per page 0 / 10 / 100 / 1000; ids as integers, UUID-like strings, and long strings;
patterns valid, duplicate-heavy, cycle-heavy, repeated-page.

## Gating

Every PR runs the smoke corpus and fails only on a gross regression: a tripwire set about three
times above current cost, so a quadratic mistake fails CI while runner noise does not.
Nightly runs the full corpus and keeps the JSON as an artifact. Release blocks on a budget
regression.

HAR is parsed with the standard library (`docs/adr/0004`). Peak memory is therefore roughly the
file size times the usual parsed-JSON overhead, which is a known limit, not a promise. A
streaming parser is a dependency the project will add when a benchmark shows it is needed, and
it would touch `inputs/har.py` only. JSONL already streams, one bounded line at a time.
