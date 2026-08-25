"""Docstring validity meta-tests: summaries must be well-formed sentences.

A "valid" docstring in Via starts with a one-line summary that ends with a
period, matching the Google convention configured for ruff. Presence alone
is checked by ``test_docstrings.py``; this module checks quality.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

SOURCE_ROOTS = [
    REPO_ROOT / "packages",
    REPO_ROOT / "services",
]
_EXCLUDED_DIR_NAMES = {"__pycache__", ".venv", "node_modules", ".next"}


def _python_sources() -> list[Path]:
    """Collect first-party Python sources.

    Returns:
        Sorted list of ``*.py`` paths.
    """
    files: list[Path] = []
    for root in SOURCE_ROOTS:
        files.extend(
            p
            for p in root.rglob("*.py")
            if not any(part in _EXCLUDED_DIR_NAMES for part in p.parts)
        )
    return sorted(set(files))


def _summary_line(docstring: str) -> str:
    """Extract the first sentence/line of a docstring.

    Args:
        docstring: Full docstring text.

    Returns:
        The summary line with whitespace normalized.
    """
    return " ".join(docstring.strip().splitlines()[0].split())


@pytest.mark.docstring
@pytest.mark.parametrize("path", _python_sources(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_docstring_summary_ends_with_period(path: Path) -> None:
    """Every docstring's summary line is a complete sentence ending in '.'.

    Args:
        path: Python source file under inspection.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    nodes: list[ast.AST] = [tree]
    nodes.extend(
        n
        for n in ast.walk(tree)
        if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    )
    bad: list[str] = []
    for node in nodes:
        doc = ast.get_docstring(node)  # type: ignore[arg-type]
        if not doc or len(doc.strip()) < 8:
            continue
        name = getattr(node, "name", "<module>")
        summary = _summary_line(doc)
        if not summary.endswith("."):
            bad.append(f"{name!r}: '{summary[:60]}'")
    assert not bad, f"{path.relative_to(REPO_ROOT)}: summary lines must end with '.': {bad}"
