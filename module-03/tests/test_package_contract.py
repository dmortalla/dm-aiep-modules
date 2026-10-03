"""Offline checks for the Story 1 package and dependency foundation."""

import importlib
import json
import subprocess
import sys
from importlib.metadata import distribution

import pytest


def test_package_import_does_not_load_integrations() -> None:
    """Keep package startup independent of SDKs and credential configuration."""
    script = (
        "import json, sys; import rag_engineering_foundations; "
        "print(json.dumps(sorted(set(sys.modules) & "
        "{'faiss', 'chromadb', 'pinecone', 'langchain', 'openai', 'streamlit'})))"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert json.loads(result.stdout) == []


@pytest.mark.parametrize(
    ("distribution_name", "module_name", "public_symbol"),
    [
        ("faiss-cpu", "faiss", "IndexFlatL2"),
        ("chromadb", "chromadb", "EphemeralClient"),
        ("pinecone", "pinecone", "Pinecone"),
        ("langchain", "langchain", "__version__"),
        ("openai", "openai.resources.embeddings", "Embeddings"),
    ],
)
def test_required_dependency_is_installed_and_importable(
    distribution_name: str, module_name: str, public_symbol: str
) -> None:
    """Verify SDK availability without constructing clients or making requests.

    Args:
        distribution_name: Required installed Python distribution.
        module_name: Corresponding importable SDK module.
        public_symbol: Entry point needed by a later integration story.
    """
    assert distribution(distribution_name).version
    assert hasattr(importlib.import_module(module_name), public_symbol)
