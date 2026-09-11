# JUnit output

Status: Active. Part of the public contract (`docs/compatibility.md`).

- One `<testsuite name="pagetrace">` carrying `tests`, `failures`, `skipped` and `errors`.
- One `<testcase>` per active invariant, in the order of `INVARIANT_IDS`. `name` is the
  invariant ID and `classname` is `pagetrace.<preset>`, so a CI report lists what was checked,
  not only what went wrong. (An earlier draft had these the other way round; grouping every
  invariant into its own class made the report useless.)
- A `PROVEN` finding of severity `ERROR`: `<failure message="..." type="<finding code>">` with
  the message and evidence lines in the body. That is the only thing that fails a build.
- `SUSPICIOUS`, and `PROVEN` findings below `ERROR`: a `<system-out>` note. The case passes.
- `INSUFFICIENT_EVIDENCE` alone on an invariant: `<skipped message="...">`.
- `errors` is always `0`. A usage error exits 2 before any report is written, so there is no
  synthetic error case to emit; the message goes to stderr instead.
- Output is deterministic: fixed ordering, no timestamps, no host names.
