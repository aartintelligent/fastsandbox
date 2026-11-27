from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from fastsandbox import SOCKET_ENV, Kit
from fastsandbox.cli import main
from fastsandbox.models import ExecOutput
from fastsandbox.testing import FakeDaemon, fake_package

APP = """
from pathlib import Path
from pydantic import BaseModel
from fastsandbox import Context, FastSandbox, KitPackage

app = FastSandbox("cli", socket={socket!r}, kit=KitPackage.open({package!r}))

class Result(BaseModel):
    echoed: str
    times: int

@app.task
async def echo(ctx: Context, text: str, times: int = 1, loud: bool = False) -> Result:
    \"\"\"Echoes text in a sandbox.\"\"\"
    out = await ctx.sandbox.exec(["echo", text])
    value = out.stdout.strip() * times
    return Result(echoed=value.upper() if loud else value, times=times)
"""


@pytest.fixture
def threaded_daemon() -> Iterator[FakeDaemon]:
    """A fake daemon serving from its own thread, for the synchronous CLI."""
    loop = asyncio.new_event_loop()
    daemon = FakeDaemon()
    daemon.on_exec(lambda sandbox, cmd: ExecOutput(exit_code=0, stdout=cmd[-1] + "\n"))
    ready = threading.Event()

    def serve() -> None:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(daemon.start())
        ready.set()
        loop.run_forever()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    ready.wait(5)
    yield daemon
    asyncio.run_coroutine_threadsafe(daemon.stop(), loop).result(5)
    loop.call_soon_threadsafe(loop.stop)
    thread.join(5)


@pytest.fixture
def app_file(tmp_path: Path, threaded_daemon: FakeDaemon) -> Path:
    package = fake_package(tmp_path / "pkg")
    path = tmp_path / "app.py"
    path.write_text(APP.format(socket=str(threaded_daemon.socket_path), package=str(package.dir)))
    return path


def test_tasks_lists_the_inputs(app_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["tasks", str(app_file)]) == 0
    out = capsys.readouterr().out
    assert "echo  (task" in out
    assert "Echoes text in a sandbox." in out
    assert "--text  str, required" in out
    assert "--times  int, default 1" in out


def test_run_prints_the_result(
    app_file: Path, threaded_daemon: FakeDaemon, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["run", f"{app_file}:app", "echo", "--text", "hi", "--times", "2", "--loud"]) == 0
    assert json.loads(capsys.readouterr().out) == {"echoed": "HIHI", "times": 2}
    assert threaded_daemon.sandboxes == {}


def test_run_takes_one_json_input(app_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", str(app_file), "echo", "--input", '{"text": "yo"}']) == 0
    assert json.loads(capsys.readouterr().out)["echoed"] == "yo"


def test_unknown_tasks_fail_cleanly(app_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", str(app_file), "nope"]) == 1
    assert "unknown task 'nope'" in capsys.readouterr().err


def test_info_describes_the_daemon(
    threaded_daemon: FakeDaemon, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(SOCKET_ENV, str(threaded_daemon.socket_path))
    monkeypatch.delenv("FASTSANDBOX_KIT_CACHE", raising=False)
    assert main(["info"]) == 0
    out = capsys.readouterr().out
    assert f"socket       {threaded_daemon.socket_path}" in out
    assert "sandboxes    0" in out
    assert "kit cache    memory, kits forged without the sbx CLI" in out


def test_kits_compile_compiles_with_the_cli_into_the_cache(
    threaded_daemon: FakeDaemon,
    compiled: list[dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(SOCKET_ENV, str(threaded_daemon.socket_path))
    monkeypatch.setenv("FASTSANDBOX_KIT_CACHE", str(tmp_path))
    command = ["kits", "compile", "shell", "--mixin", "./kits/tools", "--arg", "model=fast"]
    assert main(command) == 0
    kit = Kit(base="shell", mixins=("./kits/tools",), args={"model": "fast"})
    assert capsys.readouterr().out == f"{kit.label}: {tmp_path / kit.cache_key}\n"
    assert [(call["sbx"], call["args"]) for call in compiled] == [("sbx", {"model": "fast"})]
