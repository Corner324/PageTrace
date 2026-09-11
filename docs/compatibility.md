# Compatibility

## Python and OS

`requires-python = ">=3.11"`. CI matrix: 3.11, 3.12, 3.13, 3.14 on Linux; smoke on Windows and
macOS. Python 3.15 is checked nightly as advisory until it is stable.

## Public contract (SemVer from 0.1.0)

Breaking any of these bumps the major version after 1.0 and is a changelog headline before:

- finding codes and invariant IDs;
- CLI flags and subcommands;
- exit codes (0 / 1 / 2);
- JSON report `schema_version` and the schema in `specs/formats/`;
- JUnit structure;
- JSONL v1 input format.

Terminal output is not a contract; scripts should consume JSON.

## Versioning

SemVer. Pre-1.0 releases are `0.x`. Every release: wheel + sdist built once in CI, attested,
published via PyPI Trusted Publishing. Never from a laptop.

## Branching

`main` plus short-lived feature branches, squash merge. No `develop`, no release branches.
