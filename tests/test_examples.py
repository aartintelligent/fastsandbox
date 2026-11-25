"""The examples of `examples/`: documented, listed, and self-contained in a sandbox.

The examples create real sandboxes and run locally only (`just example
NAME`); these checks keep them documented and listed without a daemon.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).parent.parent / "examples"
SCRIPTS = sorted(EXAMPLES.glob("*.py"))
PROGRAMS = sorted(
    path for path in (EXAMPLES / "common" / "programs").glob("*.py") if path.name != "__init__.py"
)


def example_name(script: Path) -> str:
    """The name `just example` takes for `script`, e.g. `shell-exec`."""
    return script.stem.replace("_", "-")


def imported_modules(path: Path) -> set[str]:
    """The top-level modules `path` imports, relative imports aside."""
    modules = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def test_there_are_examples():
    assert len(SCRIPTS) >= 48


@pytest.mark.parametrize("script", SCRIPTS, ids=example_name)
def test_an_example_says_what_it_shows_and_how_to_run_it(script):
    docstring = ast.get_docstring(ast.parse(script.read_text()))
    assert docstring, f"{script.name} has no module docstring"
    summary, _, body = docstring.partition("\n\n")
    assert "\n" not in summary, f"the summary of {script.name} is not one line"
    assert body, f"{script.name} has a summary only"
    assert f"just example {example_name(script)}" in docstring


@pytest.mark.parametrize("script", SCRIPTS, ids=example_name)
def test_an_example_is_listed_in_the_readme(script):
    readme = (EXAMPLES / "README.md").read_text()
    assert f"[`{example_name(script)}`]({script.name})" in readme


@pytest.mark.parametrize("script", SCRIPTS, ids=example_name)
def test_an_example_runs_only_as_a_script(script):
    tree = ast.parse(script.read_text())
    guards = [
        node
        for node in tree.body
        if isinstance(node, ast.If) and "__main__" in ast.unparse(node.test)
    ]
    assert guards, f"{script.name} runs on import"


@pytest.mark.parametrize("program", PROGRAMS, ids=lambda path: path.stem)
def test_a_program_run_in_a_sandbox_needs_the_standard_library_alone(program):
    foreign = imported_modules(program) - set(sys.stdlib_module_names)
    assert not foreign, f"{program.name} imports {sorted(foreign)}"
