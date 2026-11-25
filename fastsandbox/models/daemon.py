"""The daemon: health, information, settings and disk usage."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ._base import Model

__all__ = ["DaemonInfo", "DiskUsage", "DiskUsageSummary", "Health", "Setting"]


class Health(Model):
    """Health of the daemon.

    Attributes:
        status: Overall status, `healthy` when the daemon is operational.
        version: Release version, e.g. `v0.54.1`.
        api_version: Version of the daemon API, e.g. `0.52.0`.
        revision: Source revision of the release.
        release: Whether this is a release build.
    """

    status: str
    version: str
    api_version: str
    revision: str | None = None
    release: bool | None = None

    @property
    def is_healthy(self) -> bool:
        """Whether the daemon reports itself operational."""
        return self.status == "healthy"


class DaemonInfo(Model):
    """Version and build information of the daemon.

    Attributes:
        api_socket: Path of the API socket served by the daemon.
    """

    api_socket: str | None = None


class Setting(Model):
    """A daemon setting.

    Attributes:
        key: Setting key, e.g. `sandbox.disk.dockerVolume`.
        value: Effective value.
        default: Default value.
        source: Where the effective value comes from: `default`, `override`, …
        value_type: Value type: `bool`, `string`, `int`, …
        description: Human-readable description.
    """

    key: str
    value: Any = None
    default: Any = None
    source: str | None = None
    value_type: str | None = Field(default=None, alias="type")
    description: str | None = None


class DiskUsageSummary(Model):
    """Disk usage totals for one resource type.

    Attributes:
        resource_type: Resource type, e.g. `Images`, `Containers`.
        total_count: Number of resources.
        active: Number of resources in use.
        size: Total size in bytes.
        reclaimable: Size that could be reclaimed, in bytes.
    """

    resource_type: str = Field(alias="type")
    total_count: int = 0
    active: int = 0
    size: int = 0
    reclaimable: int = 0


class DiskUsage(Model):
    """Disk usage of images, containers and volumes.

    Attributes:
        summaries: Totals per resource type.
        images: Per-image details, as reported by the daemon.
        containers: Per-container details.
        volumes: Per-volume details.
    """

    summaries: list[DiskUsageSummary] = []
    images: list[Any] = []
    containers: list[Any] = []
    volumes: list[Any] = []
