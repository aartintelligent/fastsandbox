"""The daemon itself: health, information, settings, log levels and disk usage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter

from .models import DaemonInfo, DiskUsage, Health, Setting

if TYPE_CHECKING:
    from . import _native

__all__ = ["Daemon"]

_SETTINGS = TypeAdapter(list[Setting])


class Daemon:
    """The daemon: health, information, settings, log levels and disk usage."""

    def __init__(self, native: _native.Daemon) -> None:
        self._native = native

    async def health(self) -> Health:
        """The current health of the daemon."""
        return Health.model_validate(await self._native.health())

    async def info(self) -> DaemonInfo:
        """Version and build information."""
        return DaemonInfo.model_validate(await self._native.info())

    async def settings(self) -> list[Setting]:
        """Every setting with its value."""
        return _SETTINGS.validate_python(await self._native.settings())

    async def setting(self, key: str) -> Setting:
        """The setting `key`."""
        return Setting.model_validate(await self._native.setting(key))

    async def set_setting(self, key: str, value: Any) -> Setting:
        """Sets `key` to `value`, any JSON value."""
        return Setting.model_validate(await self._native.set_setting(key, value))

    async def unset_setting(self, key: str) -> None:
        """Resets `key` to its default."""
        await self._native.unset_setting(key)

    async def log_levels(self) -> dict[str, str]:
        """The log level of every target."""
        return await self._native.log_levels()

    async def set_log_level(self, target: str, level: str) -> None:
        """Sets the log level of `target`."""
        await self._native.set_log_level(target, level)

    async def disk_usage(self) -> DiskUsage:
        """Disk usage of images, containers and volumes."""
        return DiskUsage.model_validate(await self._native.disk_usage())

    async def debug_state(self) -> Any:
        """The internal state the daemon reports for debugging."""
        return await self._native.debug_state()

    async def diagnostics(self) -> Any:
        """The diagnostics the daemon collects."""
        return await self._native.diagnostics()
