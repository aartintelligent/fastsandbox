"""Task signatures read the same, whoever evaluates their annotations.

The tasks below are compiled twice: with `from __future__ import annotations`,
which leaves every annotation a string that the framework evaluates, and
without it, as user code is often written, where Python evaluates them itself:
eagerly before 3.14, lazily from 3.14 (PEP 649). The framework must find the
same parameters, markers and schemas, and run the tasks the same way, on every
Python the package supports.
"""

from __future__ import annotations
import __future__

import sys
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from fastsandbox import Depends, FastSandbox, Task
from fastsandbox.testing import FakeDaemon

# `app` is not defined here: the test gives each module an application on the
# fake daemon before running it. The old spellings of unions (`Union`,
# `Optional`) and the quoted forward reference are deliberate.
SOURCE = """
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

from fastsandbox import Context, Depends, Mounted, Sandbox, WorkspaceDir


class Report(BaseModel):
    region: str
    seen: int
    lines: list[str] = []


type Labels = dict[str, list[int]]


def settings() -> dict[str, str]:
    return {"region": "eu"}


def counter(config: Annotated[dict[str, str], Depends(settings)]) -> Iterator[int]:
    yield len(config)


async def region(
    ctx: Context, config: Annotated[dict[str, str], Depends(settings)]
) -> AsyncIterator[str]:
    yield config["region"]


@app.task
async def inspect_repo(
    sandbox: Sandbox,
    where: Annotated[str, Depends(region)],
    seen: Annotated[int, Depends(counter, use_cache=False)],
    repo: Annotated[Path, WorkspaceDir()],
    data: Annotated[Path | None, Mounted("/data", read_only=True)] = None,
    count: Annotated[Annotated[int, Field(ge=0)], Field(le=10)] = 1,
    mode: Literal["fast", "slow"] = "fast",
    either: Union[int, str] = 0,
    lines: Optional[list[str]] = None,
    labels: Labels | None = None,
    previous: "Report | None" = None,
) -> Report:
    return Report(region=where, seen=seen, lines=lines or [])


@app.task
def count_items(items: list[tuple[int, str]], flag: bool = False) -> dict[str, int]:
    return {name: number for number, name in items if flag}


def declare_local() -> None:
    class Local(BaseModel):
        x: int

    def make() -> int:
        return 1

    @app.task
    async def local(given: Local, made: Annotated[int, Depends(make)]) -> Local:
        return Local(x=given.x + made)


declare_local()
"""

STYLES = {"stringified": __future__.annotations.compiler_flag, "evaluated": 0}


def load(app: FastSandbox, style: str, monkeypatch: pytest.MonkeyPatch) -> dict[str, Task]:
    """Runs `SOURCE` as a module compiled in `style`; the tasks it declares on `app`."""
    name = f"annotations_{style}"
    module = types.ModuleType(name)
    namespace = vars(module)
    namespace["app"] = app
    monkeypatch.setitem(sys.modules, name, module)
    # `dont_inherit`: the future import of this file must not leak into it.
    exec(compile(SOURCE, f"<{name}>", "exec", flags=STYLES[style], dont_inherit=True), namespace)
    return app.tasks


def describe(task: Task) -> dict[str, Any]:
    """What the framework read from a task: its parameters and schemas."""

    def marker(value: Any) -> Any:
        if isinstance(value, Depends):
            return ("Depends", value.dependency.__name__, value.use_cache)
        return value

    return {
        "parameters": [(p.name, p.kind, marker(p.marker)) for p in task.parameters],
        "input": task.input_model.model_json_schema(),
        "output": task.output.json_schema() if task.output is not None else None,
    }


def test_both_styles_read_the_same(
    make_app: Callable[..., FastSandbox], monkeypatch: pytest.MonkeyPatch
) -> None:
    stringified = load(make_app(), "stringified", monkeypatch)
    evaluated = load(make_app(), "evaluated", monkeypatch)
    assert sorted(stringified) == sorted(evaluated) == ["count_items", "inspect_repo", "local"]
    for name in stringified:
        assert describe(stringified[name]) == describe(evaluated[name]), name

    task = evaluated["inspect_repo"]
    assert [(p.name, p.kind) for p in task.parameters] == [
        ("sandbox", "sandbox"),
        ("where", "depends"),
        ("seen", "depends"),
        ("repo", "input"),
        ("data", "input"),
        ("count", "input"),
        ("mode", "input"),
        ("either", "input"),
        ("lines", "input"),
        ("labels", "input"),
        ("previous", "input"),
    ]
    markers = {p.name: p.marker for p in task.parameters}
    assert type(markers["repo"]).__name__ == "WorkspaceDir"
    assert (markers["data"].target, markers["data"].read_only) == ("/data", True)
    assert markers["seen"].use_cache is False
    properties = task.input_model.model_json_schema()["properties"]
    assert (properties["count"]["minimum"], properties["count"]["maximum"]) == (0, 10)
    assert properties["mode"]["enum"] == ["fast", "slow"]
    assert task.input_model.model_validate({"repo": ".", "either": "x"}).either == "x"


@pytest.mark.parametrize("style", list(STYLES))
async def test_both_styles_run_the_same(
    style: str,
    daemon: FakeDaemon,
    make_app: Callable[..., FastSandbox],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = make_app()
    load(app, style, monkeypatch)
    report = await app.run("inspect_repo", repo=tmp_path, count=3, lines=["a"])
    assert report.model_dump() == {"region": "eu", "seen": 1, "lines": ["a"]}
    assert await app.run("count_items", items=[[1, "one"]], flag=True) == {"one": 1}
    assert (await app.run("local", given={"x": 2})).x == 3
    assert daemon.sandboxes == {}
