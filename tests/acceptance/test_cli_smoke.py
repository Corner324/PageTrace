"""Acceptance: the installed CLI starts, reports its version, and never leaks a traceback."""

import subprocess
import sys

import pytest

from pagetrace import __version__
from pagetrace.cli import EXIT_USAGE, main


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"pagetrace {__version__}"


def test_check_is_not_implemented_yet(tmp_path: object) -> None:
    assert main(["check", "trace.jsonl"]) == EXIT_USAGE


def test_module_entry_point_has_no_traceback() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pagetrace", "check", "nope.jsonl"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == EXIT_USAGE
    assert "Traceback" not in proc.stderr
