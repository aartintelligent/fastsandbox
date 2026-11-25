"""The documentation site of `docs/`: complete, and in step with the package.

`just docs-build` checks that the site builds, links and references included;
these checks keep it complete: every public name in the API reference, every
page in the navigation, every example on the examples page.
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

import fastsandbox.exceptions
import fastsandbox.testing
import fastsandbox.types

ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs"
PACKAGE = ROOT / "fastsandbox"


def reexports(init: Path, package: str) -> list[tuple[str, str]]:
    """The public names `init` re-exports (`from .x import Y as Y`), with their module."""
    names = []
    for node in ast.parse(init.read_text()).body:
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            module = f"{package}.{node.module}" if node.module else package
            names += [(alias.name, module) for alias in node.names if alias.asname == alias.name]
    return [(name, module) for name, module in names if not name.startswith("__")]


def documented() -> set[str]:
    """The objects the reference renders, a whole module covering its `__all__`."""
    names = set()
    for page in (DOCS / "reference").glob("*.md"):
        names.update(re.findall(r"^::: (\S+)$", page.read_text(), re.MULTILINE))
    for module in (fastsandbox.exceptions, fastsandbox.testing, fastsandbox.types):
        if module.__name__ in names:
            names.update(f"{module.__name__}.{name}" for name in module.__all__)
    return names


def nav_pages(entries: list[Any]) -> list[str]:
    """The pages of the `nav` of zensical.toml, sections flattened."""
    pages = []
    for entry in entries:
        values = list(entry.values()) if isinstance(entry, dict) else [entry]
        for value in values:
            pages += nav_pages(value) if isinstance(value, list) else [value]
    return pages


@pytest.mark.parametrize(
    ("name", "module"),
    reexports(PACKAGE / "__init__.py", "fastsandbox"),
    ids=lambda value: value,
)
def test_public_name_in_reference(name: str, module: str) -> None:
    candidates = {f"fastsandbox.{name}", f"{module}.{name}"}
    assert candidates & documented(), f"no `::: fastsandbox.{name}` in docs/reference/"


@pytest.mark.parametrize(
    ("name", "module"),
    reexports(PACKAGE / "models" / "__init__.py", "fastsandbox.models"),
    ids=lambda value: value,
)
def test_model_in_reference(name: str, module: str) -> None:
    assert f"fastsandbox.models.{name}" in documented(), (
        f"no `::: fastsandbox.models.{name}` in docs/reference/models.md"
    )


def test_every_page_in_nav() -> None:
    config = tomllib.loads((ROOT / "zensical.toml").read_text())
    pages = nav_pages(config["project"]["nav"])
    files = sorted(str(path.relative_to(DOCS)) for path in DOCS.rglob("*.md"))
    assert sorted(pages) == files


@pytest.mark.parametrize(
    "script", sorted((ROOT / "examples").glob("*.py")), ids=lambda path: path.stem
)
def test_example_listed(script: Path) -> None:
    link = f"/examples/{script.name}"
    page = DOCS / "guides" / "examples.md"
    assert link in page.read_text(), f"{script.name} not in docs/guides/examples.md"


TEXT_SUFFIXES = {".md", ".py", ".pyi", ".toml", ".html", ".js", ".css", ".json", ".yml"}
DESCRIBED = [
    ROOT / name
    for name in ("docs", "docs_src", "fastsandbox", "overrides", "plugins", ".claude-plugin")
] + [ROOT / name for name in ("README.md", "CONTRIBUTING.md", "AGENTS.md", "pyproject.toml")]


def described_files() -> list[Path]:
    """The files that describe fastsandbox: its pages, code, plugin and manifests."""
    files = []
    for path in DESCRIBED:
        if path.is_file():
            files.append(path)
        else:
            files += [p for p in path.rglob("*") if p.is_file() and p.suffix in TEXT_SUFFIXES]
    return sorted(files)


@pytest.mark.parametrize("path", described_files(), ids=lambda path: str(path.relative_to(ROOT)))
def test_described_on_its_own_terms(path: Path) -> None:
    # fastsandbox is never described by comparison with another framework.
    found = re.findall(r"\bFast(?:API|MCP)\b|FastAPI-style", path.read_text())
    assert not found, f"{path.relative_to(ROOT)} compares fastsandbox with {found[0]}"
