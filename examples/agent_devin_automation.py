"""Devin run unattended: one prompt, no terminal, a check that does not trust it.

The example writes a small project whose test suite fails under
`examples/target/automation/`, mounts it as the workspace of a throw-away
sandbox, runs the agent in its non-interactive mode with the prompt on the
files of the host, then runs the tests again and shows the diff and the hosts
the agent reached. A prompt given on the command line replaces the default
task. It exits with an error when the tests still fail.

The command comes from the documentation of the agent
(https://docs.devin.ai/cli/reference/commands); it is the `devin` profile of
`fastsandbox.agents`, whose program and run options come from the kit itself:

    devin --permission-mode dangerous --respect-workspace-trust=false -p <prompt>

`-p` runs one prompt and exits; the run options of the kit (`--permission-mode
dangerous --respect-workspace-trust=false`) let it act without approval in this
directory. It prints text, relayed as it comes.

Credentials, required since nobody can log in: `DEVIN_API_KEY`, pushed as the
`devin` service secret of the sandbox. A secret stored with `sbx secret set`
serves as well.

Run it with:

    just example agent-devin-automation
    just example agent-devin-automation "Add a div operation to calc.sh, with its tests"
"""

from __future__ import annotations

from common import automation

if __name__ == "__main__":
    automation.main("devin")
