from pathlib import Path

from fastsandbox import Context, FastSandbox
from fastsandbox.models import ExecOutput
from fastsandbox.testing import FakeDaemon, fake_package


async def test_word_count(tmp_path: Path) -> None:
    async with FakeDaemon() as daemon:
        daemon.on_exec(lambda sandbox, cmd: ExecOutput(exit_code=0, stdout="3\n"))
        app = FastSandbox(socket=str(daemon.socket_path), kit=fake_package(tmp_path / "kit"))

        @app.task
        async def count_words(ctx: Context, text: str) -> int:
            output = await ctx.sandbox.exec(f"echo {text!r} | wc -w", check=True)
            return int(output.stdout)

        assert await app.run("count_words", text="one two three") == 3
        assert daemon.sandboxes == {}
