from pathlib import Path

import pytest


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests by suite so phase-based runs stay ergonomic."""
    for item in items:
        path_parts = Path(str(item.fspath)).parts
        if "tests" not in path_parts:
            continue
        if "domain" in path_parts:
            item.add_marker(pytest.mark.domain)
        elif "integration" in path_parts:
            item.add_marker(pytest.mark.integration)
        elif "e2e" in path_parts:
            item.add_marker(pytest.mark.e2e)
