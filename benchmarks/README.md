# Benchmarks

```bash
uv run python -m benchmarks.bench_pipeline --smoke
uv run python -m benchmarks.bench_pipeline --json benchmark-results/latest.json
```

- `generate.py` builds the corpus described in `docs/performance.md` in memory. Nothing large is
  committed, which is also why a hundred thousand pages is cheap to test.
- `bench_pipeline.py` times normalize plus checks and reports peak Python allocation. Resident
  set size would need a dependency; this number is the one a change to PageTrace can move.

Every PR runs `--smoke` and fails only on a gross regression. Nightly runs the full corpus and
keeps the JSON. Measured results, and the gap to the targets, are in `docs/performance.md`.
