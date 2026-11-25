# AGENTS.md

Guidance for AI coding agents working in this repository. `CLAUDE.md` is a symlink to this file, so
every tool reads the same instructions. This file holds the doctrine: the architecture and its
reasons, and the rules an agent follows. `CONTRIBUTING.md` holds the workflow (setting up, where a
change starts, the development rules, the gates, commits and pull requests), binding on agents too.

## What this is

fastsandbox: the Python package of Docker Sandboxes (`sbx`), the package at the root of the
repository.

- `fastsandbox/` — the package, at the root:
  - the client, one module per domain of `docker-sandbox`: `client.py` (`connect`, `Client`,
    `Creation`), `daemon.py`, `sandboxes.py`, `sandbox.py`, `sessions.py`, `ssh.py`, `images.py`,
    `events.py`, `policy.py`, `mcp.py`, `prompts.py`, `kits.py`, `streams.py`;
  - `models/`: Pydantic models mirroring the serde types of the crate, one module per domain
    (field names of the crate, aliases for the daemon's own names, `extra="allow"`); `wire()`
    gives the shape the extension expects;
  - the framework, one module per concept: `applications.py` (`FastSandbox`, `run`), `tasks.py`,
    `params.py` (markers), `dependencies/` (`models.py`, `utils.py`), `context.py`,
    `network.py`, `agents.py` (profiles of the agents `sbx` knows, `AgentRunner`);
  - `exceptions.py` (built by name from Rust), `types.py`, `utils.py`, `testing.py` (the fake
    daemon), `cli.py`, `_native.pyi` (stubs of the extension);
  - `__init__.py` re-exports the public API only (`from .x import Y as Y`).
- `fastsandbox-native/` — the native extension `fastsandbox._native` (Rust, PyO3), a thin bridge to the
  crate: one frozen class per handle, every async method an awaitable on the shared tokio runtime
  of `pyo3-async-runtimes`, payloads in their serde shape (`pythonize`), errors raised as the
  classes of `fastsandbox.exceptions`. No logic of its own.
- `docs/` — the pages of the documentation site, built with Zensical (`zensical.toml`; no
  MkDocs, no `mkdocs.yml`), one directory per section of the `nav` (`overview/`, `get-started/`,
  `agents/`, `framework/`, `client/`, `guides/`, `reference/`, `project/`): their code is included from `docs_src/`
  (`--8<-- "docs_src/…"`), the API reference rendered from the docstrings
  (`::: fastsandbox.X`). `tests/test_docs.py` keeps it complete: a new public name gets its
  `:::` entry in `docs/reference/`, a new page its place in the `nav`.
- `docs_src/` — the snippets of the documentation, by topic; each one is tested by
  `tests/test_docs_src/`.
- `examples/` — complete programs, one script per example of `docker-sandbox`, same names
  (`shell_exec.py` for `shell-exec`, run with `just example shell-exec`); `common/` holds what
  they share, `common/programs/` the scripts run inside sandboxes (standard library only). They
  create real sandboxes: linted and type-checked in `just ci`, run locally only.
- `tests/` — one file per behavior against the fake daemon; `tests/live/` against the real one.
- `plugins/fastsandbox/` — the Claude Code plugin users install, listed by the marketplace
  `.claude-plugin/marketplace.json`: skills per domain of the library (`fastsandbox`, `client`,
  `tasks`, `agents`, `testing`, `troubleshooting`) with `reference/` files, the user-invoked
  workflows `new-project` (with its project templates), `add-task` and `doctor`, and the
  `sandbox-reviewer` agent. `tests/test_plugin.py` keeps it in step with the public API.

## Commands

```bash
just ci          # fmt-check lint typos types test coverage docs-build deny
just test        # pytest, no daemon needed
just test-live   # against the daemon of the current user
just docs        # preview the documentation site (just docs-build: strict build)
uv sync          # rebuild the extension after a Rust change (uv run does it too)
```

## CI and releases

- `.github/workflows/ci.yml` mirrors `just ci` and reads no secret; `CI OK` is the required status.
  A new gate goes into both. Actions are pinned to the commit of a release, the tag in a comment.
- `.github/workflows/release.yml`: release-please opens the release PR (`release-please-config.json`,
  which also bumps Cargo.toml, Cargo.lock and uv.lock), its merge tags and builds the wheels, which
  go to PyPI by trusted publishing. Versions and `CHANGELOG.md` are never edited by hand. The first
  release is 0.1.0 (`"initial-version"`, an empty `.release-please-manifest.json`); before 1.0 a
  breaking change bumps the minor version and a feature the patch version. Running the workflow by
  hand (*Actions* → *Release* → *Run workflow*) builds and checks the distributions of a commit
  without releasing anything.
- `.github/workflows/docs.yml` builds the site on every push to `main` and deploys it to GitHub
  Pages.
- Dependabot bumps the actions, the uv and the Cargo dependencies every week.
- One-time setup of the GitHub repository: the `release` environment, restricted to `main`, holds
  `RELEASE_PLEASE_TOKEN` (a fine-grained token with *Contents* and *Pull requests* write access:
  a release PR opened with the automatic token never gets `CI OK`); the `pypi` environment,
  restricted to `main`, is the trusted publisher of the PyPI project (workflow `release.yml`, no
  token stored); Codecov authenticates through OIDC; GitHub Pages publishes from Actions, its
  `github-pages` environment restricted to `main`; branch protection of `main`: pull requests only,
  `CI OK` required, a code-owner review, squash merges, the merge queue.
- The commit types of `committed.toml`, the changelog sections of `release-please-config.json` and
  `CONTRIBUTING.md` change together. The coverage threshold (`fail_under`, `codecov.yml`) only goes
  up.

## Working mode and attribution

- Routine changes within these conventions proceed on their own; a design decision (new
  dependency, public API change, new module or layout) is proposed to the maintainer first.
- Commit messages, PR titles, descriptions and review comments never mention the AI tooling: no
  "Claude", no `Co-Authored-By` trailer, no "Generated with" footer. Authorship is only the
  configured git user.
- Never weaken a lint (workspace `[lints]`, `clippy.toml`, `[tool.ruff]`, mypy strict) or a test to
  make something pass. Commit or push only when asked.

## The daemon

- Everything about the daemon comes from `docker-sandbox` and its audit: a new route or field goes
  into the crate first, then here.
- A sandbox only stays running while a session is held: code that works in one uses
  `async with sandbox.running():`. A sandbox runs right after creation.
- Live tests and examples create real sandboxes: record the daemon state before
  (`just state-save` in the `docker-sandbox` repository), check it after (`just state-check`), and
  remove what a run left (sandboxes, images). Only dummy secret values; never read or change the
  user's stored secrets. Never call `/daemon/reset`, `/daemon/shutdown` or
  `POST /policy/network/setup`.
- Examples that change global state (the network policy, daemon settings, `sbx mcp`
  registrations, dummy `mcp:<server>:…` secrets) restore it when they end; a new one does too.

## Conventions

- Rust: the conventions of `docker-sandbox` — `//!` header on every file, `///` on every item (it
  becomes the docstring), English, full sentences; `#[allow]` carries `reason = "…"`.
- Python: one module per concept, named by what it holds; Google-style docstrings with a one-line
  summary; every public item documented and typed (`mypy --strict`); `from __future__ import
  annotations`; ruff formatting at 100 columns. Helpers shared by modules live in `utils.py`,
  without a leading underscore; private ones stay in their module with one.
- TOML, YAML, justfile: an 80-column banner block at the top, comments on their own line, `=`
  aligned (`taplo fmt`).
- Nothing committed holds personal data (home directory, user or host name, e-mail) beyond the
  maintainer: the contact in `authors`, and the name, Aurelien Andre, that the About page and the
  copyright of the site put forward as the author.
