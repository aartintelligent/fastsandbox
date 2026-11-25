"""The images of the daemon."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from .models import ImageInspect, ImageSummary, LocalImageMetadata, PullProgress
from .streams import Stream

if TYPE_CHECKING:
    from . import _native

__all__ = ["Images"]

_IMAGES = TypeAdapter(list[ImageSummary])


class Images:
    """The images of the daemon."""

    def __init__(self, native: _native.Images) -> None:
        self._native = native

    async def list(self) -> list[ImageSummary]:
        """Every image, untagged ones included."""
        return _IMAGES.validate_python(await self._native.list())

    async def inspect(self, reference: str) -> ImageInspect:
        """The details of `reference`."""
        return ImageInspect.model_validate(await self._native.inspect(reference))

    async def exists(self, reference: str) -> bool:
        """Whether `reference` is present."""
        return await self._native.exists(reference)

    async def local_metadata(self, reference: str) -> LocalImageMetadata:
        """The local metadata of `reference`."""
        return LocalImageMetadata.model_validate(await self._native.local_metadata(reference))

    async def pull(self, reference: str) -> None:
        """Pulls `reference` and waits for the end of the pull."""
        await self._native.pull(reference)

    async def pull_stream(self, reference: str) -> Stream[PullProgress]:
        """Pulls `reference`, streaming its progress."""
        return Stream(await self._native.pull_stream(reference), PullProgress.model_validate)

    async def load(self, archive: bytes) -> None:
        """Loads an image archive (`docker save` format)."""
        await self._native.load(archive)

    async def load_file(self, path: str | os.PathLike[str]) -> None:
        """Loads an image archive from a file of the host."""
        await self._native.load_file(os.fspath(path))

    async def export(self, reference: str) -> bytes:
        """Exports `reference` as an image archive."""
        return await self._native.export(reference)

    async def remove(self, reference: str) -> None:
        """Removes `reference`."""
        await self._native.remove(reference)
