# 0001 Normalized domain model between parsers and checks

Status: Proposed

## Context

Inputs (JSONL, HAR) differ in shape and carry secrets. Detectors must be deterministic, testable
with generated data, and unable to leak headers or bodies.

## Decision

Parsers produce a normalized page stream of frozen dataclasses (`Trace`, `Page`,
`RequestObservation`, `ResponseObservation`, `Continuation`, `ItemIdentity`). Detectors accept
only this model. Selectors are applied in the normalizer, once.

## Consequences

- Property tests generate model objects directly; no need to serialize to JSONL.
- Adding HAR touches only `inputs/har.py`.
- Secrets are excluded structurally: the model has no field for them.
- Cost: one extra representation to keep in sync with the JSONL spec.
