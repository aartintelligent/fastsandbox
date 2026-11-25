"""Tests of the tasks against the fake daemon of fastsandbox.

The fake daemon does not run commands: `on_exec` decides what they print and
exit with, and the tests check what the task does with it.
"""

from pathlib import Path

from checks import app

from fastsandbox.models import ExecOutput
from fastsandbox.testing import FakeDaemon


async def test_check_passes(daemon: FakeDaemon, tmp_path: Path) -> None:
    daemon.on_exec(lambda sandbox, command: ExecOutput(exit_code=0, stdout="4 passed\n"))
    report = await app.run("check", repo=tmp_path)
    assert report.passed
    assert report.output == "4 passed\n"
    assert daemon.sandboxes == {}


def failing_tests(sandbox: str, command: list[str]) -> ExecOutput:
    """The checks fail; the other commands, those that prepare the copy, succeed."""
    if "pytest" in " ".join(command):
        return ExecOutput(exit_code=2, stderr="1 failed\n")
    return ExecOutput(exit_code=0)


async def test_check_reports_a_failure(daemon: FakeDaemon, tmp_path: Path) -> None:
    daemon.on_exec(failing_tests)
    report = await app.run("check", repo=tmp_path, command="pytest")
    assert not report.passed
    assert report.exit_code == 2
    assert report.output == "1 failed\n"


async def test_check_copies_the_project_and_reaches_the_package_index(
    daemon: FakeDaemon, tmp_path: Path
) -> None:
    daemon.on_exec(lambda sandbox, command: ExecOutput(exit_code=0))
    await app.run("check", repo=tmp_path)
    upload = daemon.requests_to("PUT", "/sandbox/{name}/files")[0]
    assert upload.query["path"] == "/work"
    # One rule per host, scoped to the sandbox of the run.
    assert [rule["resources"] for rule in daemon.rules] == [
        ["pypi.org"],
        ["files.pythonhosted.org"],
    ]
