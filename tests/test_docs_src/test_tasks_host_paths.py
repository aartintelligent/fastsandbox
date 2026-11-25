"""`docs_src/tasks/host_paths.py`."""

from __future__ import annotations

import io
import tarfile
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

from fastsandbox.testing import FakeDaemon


async def test_host_paths(
    fake_environment: FakeDaemon, load_example: Callable[[str], ModuleType], tmp_path: Path
) -> None:
    repo, data, fixtures = tmp_path / "repo", tmp_path / "data", tmp_path / "fixtures"
    for directory in (repo, data, fixtures):
        directory.mkdir()
    (fixtures / "input.json").write_text("{}")

    app = load_example("tasks/host_paths.py").app
    listings = await app.run("inventory", repo=repo, data=str(data), fixtures=fixtures)
    assert listings == [str(repo.resolve()), "/data", "/work/fixtures"]
    create = fake_environment.requests_to("POST", "/sandbox")[0].json()
    assert create["workspace"] == str(repo.resolve())
    assert create["additional_workspaces"] == [
        {"dir": str(data.resolve()), "read_only": True, "target": "/data"}
    ]
    upload = fake_environment.requests_to("PUT", "/sandbox/{name}/files")[0]
    assert upload.query["path"] == "/work/fixtures"
    with tarfile.open(fileobj=io.BytesIO(upload.body)) as archive:
        assert archive.getnames() == ["input.json"]
    assert fake_environment.sandboxes == {}
