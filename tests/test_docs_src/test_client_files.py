"""`docs_src/client/files.py`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

from fastsandbox.testing import FakeDaemon


async def test_files(
    fake_environment: FakeDaemon,
    load_example: Callable[[str], ModuleType],
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "main.py").write_text("print('hi')\n")

    await load_example("client/files.py").main(project)
    assert capsys.readouterr().out == 'level = "debug"\n'
    uploads = [
        r.query["path"] for r in fake_environment.requests_to("PUT", "/sandbox/{name}/files")
    ]
    assert uploads == ["/tmp", "/tmp", "/work"]
    copied = tmp_path / "results" / "project" / "src" / "main.py"
    assert copied.read_text() == "print('hi')\n"
    assert fake_environment.sandboxes == {}
