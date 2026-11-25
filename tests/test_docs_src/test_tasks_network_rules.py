"""`docs_src/tasks/network_rules.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

from fastsandbox.testing import FakeDaemon


async def test_network_rules(
    fake_environment: FakeDaemon, load_example: Callable[[str], ModuleType]
) -> None:
    app = load_example("tasks/network_rules.py").app
    await app.run("probe", url="https://pypi.org")
    applied = fake_environment.requests_to("POST", "/policy/network/rules")[0].json()["actions"]
    assert [(change["action"], change["resources"]) for change in applied] == [
        ("allow", ["pypi.org", "files.pythonhosted.org"]),
        ("http-allow", ["api.github.com"]),
        ("deny", ["example.org"]),
    ]
    assert applied[1]["methods"] == ["GET"]
    sandbox = fake_environment.requests_to("POST", "/sandbox")[0].json()["name"]
    assert {change["sandbox_id"] for change in applied} == {sandbox}
    assert fake_environment.sandboxes == {}
