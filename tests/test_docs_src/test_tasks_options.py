"""`docs_src/tasks/options.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

from fastsandbox.testing import FakeDaemon


async def test_options(
    fake_environment: FakeDaemon, load_example: Callable[[str], ModuleType]
) -> None:
    app = load_example("tasks/options.py").app
    assert await app.run("describe-sandbox") == {"cpus": "nproc", "stage": "STAGE"}
    task = app.get_task("describe-sandbox")
    assert task.timeout == 300
    create = fake_environment.requests_to("POST", "/sandbox")[0].json()
    assert create["name"].startswith("builds-describe-sandbox-")
    assert (create["cpus"], create["memory"]) == (2, "4g")
    assert create["environment"]["STAGE"] == "ci"
    assert [rule["resources"] for rule in fake_environment.rules] == [["pypi.org"]]
    assert fake_environment.sandboxes == {}
