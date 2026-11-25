"""Files moved in and out of a sandbox."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

import fastsandbox
from fastsandbox.testing import FakeDaemon


async def test_files_round_trip(
    client: fastsandbox.Client, daemon: FakeDaemon, package: fastsandbox.KitPackage
) -> None:
    async with client.create("files", kit=package) as sandbox:
        await sandbox.write_file("/tmp/notes.txt", "dummy notes\n", mode=0o600)
        assert await sandbox.read_text("/tmp/notes.txt") == "dummy notes\n"
    assert daemon.files == {}
    assert daemon.requests_to("PUT", "/sandbox/{name}/files")[0].query["path"] == "/tmp"


async def test_directories_keep_their_name(
    client: fastsandbox.Client,
    daemon: FakeDaemon,
    package: fastsandbox.KitPackage,
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "main.py").write_text("print('hi')\n")
    copy = tmp_path / "copy"
    copy.mkdir()
    async with client.create("dirs", kit=package) as sandbox:
        await sandbox.upload_dir(project, "/work")
        assert ("dirs", "/work/project/src/main.py") in daemon.files
        archive = await sandbox.download_archive("/work/project")
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            assert tar.getnames() == ["project/src/main.py"]
        await sandbox.download_dir("/work/project", copy)
    assert (copy / "project" / "src" / "main.py").read_text() == "print('hi')\n"
