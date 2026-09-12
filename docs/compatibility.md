# Compatibility

## Python and OS

`requires-python = ">=3.11"`. CI matrix: 3.11, 3.12, 3.13, 3.14 on Linux; smoke on Windows and
macOS. Python 3.15 is checked nightly as advisory until it is stable.

The whole suite was run locally on 3.11, 3.12, 3.13 and 3.14 on Windows 11 at 0.1.0, passing on
each. A test count is not recorded here; it goes stale on the next commit and proves nothing CI
does not. macOS has not been run by hand; CI is the only evidence there.

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

## Releasing

1. `CHANGELOG.md` describes the version, and `pyproject.toml` carries it.
2. Push the tag `vX.Y.Z`. That triggers `.github/workflows/release.yml`, which reruns every
   gate with the extended property profile, builds once, smoke-installs the built wheel,
   attests the artifacts, and publishes through OIDC.
3. The `publish` job waits for a required reviewer on the `pypi` environment. Approve it only
   after `build` has passed. PyPI trusts this repository, the `release.yml` workflow and the
   `pypi` environment through a trusted publisher; there is no API token anywhere and no
   token fallback by design. First published this way: 0.1.0, 2026-09-12.

## Branching

`main` plus short-lived feature branches, squash merge. No `develop`, no release branches.
