# Benchmarks

Written at step 25 of the development sequence, after the first detectors exist.

- `generate.py`: builds the corpus described in `docs/performance.md` programmatically. Nothing
  large is committed.
- `bench_pipeline.py`: runs parse -> normalize -> check on each corpus entry, reports median
  wall time and peak RSS, writes `benchmark-results/` (gitignored).

PR runs a small smoke; nightly runs the full corpus; release blocks on budget regression.
