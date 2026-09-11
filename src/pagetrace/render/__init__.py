"""Renderers. They receive findings and a trace, never a response body.

Display safety lives here because it is the only place a trace value becomes output:
control characters are escaped and long values truncated (docs/security.md).
"""

from __future__ import annotations

from dataclasses import dataclass

from pagetrace.limits import MAX_DISPLAY_CHARS
from pagetrace.model import Scalar


@dataclass(frozen=True, slots=True)
class Display:
    """A trace value made safe to print, and the truth about what was cut."""

    text: str
    truncated: bool
    length: int


def display(value: Scalar, limit: int = MAX_DISPLAY_CHARS) -> Display:
    """Escape control characters and truncate, reporting the original length.

    A cursor is attacker-influenced text going to a terminal. Escaping it here means no
    renderer has to remember to; truncating means a megabyte token cannot fill the screen.
    """
    if value is None:
        return Display("null", truncated=False, length=4)
    if isinstance(value, bool):
        text = "true" if value else "false"
        return Display(text, truncated=False, length=len(text))
    if not isinstance(value, str):
        text = str(value)
        return Display(text, truncated=False, length=len(text))

    escaped = "".join(
        character if character.isprintable() else f"\\x{ord(character):02x}" for character in value
    )
    if len(escaped) <= limit:
        return Display(f'"{escaped}"', truncated=False, length=len(value))
    return Display(f'"{escaped[:limit]}..."', truncated=True, length=len(value))
