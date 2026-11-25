"""Cursor in a throw-away sandbox, with the MCP server of the examples.

The example registers itself as a local MCP server (`sbx mcp add`), checks it
against the MCP policy of the daemon, loads it into the gateway of the sandbox,
calls its `sum` tool from inside the sandbox, then starts the agent session:
ask the agent to call the `sum`, `echo` or `host_time` tool. The sandbox and
the registration are removed when the session ends. When `sbx` starts this
script as the MCP server, it serves MCP on its standard input and output
instead of running the example.

It takes the arguments of `agent-cursor`: the directory the agent works on,
mounted read-write at the same path, and arguments for the agent after `--`.

Credentials: a Cursor key in `CURSOR_API_KEY`, pushed as the `cursor` service
secret of the sandbox, which its proxy injects into outgoing requests while the
agent never sees it. A secret stored with `sbx secret set` serves as well;
without any, log in inside the session.

Run it with:

    just example agent-cursor-mcp
    just example agent-cursor-mcp ~/my-project
    just example agent-cursor-mcp ~/my-project -- "explain this project"
"""

from __future__ import annotations

from common import agent

if __name__ == "__main__":
    agent.main("cursor", with_mcp=True)
