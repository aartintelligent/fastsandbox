"""Kit packages."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["PackageImage"]


class PackageImage(BaseModel):
    """An image archive of a kit package.

    Attributes:
        path: Path of the archive.
        reference: Reference the archive loads as, when known.
    """

    path: str
    reference: str | None = None
