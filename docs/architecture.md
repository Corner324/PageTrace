# Architecture

```
            UNTRUSTED INPUT
                  |
        +---------+---------+
        |                   |
       HAR                JSONL          inputs/har.py, inputs/jsonl.py
        |                   |
        +---------+---------+
                  v
            INPUT PARSER                  header allowlist, size limits (limits.py)
                  v
           RawObservation                 model.py: the only object holding a body
                  v
             NORMALIZER                   normalize.py + selectors.py
                  v
      Normalized Page Stream              model.py: frozen Page and Trace
                  v
          INVARIANT ENGINE                checks/* (pure, deterministic)
                  v
              Finding[]
                  v
      +-----------+-----------+
      v           v           v
   terminal     JSON        JUnit         render/*
```

## Modules

| Module | Holds |
| ------ | ----- |
| `model.py` | every value object: observations, pages, traces, findings, evidence |
| `errors.py` | `PageTraceError`, the one exception that means exit code 2 |
| `limits.py` | input and display limits, as code constants a trace cannot raise |
| `inputs/` | parsers, plus `as_object`/`as_array` and the header allowlist |
| `selectors.py` | RFC 9535 JSONPath, and the single-name fast path |
| `normalize.py` | presets, selector sets, URL canonicalization, fingerprints |
| `checks/base.py` | helpers shared by detectors, so no detector imports another |
| `checks/*.py` | one file per invariant family; `checks/__init__.py` is the registry |
| `render/` | display safety, then terminal, JSON and JUnit |
| `cli.py` | argument parsing, file I/O, exit codes. The composition root |

## Dependency direction: downward only

| Module | May import | Must not know about |
| ------ | ---------- | ------------------- |
| `inputs/*` | `model`, `errors`, `limits` | checks, render, cli |
| `normalize`, `selectors` | `model`, `errors` | inputs, render, cli |
| `checks/*` | `model`, `checks/base` | inputs, render, cli, argparse, whether input was HAR |
| `render/*` | `model`, `checks` (for the invariant list), `limits` | inputs, cli |
| `cli` | everything | nothing forbidden; it is the composition root |

A detector receives only normalized observations. Authorization headers, cookies and raw bodies
never reach it because `Page` has no field for them. That is structural, not a convention
somebody has to remember.

## Domain objects

`RawObservation`, `Trace`, `Page`, `Observation`, `ItemsObservation`, `ItemIdentity`, `Finding`,
`Evidence`. All `@dataclass(frozen=True, slots=True)`. No Pydantic, no ORM, no DI.

## Core API

```
normalize(raw, selectors, preset) -> Page
build_trace(raws, selectors, preset, format) -> Trace
run_checks(trace)                 -> list[Finding], sorted
```

The same normalized trace always yields the same findings, in the same order, with the same
evidence. No clock, no randomness, no environment, no network anywhere in the core.

## Streaming-friendly boundaries

JSONL parses one bounded line at a time; the engine consumes a list of pages because cycle and
duplicate detection need to look backwards anyway. Memory behavior is measured in
`docs/performance.md`. Presets are an ordinary dict, not a plugin registry, and stay that way
until a second implementer actually needs one.
