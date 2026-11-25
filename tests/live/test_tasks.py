"""A task of an application, against the daemon."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastsandbox import (
    Context,
    FastSandbox,
    Network,
    Uploaded,
)


async def test_a_task_of_an_application(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "data.txt").write_text("one\ntwo\nthree\n")
    app = FastSandbox("live")

    @app.task(kit="shell", network=Network.deny("example.org"), timeout="5m")
    async def count_lines(ctx: Context, project: Annotated[Path, Uploaded("/work")]) -> int:
        output = await ctx.sandbox.exec("wc -l < /work/data.txt", check=True)
        return int(output.stdout.strip())

    assert await app.run("count_lines", project=project) == 3
