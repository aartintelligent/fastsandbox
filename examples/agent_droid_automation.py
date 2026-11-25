"""Droid run unattended: one prompt, no terminal, a check that does not trust it.

The example writes a small project whose test suite fails under
`examples/target/automation/`, mounts it as the workspace of a throw-away
sandbox, runs the agent in its non-interactive mode with the prompt on the
files of the host, then runs the tests again and shows the diff and the hosts
the agent reached. A prompt given on the command line replaces the default
task. It exits with an error when the tests still fail.

The command comes from the documentation of the agent
(https://docs.factory.ai/cli/droid-exec/overview); it is the `droid` profile of
`fastsandbox.agents`, whose program and run options come from the kit itself:

    droid exec --auto high -o stream-json <prompt>

`exec` runs one prompt and exits; it is read-only by default, `--auto high`
lets it edit and run commands, and `stream-json` reports every step: the
example prints a summary of each event as it comes.

Credentials, required since nobody can log in: `FACTORY_API_KEY`, pushed as the
`droid` service secret of the sandbox. A secret stored with `sbx secret set`
serves as well.

Run it with:

    just example agent-droid-automation
    just example agent-droid-automation "Add a div operation to calc.sh, with its tests"
"""

from __future__ import annotations

from common import automation

if __name__ == "__main__":
    automation.main("droid")
