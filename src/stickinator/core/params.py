"""Base class for parameter dataclasses.

Kept in its own module so both ``core.ops`` and ``core.ai`` can use it without
an import cycle.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Params:
    """Base class for operation and settings dataclasses.

    Subclasses must be frozen dataclasses whose fields are bool, int, float,
    str, or tuples of numbers.
    """
