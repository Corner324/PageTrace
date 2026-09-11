"""The one exception type that maps to exit code 2."""

from __future__ import annotations


class PageTraceError(Exception):
    """Invalid input or configuration. Always reported as a message, never as a traceback."""
