"""The collection of sandboxes: list, look up, create."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from .models import Created, CreateEvent, CreateRequest, SandboxInfo, wire
from .streams import Stream

if TYPE_CHECKING:
    from . import _native
    from .client import Client

__all__ = ["Sandboxes"]

_SANDBOXES = TypeAdapter(list[SandboxInfo])


_CREATE_EVENT: TypeAdapter[CreateEvent] = TypeAdapter(CreateEvent)


class Sandboxes:
    """The collection of sandboxes."""

    def __init__(self, native: _native.Sandboxes, client: Client) -> None:
        self._native = native
        self._client = client

    async def list(self) -> list[SandboxInfo]:
        """Every sandbox."""
        return _SANDBOXES.validate_python(await self._native.list())

    async def get(self, name: str) -> SandboxInfo:
        """The sandbox `name`.

        Raises:
            NotFoundError: When there is none.
        """
        return SandboxInfo.model_validate(await self._native.get(name))

    async def find(self, name: str) -> SandboxInfo | None:
        """The sandbox `name`, or `None`."""
        found = await self._native.find(name)
        return SandboxInfo.model_validate(found) if found is not None else None

    async def create(self, request: CreateRequest) -> Created:
        """Creates a sandbox from a request and waits for the result.

        The kit images must already be loaded (see `KitPackage.create_with`).
        """
        return Created.model_validate(await self._native.create(wire(request)))

    async def create_stream(self, request: CreateRequest) -> Stream[CreateEvent]:
        """Creates a sandbox, streaming its progress."""
        native = await self._native.create_stream(wire(request))
        return Stream(native, _CREATE_EVENT.validate_python)
