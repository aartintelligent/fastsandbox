"""Docker Agent run unattended: one prompt, no terminal, a check that does not trust it.

The example writes a small project whose test suite fails under
`examples/target/automation/`, mounts it as the workspace of a throw-away
sandbox, runs the agent in its non-interactive mode with the prompt on the
files of the host, then runs the tests again and shows the diff and the hosts
the agent reached. A prompt given on the command line replaces the default
task. It exits with an error when the tests still fail.

The command comes from the documentation of the agent
(https://docs.docker.com/ai/docker-agent/guides/headless/); it is the
`docker-agent` profile of `fastsandbox.agents`, whose program and run options
come from the kit itself:

    docker-agent run --yolo --exec <prompt>

`--exec` runs one prompt with the built-in default agent and exits; the run
options of the kit (`run --yolo`) approve every tool. It prints text, relayed
as it comes.

Credentials, required since nobody can log in: the key of any model provider:
`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` (or `GOOGLE_API_KEY`),
`OPENROUTER_API_KEY`, `GROQ_API_KEY`, `MISTRAL_API_KEY`, `NEBIUS_API_KEY` or
`XAI_API_KEY`, each pushed as the service secret of its provider. A secret
stored with `sbx secret set` serves as well.

Run it with:

    just example agent-docker-agent-automation
    just example agent-docker-agent-automation "Add a div operation to calc.sh, with its tests"
"""

from __future__ import annotations

from common import automation

if __name__ == "__main__":
    automation.main("docker-agent")
