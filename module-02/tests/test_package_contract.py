"""Regression contracts for shared packaging and pytest discovery."""

import importlib
import json
import subprocess
import sys
from importlib.metadata import distribution
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOTS = {
    "ai_engineering_foundations": "module-01/src",
    "prompt_engineering_systems": "module-02/src",
    "rag_engineering_foundations": "module-03/src",
    "advanced_rag_evaluation": "module-04/src",
    "ai_agent_engineering": "module-05/src",
}


def test_both_package_trees_are_importable() -> None:
    """Import both package trees, including their architectural subpackages."""
    package_names = (
        "ai_engineering_foundations",
        "ai_engineering_foundations.providers",
        "prompt_engineering_systems",
        "prompt_engineering_systems.prompts",
        "prompt_engineering_systems.structured",
        "prompt_engineering_systems.evaluation",
        "prompt_engineering_systems.safety",
        "prompt_engineering_systems.integrations",
    )

    for name in package_names:
        package = importlib.import_module(name)
        assert package.__file__ is not None


def test_pytest_covers_all_modules(pytestconfig: pytest.Config) -> None:
    """Keep all source/test roots configured with collision-safe imports.

    Args:
        pytestconfig: Active pytest configuration supplied by pytest.
    """
    assert pytestconfig.getini("testpaths") == [
        "module-01/tests",
        "module-02/tests",
        "module-03/tests",
        "module-04/tests",
        "module-05/tests",
    ]
    assert pytestconfig.getini("pythonpath") == [
        REPOSITORY_ROOT / "module-01/src",
        REPOSITORY_ROOT / "module-02/src",
        REPOSITORY_ROOT / "module-03/src",
        REPOSITORY_ROOT / "module-04/src",
        REPOSITORY_ROOT / "module-05/src",
        REPOSITORY_ROOT / "module-01/tests",
    ]
    assert pytestconfig.getoption("importmode") == "importlib"


def test_distribution_owns_only_the_intended_packages() -> None:
    """Verify installed distribution metadata includes all package roots."""
    top_level = distribution("dm-aiep-modules").read_text("top_level.txt")
    assert top_level is not None
    assert set(top_level.splitlines()) == set(PACKAGE_ROOTS)


@pytest.mark.parametrize("package_name", PACKAGE_ROOTS)
def test_editable_import_outside_repository(
    package_name: str, tmp_path: Path
) -> None:
    """Prove installed imports work without pytest's source-path injection.

    Args:
        package_name: Installed package whose editable mapping is checked.
        tmp_path: Temporary working directory outside the repository.
    """
    script = (
        "import importlib, json, sys; "
        "print(json.dumps(importlib.import_module(sys.argv[1]).__file__))"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, package_name],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    expected = (
        REPOSITORY_ROOT / PACKAGE_ROOTS[package_name] / package_name / "__init__.py"
    )
    assert Path(json.loads(result.stdout)).resolve() == expected.resolve()
