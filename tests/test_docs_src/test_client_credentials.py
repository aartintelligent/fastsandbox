"""`docs_src/client/credentials.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest

from fastsandbox.testing import FakeDaemon


async def test_credentials(
    fake_environment: FakeDaemon,
    load_example: Callable[[str], ModuleType],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EXAMPLE_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    await load_example("client/credentials.py").main()
    assert capsys.readouterr().out == "as a log prints it: **********\nrecorded: []\n"
    # The first update is the empty one of `running()`.
    updates = [
        r.json() for r in fake_environment.requests_to("POST", "/sandbox/{name}/credentials")
    ][1:]
    secret = updates[0]["custom_secrets"][0]
    assert (secret["sentinel"], secret["targets"], secret["value"]) == (
        "example-placeholder",
        ["api.example.com"],
        "dummy-token",
    )
    assert updates[1]["credential_values"] == [{"service": "github", "value": "dummy"}]
    assert updates[-1]["custom_secrets"] == []
    assert fake_environment.sandboxes == {}
