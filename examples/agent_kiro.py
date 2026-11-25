"""Kiro in a throw-away sandbox, through the socket alone.

The kit of the agent is compiled once with the `sbx` CLI, a sandbox is created
from it, the credentials found in the environment are given to that sandbox
only, and the terminal is plugged into the agent session, opened as `sbx run`
opens it. The sandbox is deleted when the session ends.

Like `sbx run kiro [PATH] [-- AGENT_ARGS...]`, the example takes the directory
the agent works on, mounted read-write at the same path, and arguments for the
agent after `--`: options added to its default command, or a prompt in its
place. Without a directory, nothing of the host is mounted: the agent works in
the filesystem of the sandbox.

Credentials: none that `sbx` can inject for Kiro, which it knows no service
secret for. Sign in with the device flow the agent offers on first run, or set
`KIRO_API_KEY`, given to the agent process as is: its value is visible inside
the sandbox.

Run it with:

    just example agent-kiro
    just example agent-kiro ~/my-project
    just example agent-kiro ~/my-project -- "explain this project"
"""

from __future__ import annotations

from common import agent

if __name__ == "__main__":
    agent.main("kiro")
