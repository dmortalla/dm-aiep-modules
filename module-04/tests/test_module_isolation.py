"""Rule 44 guard: Module 4 must never depend on an earlier academic module.

Each academic module is standalone. This test statically parses every Module 4
Python file (runtime source, tests, examples, and the Story 11 dashboard
``app.py``) and fails if any of them imports an earlier module's package,
whether or not that import would happen to execute during the test run.
Further checks confirm that importing every Module 4 runtime module, and the
dashboard app, loads none of those packages transitively.
"""

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
SURFACES = ("src", "tests", "examples")
APP_FILE = MODULE_ROOT / "app.py"
FORBIDDEN = frozenset(
    {
        "ai_engineering_foundations",  # Module 1
        "prompt_engineering_systems",  # Module 2
        "rag_engineering_foundations",  # Module 3
    }
)
_DYNAMIC_IMPORTERS = frozenset({"import_module", "__import__", "find_spec"})


def imported_packages(source: str) -> set[str]:
    """Return top-level package names imported by one Python source text.

    Covers ``import x``, ``from x import y``, and string-literal dynamic
    imports such as ``importlib.import_module("x.y")``. Relative imports stay
    inside the importing package and are ignored.
    """
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else (
                func.id if isinstance(func, ast.Name) else None
            )
            if (
                name in _DYNAMIC_IMPORTERS
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                found.add(node.args[0].value.split(".")[0])
    return found


def module_4_python_files() -> list[Path]:
    """Return every Module 4 solution Python file: three surfaces plus app.py."""
    return sorted(
        [
            path
            for surface in SURFACES
            for path in (MODULE_ROOT / surface).rglob("*.py")
            if "__pycache__" not in path.parts
        ]
        + [APP_FILE]
    )


@pytest.mark.parametrize(
    "snippet",
    [
        "import rag_engineering_foundations",
        "from rag_engineering_foundations.chunking import DocumentChunk",
        "import prompt_engineering_systems.templates as t",
        "from ai_engineering_foundations import client",
        "import importlib\nimportlib.import_module('rag_engineering_foundations.x')",
        "__import__('prompt_engineering_systems')",
        "def lazy():\n    from rag_engineering_foundations import errors",
    ],
)
def test_guard_detects_every_import_form(snippet: str) -> None:
    """The guard itself must catch the forms that caused the original incident."""
    assert imported_packages(snippet) & FORBIDDEN


def test_guard_ignores_relative_and_third_party_imports() -> None:
    source = "from .corpus import CorpusChunk\nimport chromadb\nimport pinecone\n"
    assert not imported_packages(source) & FORBIDDEN


def test_guard_scans_all_three_surfaces() -> None:
    files = module_4_python_files()
    for surface in SURFACES:
        assert any(path.is_relative_to(MODULE_ROOT / surface) for path in files)
    assert Path(__file__).resolve() in files


def test_guard_scans_the_dashboard_app() -> None:
    assert APP_FILE.is_file()
    assert APP_FILE in module_4_python_files()


def test_no_module_4_file_imports_an_earlier_academic_module() -> None:
    violations = {
        str(path.relative_to(MODULE_ROOT)): sorted(
            imported_packages(path.read_text(encoding="utf-8")) & FORBIDDEN
        )
        for path in module_4_python_files()
    }
    violations = {path: names for path, names in violations.items() if names}
    assert violations == {}


def test_importing_every_runtime_module_loads_no_earlier_academic_module() -> None:
    """Catch transitive loading too, in a clean interpreter."""
    package_root = MODULE_ROOT / "src"
    modules = sorted(
        ".".join(path.relative_to(package_root).with_suffix("").parts).removesuffix(
            ".__init__"
        )
        for path in (package_root / "advanced_rag_evaluation").rglob("*.py")
        if "__pycache__" not in path.parts
    )
    script = (
        "import importlib, json, sys\n"
        f"for name in {modules!r}:\n"
        "    importlib.import_module(name)\n"
        f"print(json.dumps(sorted({{m.split('.')[0] for m in sys.modules}}"
        f" & set({sorted(FORBIDDEN)!r}))))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
        timeout=180,
    )
    assert json.loads(result.stdout.strip().splitlines()[-1]) == []


def test_importing_the_dashboard_app_loads_no_earlier_academic_module() -> None:
    """Import app.py without running its page, in a clean interpreter."""
    script = (
        "import importlib.util, json, sys\n"
        f"spec = importlib.util.spec_from_file_location('m4_app', {str(APP_FILE)!r})\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(module)\n"
        f"print(json.dumps(sorted({{m.split('.')[0] for m in sys.modules}}"
        f" & set({sorted(FORBIDDEN)!r}))))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
        timeout=180,
    )
    assert json.loads(result.stdout.strip().splitlines()[-1]) == []
