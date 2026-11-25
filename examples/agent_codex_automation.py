"""Codex run unattended: one prompt, no terminal, a check that does not trust it.

The example writes a small project whose test suite fails under
`examples/target/automation/`, mounts it as the workspace of a throw-away
sandbox, runs the agent in its non-interactive mode with the prompt on the
files of the host, then runs the tests again and shows the diff and the hosts
the agent reached. A prompt given on the command line replaces the default
task. It exits with an error when the tests still fail.

The command comes from the documentation of the agent
(https://learn.chatgpt.com/docs/non-interactive-mode); it is the `codex`
profile of `fastsandbox.agents`, whose program and run options come from the
kit itself:

    codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check --json <prompt>

`exec` runs one prompt and exits; the approvals and the sandbox of Codex are
off, since the Docker sandbox isolates it, and `--json` reports every step: the
example prints a summary of each event as it comes.

Credentials, required since nobody can log in: `OPENAI_API_KEY` or
`CODEX_API_KEY`, pushed as the `openai` service secret of the sandbox. A secret
stored with `sbx secret set` serves as well.

Run it with:

    just example agent-codex-automation
    just example agent-codex-automation "Add a div operation to calc.sh, with its tests"
"""

from __future__ import annotations

from common import automation

if __name__ == "__main__":
    automation.main("codex")
