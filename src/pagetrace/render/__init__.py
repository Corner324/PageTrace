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
    """A trace value made safe to emit, and the truth about what was cut.

    `value` keeps the JSON type: a numeric cursor stays a number, null stays null, and only
    strings are escaped and shortened. `text` is the terminal form, where strings are quoted so
    leading spaces and empty values are visible.
    """

    value: Scalar
    truncated: bool
    length: int

    @property
    def text(self) -> str:
        if self.value is None:
            return "null"
        if isinstance(self.value, bool):
            return "true" if self.value else "false"
        if isinstance(self.value, str):
            suffix = "..." if self.truncated else ""
            return f'"{self.value}{suffix}"'
        return str(self.value)


def display(value: Scalar, limit: int = MAX_DISPLAY_CHARS) -> Display:
    """Escape control characters and truncate, reporting the original length.

    A cursor is attacker-influenced text on its way to a terminal. Escaping it here means no
    renderer has to remember to; truncating means a megabyte token cannot fill the screen.
    """
    if not isinstance(value, str):
        return Display(value, truncated=False, length=len(str(value)))

    escaped = "".join(
        character if character.isprintable() else f"\\x{ord(character):02x}" for character in value
    )
    if len(escaped) <= limit:
        return Display(escaped, truncated=False, length=len(value))
    return Display(escaped[:limit], truncated=True, length=len(value))
