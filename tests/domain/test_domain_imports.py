"""Guardrails for the zero-Django domain rule."""

import ast
from pathlib import Path


BANNED_IMPORT_ROOTS = {"celery", "django", "httpx", "rest_framework"}


def test_domain_layer_has_no_framework_imports():
    domain_root = Path(__file__).resolve().parents[2] / "domain"

    for path in domain_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots = {node.module.split(".")[0]}
            else:
                continue

            banned = imported_roots & BANNED_IMPORT_ROOTS
            assert not banned, f"{path} imports banned domain dependency: {banned}"
