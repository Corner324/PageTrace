"""CLI entry point. Wiring only; no analysis logic lives here (docs/architecture.md)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from pagetrace import __version__

# Exit code contract (specs/product.md). Public, versioned with the CLI.
EXIT_OK = 0  # no PROVEN violations
EXIT_VIOLATIONS = 1  # at least one PROVEN violation
EXIT_USAGE = 2  # invalid input / configuration


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pagetrace", description=__doc__)
    parser.add_argument("--version", action="version", version=f"pagetrace {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="check a recorded pagination trace")
    check.add_argument("trace", help="path to a JSONL trace (specs/formats/jsonl-v1.md)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "check":
        print("pagetrace: analysis engine not implemented yet", file=sys.stderr)
        return EXIT_USAGE
    return EXIT_USAGE  # pragma: no cover - argparse rejects unknown commands
