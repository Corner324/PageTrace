"""Input and display limits. See docs/security.md.

These are code constants on purpose: a trace file must never be able to raise a limit that
protects the process reading it.
"""

from __future__ import annotations

# Largest single JSONL line accepted, in bytes.
MAX_LINE_BYTES = 64 * 1024 * 1024

# Largest decoded HAR response body accepted, in bytes.
MAX_BODY_BYTES = 64 * 1024 * 1024

# Characters of a scalar shown in rendered evidence before truncation.
MAX_DISPLAY_CHARS = 120
