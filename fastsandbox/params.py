"""Markers of task parameters: host paths and dependencies.

They go in `Annotated`: `repo: Annotated[Path, WorkspaceDir()]`,
`token: Annotated[str, Depends(get_token)]`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["Depends", "Mounted", "Uploaded", "WorkspaceDir"]


@dataclass(frozen=True)
class WorkspaceDir:
    """Marks a path parameter as the workspace of the sandbox.

    The host directory is mounted at its own path, or cloned with `clone=True`.

    Example:
        >>> async def fix(ctx: Context, repo: Annotated[Path, WorkspaceDir()]) -> None: ...

    Attributes:
        clone: The sandbox works on a private clone of the Git repository of
            the directory instead of the directory itself.

    """

    clone: bool = False


@dataclass(frozen=True)
class Mounted:
    """Marks a path parameter as a further host directory or file mounted into the sandbox.

    Attributes:
        target: Absolute path inside the sandbox; the host path when unset.
        read_only: Whether the sandbox can only read it.

    """

    target: str | None = None
    read_only: bool = False


@dataclass(frozen=True)
class Uploaded:
    """Marks a path parameter as a host directory copied into the sandbox.

    The contents of the directory are copied into `target` before the task
    runs; the copy is the sandbox's own.

    Attributes:
        target: Directory inside the sandbox.

    """

    target: str


@dataclass(frozen=True)
class Depends:
    """A dependency resolved for each run.

    The dependency is a function, sync or async, a generator or an async
    generator (its code after `yield` runs once the task ends); it can itself
    take a `Context` and other dependencies.

    Example:
        >>> async def token(ctx: Context) -> str: ...
        >>> async def task(ctx: Context, token: Annotated[str, Depends(token)]) -> None: ...

    Attributes:
        dependency: The function that provides the value.
        use_cache: Whether one value is shared by every parameter of a run
            that depends on the same function.
    """

    dependency: Callable[..., Any]
    use_cache: bool = True
