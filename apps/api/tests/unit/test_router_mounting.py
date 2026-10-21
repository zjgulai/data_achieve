"""Guard against routers that are defined but never mounted.

In October 2026, 25 implemented endpoints returned 404 because their routers
were imported in ``main.py`` but never passed to ``include_router``. This test
walks the AST of ``main.py`` and fails on the same class of omission.
"""

from __future__ import annotations

import ast
from pathlib import Path

from data_intelligence_hub.main import create_app

MAIN_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "data_intelligence_hub"
    / "main.py"
)


def _router_imports(tree: ast.Module) -> dict[str, str]:
    imported: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ""
        if not module.startswith("data_intelligence_hub.api.routes"):
            continue
        for alias in node.names:
            if alias.name == "router":
                imported[alias.asname or alias.name] = module
    return imported


def _included_routers(tree: ast.Module) -> set[str]:
    included: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "include_router" or not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Name):
            included.add(first.id)
    return included


def test_every_imported_api_router_is_mounted() -> None:
    tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
    imported = _router_imports(tree)
    included = _included_routers(tree)
    missing = sorted(name for name in imported if name not in included)
    assert not missing, f"routers imported but never mounted: {missing}"


def test_application_exposes_a_large_route_surface() -> None:
    app = create_app()
    assert len(app.routes) >= 220, (
        f"unexpectedly small route surface: {len(app.routes)} route objects"
    )
