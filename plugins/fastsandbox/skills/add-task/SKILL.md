---
name: add-task
description: Adds a task or an agent task to an existing fastsandbox application, with its test against the fake daemon - from a description of what it should do. Use when the user wants a new job in a sandbox, or a new coding agent task, in a project that already uses FastSandbox.
argument-hint: "[what the task should do]"
disable-model-invocation: true
---

# Add a task

What the task should do: `$ARGUMENTS`. If that is empty or vague, ask what
runs in the sandbox, on which files, with which hosts, and what comes back.

## 1. Find the application

The application is the module named by `[tool.fastsandbox] app` in
`pyproject.toml`, else `app.py`, else `main.py`; it holds a `FastSandbox`
instance. Read it, and its tests, to follow their style. No application yet:
suggest `/fastsandbox:new-project` instead.

## 2. Choose the kind of task

- **A coding agent does the work** (fixes, reviews, writes code): an agent
  task, `@app.agent("<agent>", ...)`. Load the `agents` skill of this plugin.
- **A command, a build, a script, a check**: a task, `@app.task(...)`. Load the
  `tasks` skill.
- **Something the task does inside its sandbox** (commands, files, ports,
  network): `ctx.sandbox` is a client `Sandbox`; the `client` skill has its
  API.

## 3. Write it

Follow the rules of those skills, and in particular:

- the inputs are the parameters, typed; the result is a typed return
  annotation, a Pydantic model for anything structured;
- host directories come in through a marker: `Uploaded(...)` or
  `WorkspaceDir(clone=True)` unless the task must change the host;
- a `timeout`, and `Network` rules for anything unattended;
- for an agent, the result is checked in the sandbox (tests, a build), and the
  work leaves as a patch, a file or a report;
- a docstring: it is the description `fastsandbox tasks` shows.

## 4. Test it

Add its test next to the others (`testing` skill):

- a task: run it with `app.run(...)` against the fake daemon, `on_exec`
  deciding what its commands print, and assert on the result, the requests
  the daemon received and `daemon.sandboxes == {}`;
- an agent task: an agent run needs the real daemon, so assert on what the
  task declares (its agent, its network rules, its markers, its inputs and
  result schemas).

Run the tests (`uv run pytest`) until they pass.

## 5. Hand over

Show the command that runs the new task for real
(`uv run fastsandbox run <task> --<input> ...`; `fastsandbox tasks` lists the
options), and do not run it without asking: it creates a real sandbox.
Suggest the `fastsandbox:sandbox-reviewer` agent on the change.
