"""Kiro run unattended: one prompt, no terminal, a check that does not trust it.

The example writes a small project whose test suite fails under
`examples/target/automation/`, mounts it as the workspace of a throw-away
sandbox, runs the agent in its non-interactive mode with the prompt on the
files of the host, then runs the tests again and shows the diff and the hosts
the agent reached. A prompt given on the command line replaces the default
task. It exits with an error when the tests still fail.

The command comes from the documentation of the agent
(https://kiro.dev/docs/cli/headless); it is the `kiro` profile of
`fastsandbox.agents`, whose program and run options come from the kit itself:

    kiro chat --trust-all-tools --no-interactive <prompt>

`--no-interactive` runs one prompt and exits; the run options of the kit (`chat
--trust-all-tools`) let it use every tool. It prints text, relayed as it comes.

Credentials, required since nobody can log in: `KIRO_API_KEY` (paid plans),
given to the agent process as is: `sbx` knows no service secret for Kiro, so
the key is visible inside the sandbox.

Run it with:

    just example agent-kiro-automation
    just example agent-kiro-automation "Add a div operation to calc.sh, with its tests"
"""

from __future__ import annotations

from common import automation

if __name__ == "__main__":
    automation.main("kiro")
