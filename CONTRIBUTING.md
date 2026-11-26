# Contributing

The binding process of this repository: how to set up, where a change starts,
which rules it follows, which gates it must pass, how a commit is written and
how it lands. `AGENTS.md` holds the doctrine (the architecture and its
reasons); this file holds the workflow.

## Prerequisites

- Rust 1.97.1 through rustup (`rust-toolchain.toml` pins it, with `clippy` and
  `rustfmt`). The extension also builds on its minimum version, the
  `rust-version` of `Cargo.toml` (1.88), which CI checks.
- [uv](https://docs.astral.sh/uv/), which builds the extension and keeps the
  Python environment of the repository, on Python 3.14 (`.python-version`;
  uv installs it when it is missing). The package itself supports Python 3.12
  and later: ruff and mypy check the code against 3.12 (`target-version`,
  `python_version`), and the tests run on every supported version.
- `just` (task runner), `taplo` (TOML formatting), `typos` (spelling) and
  `cargo-deny` (supply-chain audit).
- For the live tests and the examples only: Docker Sandboxes installed and its
  daemon running for your user (`sbx version` answers), with the `sbx` CLI on
  `PATH`, and a checkout of `docker-sandbox` for `just state-save` and
  `just state-check`.

## Getting started

```bash
uv sync               # builds the extension, installs the package in editable mode
just test             # the tests, against the fake daemon: no daemon needed
just test-python 3.12 # the same tests on another supported Python
just docs             # the documentation site on http://localhost:8000, rebuilt as you write
just ci               # every gate, before a push
just test-live        # the tests against the daemon of your user (creates sandboxes)
just example NAME     # one example of examples/ (creates sandboxes)
just plugin-validate  # the Claude Code plugin, with the `claude` CLI
```

A change to a Rust file rebuilds the extension on the next `uv run`
(`[tool.uv] cache-keys`).

## Where a change starts

- **A bug or a change request** starts as an
  [issue](https://github.com/aartintelligent/fastsandbox/issues/new/choose),
  with its template. A change request says what you are trying to do rather
  than how you would implement it; the design is agreed in the issue, then the
  pull request follows it.
- **A design decision** (a new dependency, a change to the public API, a new
  module) is proposed in an issue before any code.
- **A new route or field of the daemon** lands in
  [`docker-sandbox`](https://github.com/aartintelligent/docker-sandbox) first,
  with its audit and its fixtures, then here.
- **Questions about Docker Sandboxes itself** belong to the
  [Docker documentation](https://docs.docker.com/ai/sandboxes/).
- **A security vulnerability** never goes in a public issue: follow the
  [security policy](https://github.com/aartintelligent/fastsandbox/security/policy).

## Development rules

- The native extension carries no logic: it bridges `docker-sandbox`. Helpers,
  defaults and conveniences are written in Python.
- Python: one module per concept, named by what it holds; Google-style
  docstrings with a one-line summary; every public item documented and typed
  (mypy, strict); `from __future__ import annotations`; ruff formatting at 100
  columns. Helpers shared by modules live in `utils.py` without a leading
  underscore; private ones stay in their module, with one.
- Rust: a `//!` header on every file, `///` on every item (it becomes the
  docstring), full sentences; an `#[allow]` carries its `reason = "…"`.
- TOML, YAML and the justfile open with an 80-column header comment stating
  the file's role; comments sit on their own line, above the key, never
  inline; `=` aligned (`taplo fmt`).
- Never weaken a lint (workspace `[lints]`, `clippy.toml`, `[tool.ruff]`, mypy
  strict), a test or a threshold to make something pass. The coverage
  threshold (`fail_under`, `codecov.yml`) only goes up.
- English in code, docstrings, documentation and commits.
- Nothing committed holds personal data (a home directory, a user or host
  name, an e-mail address) beyond the maintainer's: the contact in `authors`,
  and the name the About page and the copyright of the site give.

## Quality gates

```bash
just ci   # fmt-check, lint, typos, types, test, coverage, docs-build, deny
```

| Gate | Recipe | What it guards |
|---|---|---|
| Format | `just fmt-check` | `cargo fmt`, `taplo fmt`, `ruff format` |
| Lint | `just lint` | clippy (pedantic, warnings as errors), ruff, examples included |
| Spelling | `just typos` | `[tool.typos]` in pyproject.toml |
| Types | `just types` | mypy, strict, on the package and the examples |
| Tests | `just test` | pytest against the fake daemon, `docs_src/` included; the examples documented and listed |
| Coverage | `just coverage` | at least 85 % of the lines of the package run (`[tool.coverage.report] fail_under`) |
| Docs | `just docs-build` | the documentation site builds in strict mode: links, anchors, snippets and API references resolve |
| Dependencies | `just deny` | `cargo deny check` (deny.toml), `pip-audit` on the locked Python dependencies |
| Live | `just test-live` | the real daemon of the current user |

Every gate but the live one passes before a push. The live gate runs when a
change touches the calls to the daemon.

CI (`.github/workflows/ci.yml`) runs the same gates on every pull request, in
the merge queue and on `main`, without any secret; a pull request runs only the
jobs its changes concern, and `CI OK` is the one required status. On top of
`just ci`, it tests on Python 3.12, 3.13 and 3.14 on Linux (and on 3.12 and
3.14 on macOS when the package or the extension changes), builds the extension
on its minimum Rust version, builds the wheel and installs it on every
supported Python, and checks that every commit of the pull request is a
Conventional Commit. The live tests and the examples need a real daemon
and stay local.

## Testing

- One test file per behavior (`test_create.py`, `test_dependencies.py`…),
  against the fake daemon of `fastsandbox.testing`; the `fake_environment`
  fixture points code written for the real daemon at it, kit cache included.
- Every snippet of `docs_src/` has its test in `tests/test_docs_src/`.
- Interactive sessions, agent runs and SSH tunnels upgrade their connection,
  which the fake daemon answers with 501; the routes it does not serve, the
  event streams among them, answer 404. They are tested in `tests/live/`,
  against the real daemon.
- Live tests and examples create real sandboxes on your daemon. Record its
  state before (`just state-save` in `docker-sandbox`), check it after
  (`just state-check`), and remove what a run left: sandboxes, images. Use
  dummy secret values only; never read or change the secrets you have stored.
  Never call `/daemon/reset`, `/daemon/shutdown` or
  `POST /policy/network/setup`.

## Documentation

`just docs` previews the site as you write; `just docs-build` builds it as CI
does.

- A new page goes in the directory of its section of `docs/` and gets a named
  entry in the `nav` of `zensical.toml`; the first page of a section is an
  entry of its own, `Introduction`.
- Code comes from `docs_src/`: a page includes a tested snippet with
  `--8<-- "docs_src/tasks/run_tests.py"`, and a new snippet comes with its
  test. Only one-line fragments and shell commands are written in the page
  itself.
- A new public name gets its `:::` entry in `docs/reference/`; pages link it
  as `[Sandbox.exec()][fastsandbox.Sandbox.exec]`. `tests/test_docs.py` checks
  that the reference, the `nav` and the examples page are complete.
- fastsandbox is described on its own terms, never by comparison with another
  framework.

## The Claude Code plugin

`plugins/fastsandbox/` is the plugin users install with
`/plugin install fastsandbox --marketplace aartintelligent/fastsandbox`, and
`.claude-plugin/marketplace.json` the marketplace that lists it.

- It is released with the package: release-please bumps its version, never
  edit it by hand.
- A change to the public API updates the skill of its domain (`client`,
  `tasks`, `agents`, `testing`, `troubleshooting`) in the same pull request.
  `tests/test_plugin.py` checks that every public name appears in a skill,
  that every Python block parses and names real objects, that the links and
  the URLs of the site resolve, and runs the tests of the project templates.
- The project templates of `new-project` are user projects: linted,
  type-checked and tested with the package.
- Skills stay operational: signatures, rules, pitfalls, short examples, a link
  to the full page. A workflow with side effects is user-invoked
  (`disable-model-invocation: true`), asks before it creates real sandboxes,
  and never reads or prints a secret.
- `just plugin-validate` runs before a push that touches the plugin; it needs
  Claude Code, which CI does not install.

## Examples

- A new example follows one of `docker-sandbox`, under the same name
  (`shell_exec.py` for `shell-exec`), and uses what the library offers rather
  than rewriting it; what several examples need goes in `examples/common/`.
- Its module docstring says what it shows, what was measured, the credentials
  it reads, and `just example <name>`; it is listed in `examples/README.md` and
  on the examples page of the site. `tests/test_examples.py` checks both.
- A program run inside a sandbox (`examples/common/programs/`) uses the Python
  standard library alone.
- An example that changes global state (the network policy, daemon settings,
  `sbx mcp` registrations, dummy secrets) restores it when it ends.

## Commit conventions

Conventional Commits, in English, enforced by `committed` (`committed.toml`):

| Type | Changelog section |
|---|---|
| `feat` | Added |
| `fix` | Fixed |
| `perf` | Performance |
| `docs` | Documentation |
| `refactor` | Changed |
| `deprecate` | Deprecated |
| `revert` | Reverted |
| `test`, `build`, `ci`, `chore`, `style` | None |

The scope is the module or the area (`feat(client): …`, `fix(applications):
…`); a breaking change is marked with `!` (`feat(client)!: …`). Header and
lines at most 100 characters; lowercase description. No attribution trailer
of any tool.

## Pull requests

Every change branches off `main` and lands by pull request, squash-merged
through the merge queue, with `CI OK` green and a review from the code owners.
One topic per pull request, with its template filled in; its title becomes the
squash commit on `main`, so it follows the commit conventions.

Versions and `CHANGELOG.md` are never edited by hand: release-please derives
them from the commits on `main` and opens the release pull request; its merge
tags the version and publishes the wheels to PyPI.

## License

By contributing, you agree that your contributions are dual licensed under
MIT OR Apache-2.0, as the rest of the project.
