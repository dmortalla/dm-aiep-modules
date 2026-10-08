"""Offline checks for the Story 1 package scaffold.

Story 1 introduces no new third-party dependencies; those are added in the
stories that own each integration boundary (BM25, RAGAS, LangSmith,
LangFuse, cross-encoder reranking). Shared packaging/discovery regression
coverage, including the editable-import-outside-the-repository check for
every package root, lives in
``module-02/tests/test_package_contract.py``; this module only verifies
isolated package startup.
"""

import json
import subprocess
import sys


def test_package_import_does_not_load_integrations() -> None:
    """Keep package startup independent of SDKs and credential configuration."""
    script = (
        "import json, sys; import advanced_rag_evaluation; "
        "print(json.dumps(sorted(set(sys.modules) & "
        "{'faiss', 'chromadb', 'pinecone', 'langchain', 'openai', 'streamlit', "
        "'ragas', 'langsmith', 'langfuse', 'sentence_transformers', 'rank_bm25'})))"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert json.loads(result.stdout) == []
