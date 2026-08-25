"""Repo-wide docstring presence meta-tests (marker: docstring).

Docstrings are a hard requirement in Via. Ruff's pydocstyle rules and
interrogate enforce them during lint; these tests re-assert presence from
inside the test suite so a violation fails `pytest` too, not just CI.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Source roots scanned for Python docstrings.
SOURCE_ROOTS = [
    REPO_ROOT / "packages",
    REPO_ROOT / "services",
]

_EXCLUDED_DIR_NAMES = {"__pycache__", ".venv", "node_modules", ".next", "_private"}


def _python_sources() -> list[Path]:
    """Collect all first-party Python source files.

    Returns:
        Sorted list of ``*.py`` paths under the source roots.
    """
    files: list[Path] = []
    for root in SOURCE_ROOTS:
        files.extend(
            p
            for p in root.rglob("*.py")
            if not any(part in _EXCLUDED_DIR_NAMES for part in p.parts)
        )
    return sorted(set(files))


def _has_real_docstring(node: ast.AST) -> bool:
    """Check whether an AST node carries a non-empty docstring.

    Args:
        node: Module, class or function node.

    Returns:
        True when a stripped docstring of at least 8 characters exists.
    """
    doc = ast.get_docstring(node)  # type: ignore[arg-type]
    return doc is not None and len(doc.strip()) >= 8


def _iter_definitions(tree: ast.Module, path: Path) -> list[tuple[Path, str]]:
    """Yield every public module/class/function lacking a docstring.

    Args:
        tree: Parsed module.
        path: File the tree came from (for messages).

    Returns:
        Offense tuples of (path, qualified name).
    """
    missing: list[tuple[Path, str]] = []
    if not _has_real_docstring(tree):
        missing.append((path, "<module>"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            if not _has_real_docstring(node):
                missing.append((path, node.name))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            parent_private = getattr(node, "_via_parent_private", False)
            if name.startswith("_") or parent_private:
                continue
            if not _has_real_docstring(node):
                missing.append((path, name))
    return missing


@pytest.mark.docstring
def test_every_public_definition_has_a_docstring() -> None:
    """All modules, public classes and public functions carry docstrings."""
    offenders: list[str] = []
    for path in _python_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for rel_path, name in _iter_definitions(tree, path):
            offenders.append(f"{rel_path.relative_to(REPO_ROOT)}::{name}")
    assert not offenders, f"missing docstrings ({len(offenders)}):\n" + "\n".join(
        sorted(offenders)[:40]
    )
