---
name: doctor
description: Checks, read-only, that this machine is ready for fastsandbox - Docker Sandboxes installed and its daemon answering, Python 3.14, the package, the API version of the daemon, the kit cache, the agent keys present - and says how to fix what is missing. Use before a first project, or when a fastsandbox program fails to connect.
disable-model-invocation: true
---

# fastsandbox doctor

Run each check below, from the project directory when there is one, and finish
with a table: check, status (ok / missing / warning), and the fix. Every check
is read-only: create nothing, change nothing, install nothing without asking.

## 1. Docker Sandboxes

```sh
sbx version
```

fastsandbox connects to the socket of `sandboxd`, the daemon of Docker
Sandboxes; without it nothing works. If `sbx` is not found, Docker Sandboxes is
not installed: point to https://docs.docker.com/ai/sandboxes/ and stop there.
If it fails, the daemon is not running for this user.

## 2. Python

```sh
uv python find 3.14 || python3 --version
```

fastsandbox needs Python 3.14 or newer; `uv python install 3.14` installs it.

## 3. The package and the daemon

In a project that depends on fastsandbox:

```sh
uv run fastsandbox info
```

Elsewhere, `uvx fastsandbox info`. It prints the socket, the version of `sbx`
and its health, the API version of the daemon and the range this release of
fastsandbox supports, the number of sandboxes and the kit cache. Read it:

- an error naming the socket: the daemon is not reachable as this user, or
  `DOCKER_SANDBOXES_API` points elsewhere;
- a warning on the API version: the daemon runs a version this release was not
  checked against; upgrading fastsandbox is the fix;
- the kit cache directory: where compiled kits are kept.

## 4. The kits

A kit is compiled with the `sbx` CLI on its first use, which can take minutes.
If the user names the kits they will use (`shell`, `claude`, `codex`...),
suggest `uv run fastsandbox kits compile <kit>` for each, and run it only if
they agree.

## 5. The agent keys

Check which keys are set, **printing their names only, never their values**:

```sh
for name in ANTHROPIC_API_KEY OPENAI_API_KEY CODEX_API_KEY COPILOT_GITHUB_TOKEN GH_TOKEN GITHUB_TOKEN CURSOR_API_KEY DEVIN_API_KEY FACTORY_API_KEY KIRO_API_KEY GEMINI_API_KEY GOOGLE_API_KEY OPENROUTER_API_KEY GROQ_API_KEY MISTRAL_API_KEY NEBIUS_API_KEY XAI_API_KEY; do
  if [ -n "$(printenv "$name")" ]; then echo "$name is set"; fi
done
```

Map them to the agents: `claude` reads `ANTHROPIC_API_KEY`; `codex`
`OPENAI_API_KEY`, else `CODEX_API_KEY`; `copilot` `COPILOT_GITHUB_TOKEN`, else
`GH_TOKEN`, else `GITHUB_TOKEN`; `cursor` `CURSOR_API_KEY`; `devin`
`DEVIN_API_KEY`; `droid` `FACTORY_API_KEY`; `kiro` `KIRO_API_KEY`;
`docker-agent` and `opencode` the keys of the model providers. A key missing
here is not an error: a secret stored with `sbx secret set` applies when none
is pushed.

## 6. Report

End with the table and, for each line that is not ok, the one action that
fixes it. If everything is ok, suggest `/fastsandbox:new-project`.
