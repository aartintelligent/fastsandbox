"""`docs_src/tasks/inputs_outputs.py`."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

import pytest
from pydantic import ValidationError

from fastsandbox.models import ExecOutput
from fastsandbox.testing import FakeDaemon


async def test_inputs_outputs(
    fake_environment: FakeDaemon, load_example: Callable[[str], ModuleType]
) -> None:
    module = load_example("tasks/inputs_outputs.py")
    fake_environment.on_exec(
        lambda sandbox, cmd: ExecOutput(exit_code=0, stdout=" 4  8 /tmp/input.txt\n")
    )
    count = await module.app.run("count", text="one two\nthree four\n", repeat="2", tags=["a"])
    assert count == module.Count(lines=4, words=8, tags=["a"])
    upload = fake_environment.requests_to("PUT", "/sandbox/{name}/files")[0]
    assert upload.query["path"] == "/tmp"

    requests = len(fake_environment.requests)
    with pytest.raises(ValidationError):
        await module.app.run("count", text="x", repeat=0)
    with pytest.raises(ValidationError):
        await module.app.run("count", text="x", colour="blue")
    # Invalid inputs fail before any sandbox is created.
    assert len(fake_environment.requests) == requests

    task = module.app.get_task("count")
    assert task.input_schema["required"] == ["text"]
    assert task.output_schema is not None
    assert set(task.output_schema["properties"]) == {"lines", "words", "tags"}
