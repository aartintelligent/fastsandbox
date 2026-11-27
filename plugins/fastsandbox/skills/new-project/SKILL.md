---
name: new-project
description: Scaffolds a new Python project that uses fastsandbox - an application of coding agents, an application of tasks run in throw-away sandboxes, or a tool built on the client - with a pyproject for Python 3.12 or newer, the code, tests that run without a daemon, and a README. Use when the user wants to start a project with fastsandbox.
argument-hint: "[directory] [agent | tasks | client]"
disable-model-invocation: true
---

# New fastsandbox project

Arguments given: `$ARGUMENTS` (a directory and a kind, both optional).

## 1. Understand what the project is for

Unless the arguments already say it, ask the user, in one short round of
questions:

- **The kind of project**:
  - `agent`: a coding agent works on a repository in a sandbox (Claude Code,
    Codex, Copilot, Cursor, Devin, Docker Agent, Droid, Kiro or OpenCode);
  - `tasks`: jobs run in throw-away sandboxes with validated inputs and
    results (tests, builds, scripts);
  - `client`: a tool that drives sandboxes directly (create, commands, files,
    policy, images, events...).
- For `agent`: which agent; whether it may change the repository in place or
  works on a private clone (recommend the clone); what comes back (a patch, a
  file, a report); which hosts it needs besides its own service.
- For `tasks`: what runs in the sandbox, on which files, with which hosts.
- The directory and the project name (default: the kind's template name).

## 2. Check the machine, quickly

Run `sbx version`. If the command is missing or fails, tell the user that
Docker Sandboxes must be installed and running for fastsandbox to do anything
(https://docs.docker.com/ai/sandboxes/), and that `/fastsandbox:doctor` checks
the rest; go on with the scaffolding anyway, since the tests need no daemon.

## 3. Copy the template

The templates are in `${CLAUDE_SKILL_DIR}/templates/`:

| Kind | Template | Main module | Test |
|---|---|---|---|
| `agent` | `templates/agent/` | `agents.py`: `fix`, Claude Code on a clone, the tests decide, the commits come back as a patch | the declaration of the task |
| `tasks` | `templates/tasks/` | `checks.py`: `check`, a command run on a copy of the project | runs against the fake daemon |
| `client` | `templates/client/` | `probe.py`: a sandbox created, asked for its system, deleted | runs against the fake daemon |

Copy the whole template directory, hidden files included, into the target
directory (never over existing files without asking). Then adapt it to what
the user described:

- rename the project in `pyproject.toml`, the application
  (`FastSandbox("...")`) and the README;
- change the agent, the prompt, the result model, the command or the network
  rules as asked; load the `agents`, `tasks` or `client` skill of this plugin
  for the API and its rules, and keep the safe defaults (a clone or an upload,
  `Network` rules, a timeout, the result checked in the sandbox);
- keep the tests in step with the code: a test per task, against the fake
  daemon (`testing` skill).

Never write a secret into a file: the README names the environment variable of
the agent's key, the user exports it.

## 4. Install and test

In the project directory:

```sh
uv sync
uv run pytest
```

The tests use the fake daemon of `fastsandbox.testing`: no sandbox is created.
Fix the code until they pass.

## 5. Hand over

Tell the user how to run the project for real, from its README: export the
key (the kit is forged without the `sbx` CLI on the first run), run the
task with `uv run fastsandbox run ...` or `uv run python probe.py`. Do not run
it yourself without asking: it creates real sandboxes on their daemon. Suggest
the `fastsandbox:sandbox-reviewer` agent once they change the code.
