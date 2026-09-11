"""Command line entry point and the composition root.

Wiring only. Every decision this module makes is about argument handling, file I/O and exit
codes; nothing here knows why a finding is proven.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pagetrace import __version__
from pagetrace.checks import run_checks
from pagetrace.errors import PageTraceError
from pagetrace.inputs import detect_format, read_trace
from pagetrace.model import Trace, exit_code_for
from pagetrace.normalize import PRESET_DEFAULTS, PRESETS, SelectorSet, build_trace, filter_requests
from pagetrace.render.json import render_json
from pagetrace.render.terminal import render_terminal

# Exit code contract (specs/product.md). Public, versioned with the CLI.
EXIT_OK = 0
EXIT_VIOLATIONS = 1
EXIT_USAGE = 2

FORMATS = ("terminal", "json", "junit")
INPUT_FORMATS = ("auto", "jsonl", "har")

_SELECTOR_HELP = {
    "cursor": "request-side continuation token",
    "next": "response-side continuation token",
    "page": "request-side page number",
    "offset": "request-side offset",
    "items": "response-side array of items",
    "id": "item-side identity, relative to one item",
    "total": "response-side declared total",
    "has-more": "response-side continuation flag",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pagetrace",
        description="Check a recorded API pagination trace. Never claims more than it proves.",
    )
    parser.add_argument("--version", action="version", version=f"pagetrace {__version__}")
    subcommands = parser.add_subparsers(dest="command", required=True)

    check = subcommands.add_parser("check", help="check a recorded pagination trace")
    check.add_argument("trace", type=Path, help="path to a JSONL or HAR trace")
    check.add_argument("--preset", choices=PRESETS, default="cursor")
    check.add_argument("--input-format", choices=INPUT_FORMATS, default="auto")
    check.add_argument("--format", choices=FORMATS, default="terminal", dest="output_format")
    check.add_argument("--output", type=Path, default=None, help="write the report here")
    check.add_argument("--url-filter", default=None, help="keep only URLs containing this text")
    for flag, description in _SELECTOR_HELP.items():
        defaults = sorted(
            {
                preset: expressions[flag.replace("-", "_")]
                for preset, expressions in PRESET_DEFAULTS.items()
                if flag.replace("-", "_") in expressions
            }.items()
        )
        shown = ", ".join(f"{preset}: {expression}" for preset, expression in defaults)
        check.add_argument(
            f"--{flag}",
            default=None,
            metavar="JSONPATH",
            help=f"{description} (defaults - {shown})" if shown else description,
        )
    return parser


def analyze(args: argparse.Namespace) -> Trace:
    """Read the trace file and normalize it into a page stream."""
    selectors = SelectorSet.build(
        args.preset,
        {
            "cursor": args.cursor,
            "next": args.next,
            "page": args.page,
            "offset": args.offset,
            "items": args.items,
            "id": args.id,
            "total": args.total,
            "has_more": args.has_more,
        },
    )
    source_format = detect_format(args.trace) if args.input_format == "auto" else args.input_format
    raws = filter_requests(read_trace(args.trace, args.input_format), args.url_filter)
    if not raws:
        raise PageTraceError(f"no requests left to analyze after --url-filter {args.url_filter!r}")
    return build_trace(raws, selectors, args.preset, source_format)


def run_check(args: argparse.Namespace) -> int:
    trace = analyze(args)
    findings = run_checks(trace)

    if args.output_format == "terminal":
        report = render_terminal(trace, findings, args.trace.name)
    elif args.output_format == "json":
        report = render_json(trace, findings)
    else:  # pragma: no cover - the JUnit renderer arrives with its own tests
        raise PageTraceError(f"--format {args.output_format} is not implemented yet")

    _write(report, args.output)
    return exit_code_for(findings)


def _write(report: str, output: Path | None) -> None:
    if output is None:
        sys.stdout.write(report)
        return
    try:
        output.write_text(report, encoding="utf-8")
    except OSError as exc:
        raise PageTraceError(f"cannot write {output}: {exc}") from exc


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_check(args)
    except PageTraceError as exc:
        print(f"pagetrace: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        print("pagetrace: interrupted", file=sys.stderr)
        return EXIT_USAGE
