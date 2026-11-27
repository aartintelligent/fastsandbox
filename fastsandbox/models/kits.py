"""Kit packages."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["PackageImage"]


class PackageImage(BaseModel):
    """An image archive of a kit package.

    Attributes:
        path: Path of the archive, `None` for an archive held in memory, as those of a
            package forged in memory are.
        reference: Reference the archive loads as, when known.
    """

    path: str | None = None
    reference: str | None = None
