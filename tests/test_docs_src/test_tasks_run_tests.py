"""`docs_src/tasks/run_tests.py`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType

from fastsandbox.testing import FakeDaemon


async def test_run_tests(
    fake_environment: FakeDaemon, load_example: Callable[[str], ModuleType], tmp_path: Path
) -> None:
    (tmp_path / "Makefile").write_text("test:\n\ttrue\n")
    app = load_example("tasks/run_tests.py").app
    report = await app.run("run_tests", repo=tmp_path)
    assert report.passed
    assert report.summary == "cd /work && make test\n"
    upload = fake_environment.requests_to("PUT", "/sandbox/{name}/files")[0]
    assert upload.query["path"] == "/work"
    assert [rule["resources"] for rule in fake_environment.rules] == [["pypi.org"]]
    assert fake_environment.sandboxes == {}
