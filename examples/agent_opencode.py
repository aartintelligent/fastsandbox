"""OpenCode in a throw-away sandbox, through the socket alone.

The kit of the agent is forged without the `sbx` CLI, a sandbox is created
from it, the credentials found in the environment are given to that sandbox
only, and the terminal is plugged into the agent session, opened as `sbx run`
opens it. The sandbox is deleted when the session ends.

Like `sbx run opencode [PATH] [-- AGENT_ARGS...]`, the example takes the
directory the agent works on, mounted read-write at the same path, and
arguments for the agent after `--`: options added to its default command, or a
prompt in its place. Without a directory, nothing of the host is mounted: the
agent works in the filesystem of the sandbox.

Credentials: the key of any model provider: `ANTHROPIC_API_KEY`,
`OPENAI_API_KEY`, `GEMINI_API_KEY` (or `GOOGLE_API_KEY`), `OPENROUTER_API_KEY`,
`GROQ_API_KEY`, `MISTRAL_API_KEY`, `NEBIUS_API_KEY` or `XAI_API_KEY`, each
pushed as the service secret of its provider, which its proxy injects into
outgoing requests while the agent never sees it. A secret stored with `sbx
secret set` serves as well; without any, log in inside the session.

Run it with:

    just example agent-opencode
    just example agent-opencode ~/my-project
    just example agent-opencode ~/my-project -- "explain this project"
"""

from __future__ import annotations

from common import agent

if __name__ == "__main__":
    agent.main("opencode")
