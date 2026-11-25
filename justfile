# ------------------------------------------------------------------------------
# just — the development recipes of fastsandbox.
#
# Every recipe runs through `uv`, which keeps the environment in `.venv` and
# rebuilds the native extension when a Rust file changed (`[tool.uv]
# cache-keys` in pyproject.toml).
# ------------------------------------------------------------------------------

# List the recipes.
default:
    @just --list

# Build the native extension and install the package in editable mode.
sync:
    uv sync

# Every local gate: formatting, lints, spelling, types, tests, coverage, the
# documentation and the supply chain, as the CI workflow runs them.
ci: fmt-check lint typos types test coverage docs-build deny

# Format the Rust, the TOML and the Python code.
fmt:
    cargo fmt
    taplo fmt
    uv run ruff format

# Check the formatting without changing anything.
fmt-check:
    cargo fmt --check
    taplo fmt --check
    uv run ruff format --check

# Lint the Rust (clippy, warnings as errors) and the Python (ruff).
lint:
    cargo clippy --all-targets -- -D warnings
    uv run ruff check

# Spell-check the repository (`[tool.typos]` in pyproject.toml).
typos:
    typos

# Type-check the package and the examples (mypy, strict).
types:
    uv run mypy

# The tests, against the fake daemon of `fastsandbox.testing`.
test *ARGS:
    uv run pytest {{ARGS}}

# The tests with the coverage of the package, below which they fail
# (`[tool.coverage.report] fail_under` in pyproject.toml).
coverage:
    uv run pytest --cov --cov-report=term

# Preview the documentation site on http://localhost:8000, rebuilt as its pages,
# the snippets of `docs_src/` or the docstrings change.
docs *ARGS:
    uv run zensical serve {{ARGS}}

# Build the documentation site into `site/` in strict mode (`zensical.toml`): a
# broken link, a missing snippet or an unresolved API reference fails it.
docs-build:
    uv run zensical build --clean --strict

# The supply chain: the Rust dependencies against deny.toml, the locked Python
# ones against the advisories of PyPI.
deny:
    cargo deny check
    @mkdir -p target
    uv export --all-groups --no-emit-project --format requirements-txt --output-file target/requirements.txt
    uv run pip-audit --strict --disable-pip --requirement target/requirements.txt

# The tests against the real daemon of the current user (`tests/live/`): they
# create and delete throw-away sandboxes.
test-live *ARGS:
    uv run pytest -m live -o addopts="--import-mode=importlib" tests/live {{ARGS}}

# Run the example NAME of `examples/` (`just example shell-exec`), with its
# arguments, each passed as it was quoted (`-- "explain this project"` stays one
# argument): it creates real sandboxes on the daemon of the current user, and
# deletes them when it ends.
[positional-arguments]
example NAME *ARGS:
    @shift; uv run python examples/{{replace(NAME, "-", "_")}}.py "$@"

# Validate the Claude Code plugin and its marketplace with the `claude` CLI,
# strict: warnings fail. Not part of `ci`, which does not install Claude Code;
# tests/test_plugin.py checks the plugin there.
plugin-validate:
    claude plugin validate --strict plugins/fastsandbox
    claude plugin validate --strict .

# Build the release wheel of this platform into `dist/`.
wheel:
    uv run maturin build --release --out dist
