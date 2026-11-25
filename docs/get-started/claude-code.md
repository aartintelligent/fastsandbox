# With Claude Code

fastsandbox comes with a plugin for [Claude Code](https://code.claude.com/docs).
It teaches Claude the whole library (the client, tasks, agent tasks, tests and
troubleshooting) and adds commands that set up a project, check the machine
and add tasks. Install it, then describe what you want to build.

## Install the plugin

In Claude Code:

```text
/plugin install fastsandbox --marketplace aartintelligent/fastsandbox
```

or, in two steps:

```text
/plugin marketplace add aartintelligent/fastsandbox
/plugin install fastsandbox@fastsandbox
```

The plugin does not install Docker Sandboxes: fastsandbox still needs it on the
machine, its daemon running (see [Installation](installation.md#install-docker-sandboxes)).

## What it gives

| Part | Name | What it does |
|---|---|---|
| Skills | `fastsandbox`, `client`, `tasks`, `agents`, `testing`, `troubleshooting` | The library, domain by domain: its API with exact signatures, its rules and its pitfalls, with a short example each. Claude loads the one the work calls for. |
| Command | `/fastsandbox:new-project` | Scaffolds a project, an application of coding agents, an application of tasks or a tool built on the client, with a pyproject in Python 3.14, the code, tests that run without a daemon, and a README. |
| Command | `/fastsandbox:add-task` | Adds a task or an agent task, and its test, to an existing application. |
| Command | `/fastsandbox:doctor` | Checks the machine, read-only: Docker Sandboxes, Python, the package, the API version of the daemon, the kits, the agent keys. |
| Agent | `fastsandbox:sandbox-reviewer` | Reviews code that uses fastsandbox for the mistakes that cost safety or correctness: host files exposed, open network, secrets, sandboxes that stop or leak, unchecked agent results, missing timeouts. |

## Start a project

Check the machine, then scaffold:

```text
/fastsandbox:doctor
/fastsandbox:new-project my-agents agent
```

or say it in plain words:

```text
Set up a project with fastsandbox where Codex fixes the failing tests of a
repository, on a private clone, and returns a patch.
```

Claude asks what it needs to know, writes the project, and runs its tests,
which use the fake daemon of `fastsandbox.testing`: no sandbox is created. It
asks before running anything that creates real sandboxes on your daemon.

## Safe by default

- The plugin reads no secret: the doctor checks which agent keys are set by
  their names, never their values, and the projects it writes name the
  variables you export.
- The code it writes follows the defaults of the [agent pages](../agents/repository.md):
  a private clone rather than your directory, network rules, a timeout, and
  the work checked by the tests in the sandbox.

## Updates

The plugin is released with the package and carries its version. Claude Code
does not update plugins of other marketplaces on its own: run
`/plugin marketplace update fastsandbox`, or turn auto-update on in
`/plugin` › *Marketplaces*.
