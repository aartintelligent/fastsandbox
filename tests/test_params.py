"""The host path markers of task parameters."""

from __future__ import annotations

import io
import tarfile
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

from fastsandbox import (
    FastSandbox,
    Mounted,
    Uploaded,
    WorkspaceDir,
)
from fastsandbox.testing import FakeDaemon


async def test_markers_mount_and_upload(
    daemon: FakeDaemon, make_app: Callable[..., FastSandbox], tmp_path: Path
) -> None:
    app = make_app()
    repo, data, docs = tmp_path / "repo", tmp_path / "data", tmp_path / "docs"
    for directory in (repo, data, docs):
        directory.mkdir()
    (docs / "readme.txt").write_text("hello")

    @app.task
    async def build(
        repo: Annotated[Path, WorkspaceDir()],
        data: Annotated[Path, Mounted("/data", read_only=True)],
        docs: Annotated[Path, Uploaded("/work/docs")],
    ) -> None:
        return None

    await app.run("build", repo=repo, data=str(data), docs=docs)
    create = daemon.requests_to("POST", "/sandbox")[0].json()
    assert create["workspace"] == str(repo.resolve())
    assert create["additional_workspaces"] == [
        {"dir": str(data.resolve()), "read_only": True, "target": "/data"}
    ]
    execs = [r.json() for r in daemon.requests_to("POST", "/sandbox/{name}/exec")]
    assert execs[1]["cmd"][-2] == "/work/docs"
    assert execs[1]["user"] == "0"
    upload = daemon.requests_to("PUT", "/sandbox/{name}/files")[0]
    assert upload.query["path"] == "/work/docs"

    with tarfile.open(fileobj=io.BytesIO(upload.body)) as archive:
        assert archive.getnames() == ["readme.txt"]
