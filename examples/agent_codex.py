"""Codex in a throw-away sandbox, through the socket alone.

The kit of the agent is compiled once with the `sbx` CLI, a sandbox is created
from it, the credentials found in the environment are given to that sandbox
only, and the terminal is plugged into the agent session, opened as `sbx run`
opens it. The sandbox is deleted when the session ends.

Like `sbx run codex [PATH] [-- AGENT_ARGS...]`, the example takes the directory
the agent works on, mounted read-write at the same path, and arguments for the
agent after `--`: options added to its default command, or a prompt in its
place. Without a directory, nothing of the host is mounted: the agent works in
the filesystem of the sandbox.

Credentials: an OpenAI key in `OPENAI_API_KEY` or `CODEX_API_KEY`, pushed as
the `openai` service secret of the sandbox, which its proxy injects into
outgoing requests while the agent never sees it. A secret stored with `sbx
secret set` serves as well; without any, log in inside the session, or sign in
on the host beforehand with `sbx secret set openai --oauth`.

Run it with:

    just example agent-codex
    just example agent-codex ~/my-project
    just example agent-codex ~/my-project -- "explain this project"
"""

from __future__ import annotations

from common import agent

if __name__ == "__main__":
    agent.main("codex")
