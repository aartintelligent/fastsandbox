"""Commands in a shell sandbox, from a plain program to the agent of the kit.

The example shows outputs and exit codes, `check`, users, working directory
and environment, per-command deadlines, standard input, an execution followed
by its identifier, and the agent of the kit run without a terminal.

Run it with:

    just example shell-exec
"""

from __future__ import annotations

import common
import fastsandbox
from common import kit
from fastsandbox import CommandFailedError, NotFoundError, SandboxTimeoutError

EXIT_TIMEOUT = 10.0
"""How long an interactive execution is given to report its exit code, in seconds."""


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    package = await kit.package(client, "shell")
    async with (
        client.create(fastsandbox.unique_name("example-exec"), kit=package) as sandbox,
        sandbox.running(),
    ):
        # A program and its arguments, not interpreted by a shell.
        whoami = await sandbox.exec(["id", "-un"], check=True)
        print(f"default user: {whoami.stdout.strip()}")

        # A shell script, as root, in a working directory, with a variable.
        script = await sandbox.exec(
            'echo "$GREETING from $(pwd) as $(id -un)"',
            user="0",
            working_dir="/tmp",
            env={"GREETING": "hello"},
            check=True,
        )
        print(script.stdout, end="")

        # A non-zero exit code is an output; `check` turns it into an error
        # that keeps the outputs.
        failing = await sandbox.exec("echo failing >&2; exit 3")
        print(f"exit code {failing.exit_code}")
        try:
            failing.check()
        except CommandFailedError as error:
            print(f"checked: code {error.exit_code}, stderr {error.stderr.strip()!r}")

        # A missing program is not an error either: it exits with 127.
        missing = await sandbox.exec(["no-such-program"])
        print(f"missing program: exit code {missing.exit_code}")

        # A command can have its own deadline, shorter than the client's.
        try:
            await sandbox.exec(["sleep", "10"], timeout=1)
        except SandboxTimeoutError as error:
            print(f"deadline: {error}")
        else:
            print("unexpected: the command ended before its deadline")

        # An interactive execution reads standard input.
        counted = await (await sandbox.attach(["wc", "-l"])).collect(
            "one\ntwo\nthree\n", exit_timeout=EXIT_TIMEOUT
        )
        print(f"wc -l read {counted.stdout.decode().strip()} lines")

        # An execution followed by its identifier, as a program that hands it
        # to another task, or polls it, does.
        session = await sandbox.attach("sleep 1; exit 3")
        short = session.id[:12]
        state = await sandbox.exec_inspect(session.id)
        print(f"execution {short}: running {state.running}")
        code = await session.wait(EXIT_TIMEOUT)
        print(f"execution {short}: ended with exit code {code}")
        # Once the daemon has reported its end, it forgets the execution.
        try:
            state = await sandbox.exec_inspect(session.id)
        except NotFoundError:
            print(f"execution {short}: forgotten by the daemon once ended")
        else:
            print(f"execution {short}: still known, running {state.running}")

        # The agent of the kit, bash for `shell`, in a session without a
        # terminal: its standard output and error come apart, as an unattended
        # program needs them.
        agent = await (
            await sandbox.agent_session(["-c", "echo out; echo err >&2"], tty=False)
        ).collect("", exit_timeout=EXIT_TIMEOUT)
        print(
            f"agent session without a terminal: stdout {agent.stdout.decode()!r}, "
            f"stderr {agent.stderr.decode()!r}"
        )


if __name__ == "__main__":
    common.main(main)
