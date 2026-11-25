"""The Claude Code plugin of `plugins/fastsandbox/`: valid, complete, in step with the package.

`just plugin-validate` checks it with the `claude` CLI; these checks run
everywhere: the manifests and their version, the skills and their links, the
Python they show, the public API they cover, and the project templates, whose
tests run as a user would run them.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

import fastsandbox
import fastsandbox.exceptions
import fastsandbox.testing
import fastsandbox.types

ROOT = Path(__file__).parent.parent
PLUGIN = ROOT / "plugins" / "fastsandbox"
TEMPLATES = PLUGIN / "skills" / "new-project" / "templates"
DOCS = ROOT / "docs"
SITE = "https://aartintelligent.github.io/fastsandbox/"

MARKDOWN = sorted(PLUGIN.rglob("*.md"))
SKILLS = sorted(PLUGIN.glob("skills/*/SKILL.md"))
TEMPLATE_DIRS = sorted(path for path in TEMPLATES.iterdir() if path.is_dir())
FENCED = re.compile(r"^```[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
PYTHON = re.compile(r"^```python[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)


def relative(path: Path) -> str:
    """`path` relative to the plugin, as a test id."""
    return str(path.relative_to(PLUGIN))


def frontmatter(path: Path) -> dict[str, str]:
    """The fields of the YAML frontmatter of `path`, folded onto one line each."""
    text = path.read_text()
    assert text.startswith("---\n"), f"{relative(path)} has no frontmatter"
    fields: dict[str, str] = {}
    key = ""
    for line in text[4 : text.index("\n---\n", 4)].splitlines():
        if line[:1].isspace() and key:
            fields[key] = f"{fields[key]} {line.strip()}".strip()
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        fields[key] = "" if value in {">", "|", ">-", "|-"} else value.strip("\"'")
    return fields


def reexports(init: Path) -> list[str]:
    """The public names `init` re-exports (`from .x import Y as Y`)."""
    names = []
    for node in ast.parse(init.read_text()).body:
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            names += [alias.name for alias in node.names if alias.asname == alias.name]
    return [name for name in names if not name.startswith("__")]


def code(text: str) -> str:
    """The code of `text`: its fenced blocks and its inline code spans."""
    return "\n".join(FENCED.findall(text) + re.findall(r"`([^`\n]+)`", FENCED.sub("", text)))


def exists(module: str, name: str) -> bool:
    """Whether `module` has the attribute or the submodule `name`."""
    return hasattr(importlib.import_module(module), name) or (
        importlib.util.find_spec(f"{module}.{name}") is not None
    )


PUBLIC = sorted(
    set(reexports(ROOT / "fastsandbox" / "__init__.py"))
    | set(fastsandbox.exceptions.__all__)
    | set(fastsandbox.testing.__all__)
    | set(fastsandbox.types.__all__)
)
PLUGIN_CODE = "\n".join(code(page.read_text()) for page in MARKDOWN)


def load(path: Path) -> Any:
    """The JSON document at `path`."""
    return json.loads(path.read_text())


def test_marketplace_lists_the_plugin() -> None:
    marketplace = load(ROOT / ".claude-plugin" / "marketplace.json")
    manifest = load(PLUGIN / ".claude-plugin" / "plugin.json")
    [entry] = marketplace["plugins"]
    assert entry["name"] == manifest["name"] == marketplace["name"] == "fastsandbox"
    assert (ROOT / entry["source"]).resolve() == PLUGIN.resolve()
    assert "version" not in entry, "the version lives in plugin.json only"


def test_plugin_carries_the_version_of_the_package() -> None:
    manifest = load(PLUGIN / ".claude-plugin" / "plugin.json")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert manifest["version"] == project["version"]
    release = load(ROOT / "release-please-config.json")["packages"]["."]
    bumped = {extra["path"] for extra in release["extra-files"]}
    assert "plugins/fastsandbox/.claude-plugin/plugin.json" in bumped


@pytest.mark.parametrize("skill", SKILLS, ids=lambda path: path.parent.name)
def test_skill_frontmatter(skill: Path) -> None:
    fields = frontmatter(skill)
    assert fields["name"] == skill.parent.name
    assert 0 < len(fields["description"]) <= 1536
    assert len(skill.read_text().splitlines()) <= 500


@pytest.mark.parametrize("page", MARKDOWN, ids=relative)
def test_links_resolve(page: Path) -> None:
    for target in re.findall(r"\]\(([^)\s]+)\)", page.read_text()):
        if target.startswith(("http://", "https://", "mailto:", "#")) or "${" in target:
            continue
        path = target.split("#")[0]
        assert (page.parent / path).exists(), f"{relative(page)} links to {target}"


@pytest.mark.parametrize("page", MARKDOWN, ids=relative)
def test_site_urls_name_pages(page: Path) -> None:
    for path in re.findall(re.escape(SITE) + r"([\w\-/]*)", page.read_text()):
        path = path.strip("/")
        candidates = (
            [DOCS / f"{path}.md", DOCS / path / "index.md"] if path else [DOCS / "index.md"]
        )
        assert any(candidate.is_file() for candidate in candidates), (
            f"{relative(page)}: no page of docs/ at {SITE}{path}"
        )


@pytest.mark.parametrize("page", MARKDOWN, ids=relative)
def test_python_is_valid_and_names_exist(page: Path) -> None:
    for block in PYTHON.findall(page.read_text()):
        tree = ast.parse(block, filename=relative(page))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("fastsandbox"):
                module = node.module or ""
                for alias in node.names:
                    assert exists(module, alias.name), f"{relative(page)}: {module}.{alias.name}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("fastsandbox"):
                        importlib.import_module(alias.name)
            elif (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "fastsandbox"
            ):
                assert exists("fastsandbox", node.attr), (
                    f"{relative(page)}: fastsandbox.{node.attr}"
                )


@pytest.mark.parametrize("name", PUBLIC)
def test_public_name_in_plugin(name: str) -> None:
    pattern = rf"(?<![\w]){re.escape(name)}(?!\w)"
    assert re.search(pattern, PLUGIN_CODE), f"{name} is in no skill of the plugin"


def test_every_template_is_offered() -> None:
    offered = (PLUGIN / "skills" / "new-project" / "SKILL.md").read_text()
    for template in TEMPLATE_DIRS:
        assert f"templates/{template.name}/" in offered


@pytest.mark.parametrize("template", TEMPLATE_DIRS, ids=lambda path: path.name)
def test_template_project(template: Path) -> None:
    ours = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    config = tomllib.loads((template / "pyproject.toml").read_text())
    assert config["project"]["requires-python"] == ours["requires-python"]
    assert any(dep.startswith("fastsandbox") for dep in config["project"]["dependencies"])
    app = config.get("tool", {}).get("fastsandbox", {}).get("app")
    if app is not None:
        assert (template / app).is_file()
    assert (template / "README.md").is_file()


@pytest.mark.parametrize("template", TEMPLATE_DIRS, ids=lambda path: path.name)
def test_template_tests_pass(template: Path, tmp_path: Path) -> None:
    project = tmp_path / template.name
    shutil.copytree(template, project, ignore=shutil.ignore_patterns("__pycache__", ".*_cache"))
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {fastsandbox.SOCKET_ENV, "FASTSANDBOX_KIT_CACHE"}
    }
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
