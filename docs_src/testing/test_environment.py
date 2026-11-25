from pathlib import Path

import pytest

import fastsandbox
from fastsandbox import Context, FastSandbox, Kit
from fastsandbox.models import ExecOutput
from fastsandbox.testing import FakeDaemon, fake_package

app = FastSandbox("ci")


@app.task(kit="shell")
async def python_version(ctx: Context) -> str:
    output = await ctx.sandbox.exec(["python3", "--version"], check=True)
    return output.stdout.strip()


async def test_python_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async with FakeDaemon() as daemon:
        kits = tmp_path / "kits"
        fake_package(kits / Kit(base="shell").cache_key)
        monkeypatch.setenv(fastsandbox.SOCKET_ENV, str(daemon.socket_path))
        monkeypatch.setenv("FASTSANDBOX_KIT_CACHE", str(kits))
        daemon.on_exec(lambda sandbox, cmd: ExecOutput(exit_code=0, stdout="Python 3.12.3\n"))

        assert await app.run("python_version") == "Python 3.12.3"
        assert daemon.sandboxes == {}
