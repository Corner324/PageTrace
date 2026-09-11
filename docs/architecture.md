# Architecture

```
            UNTRUSTED INPUT
                  |
        +---------+---------+
        |                   |
       HAR                JSONL          src/pagetrace/inputs/
        |                   |
        +---------+---------+
                  v
            INPUT PARSER                  drops secrets, enforces limits
                  v
             NORMALIZER                   src/pagetrace/normalize.py, selectors.py
                  v
      Normalized Page Stream              src/pagetrace/model.py (frozen dataclasses)
                  v
          INVARIANT ENGINE                src/pagetrace/checks/*  (pure, deterministic)
                  v
              Finding[]
                  v
      +-----------+-----------+
      v           v           v
   terminal     JSON        JUnit         src/pagetrace/render/*
```

## Dependency direction: downward only

| Module | May import | Must not know about |
| ------ | ---------- | ------------------- |
| `inputs/*` | `model` | checks, render, cli |
| `normalize`, `selectors` | `model` | inputs, render, cli |
| `checks/*` | `model` | inputs, render, cli, argparse, whether input was HAR |
| `render/*` | `model` | inputs, checks internals, cli |
| `cli` | everything | nothing forbidden; it is the composition root |

A detector receives only normalized observations. Authorization headers, cookies and raw bodies
never reach it because the parser never puts them into the model.

## Domain objects

`Trace`, `Page`, `RequestObservation`, `ResponseObservation`, `Continuation`, `ItemIdentity`,
`Finding`, `Evidence`. All `@dataclass(frozen=True, slots=True)`. No Pydantic, no ORM.

## Core API (conceptual)

```
normalize(raw_observation) -> PageObservation
check(page_stream)          -> Iterable[Finding]
```

## Streaming-friendly boundaries

Parsers yield observations; the engine consumes an iterator. Memory targets in
`docs/performance.md`. Presets are an ordinary dict, not a plugin registry.
