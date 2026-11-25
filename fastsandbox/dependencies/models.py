"""How each parameter of a task or a dependency is filled."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["Parameter"]


@dataclass(frozen=True)
class Parameter:
    """A parameter of a task function and how it is filled.

    Attributes:
        name: The name of the parameter.
        kind: `input` (validated from the arguments), `context`, `sandbox`,
            `client`, `agent` or `depends`.
        annotation: The type of the value, without its markers.
        marker: The marker of an input (`WorkspaceDir`, `Mounted`,
            `Uploaded`), or the `Depends` of a dependency.
    """

    name: str
    kind: str
    annotation: Any
    marker: Any = None
