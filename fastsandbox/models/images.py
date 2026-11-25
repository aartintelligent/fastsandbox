"""The images of the daemon and the progress of their pulls."""

from __future__ import annotations

from pydantic import Field

from ._base import Model

__all__ = ["ImageInspect", "ImageSummary", "LocalImageMetadata", "ProgressDetail", "PullProgress"]


class ImageSummary(Model):
    """An image of the daemon.

    Attributes:
        repository: Repository, e.g. `docker.io/library/sandbox-kit-assembled`.
        tag: Tag, absent for images only referenced by digest.
        id: Image identifier (`sha256:…`).
        digest: Content digest (`sha256:…`).
        size: Size in bytes.
        created_at: Creation time (RFC 3339).
        agent: Agent of the kit the image belongs to, when known.
    """

    repository: str
    tag: str | None = None
    id: str
    digest: str | None = None
    size: int | None = None
    created_at: str | None = None
    agent: str | None = None

    @property
    def reference(self) -> str:
        """`repository:tag`, else `repository@digest`, else `repository@id`."""
        if self.tag:
            return f"{self.repository}:{self.tag}"
        if self.digest is not None:
            return f"{self.repository}@{self.digest}"
        return f"{self.repository}@{self.id}"


class ImageInspect(Model):
    """Details of an image.

    Attributes:
        id: Image identifier (`sha256:…`).
        agent: Agent of the kit the image belongs to, when known.
        cmd: Default command.
        entrypoint: Entrypoint.
        user: Default user.
        created_at: Creation time (RFC 3339).
    """

    id: str
    agent: str | None = None
    cmd: list[str] = []
    entrypoint: list[str] = []
    user: str | None = None
    created_at: str | None = None


class LocalImageMetadata(Model):
    """Local metadata of an image.

    Attributes:
        local_snapshot: Whether the image is a locally saved snapshot.
    """

    local_snapshot: bool = False


class ProgressDetail(Model):
    """Byte counts of a layer being pulled.

    Attributes:
        current: Bytes transferred so far.
        total: Size of the layer.
    """

    current: int | None = None
    total: int | None = None


class PullProgress(Model):
    """One line of the progress of an image pull.

    Attributes:
        id: Layer the line refers to, when it refers to one.
        status: What happens, e.g. `Downloading`.
        progress_detail: Byte counts of the layer.
        error: Failure of the pull, always the last line of a failed stream.
    """

    id: str | None = None
    status: str | None = None
    progress_detail: ProgressDetail | None = Field(default=None, alias="progressDetail")
    error: str | None = None
