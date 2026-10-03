# Story 1: Package scaffold and dependency integration

The implementation follows the source requirements and architecture frozen at
commit `8957379`. This story establishes installation and import readiness only;
all source-level runtime integration requirements remain pending.

## Foundation

The package lives at `module-03/src/rag_engineering_foundations`. Its initializer
does not load SDKs, initialize clients, or access credentials. No domain contracts
or errors are introduced before the stories that own their validation and failure
boundaries. Root setuptools and pytest configuration include all three modules;
the existing repository-wide Ruff configuration already covers the new Python
files without changing its rules.

## Dependencies

The shared project adds these direct dependencies, resolved on Python 3.12:

| Package | Minimum version | Purpose |
| --- | --- | --- |
| `faiss-cpu` | 1.15.1 | CPU FAISS runtime for the required vector-store integration |
| `chromadb` | 1.5.9 | ChromaDB runtime and client |
| `pinecone` | 10.0.0 | Current Pinecone SDK for the later explicit remote adapter |
| `langchain` | 1.4.3 | LangChain runtime for the later RAG integration boundary |

The existing `openai>=3.22.1` SDK exposes the Embeddings resource and is retained
for the required OpenAI Embeddings adapter. The existing `langchain-core` remains
unchanged for Module 2. Provider wrappers and unrelated direct dependencies are
unnecessary at this stage. `uv.lock` records the transitive dependency resolution;
existing locked package versions are preserved.

Package references: [FAISS CPU](https://pypi.org/project/faiss-cpu/),
[ChromaDB](https://pypi.org/project/chromadb/),
[Pinecone](https://pypi.org/project/pinecone/), and
[LangChain](https://pypi.org/project/langchain/).

## Verification scope

Module 3 tests check isolated package startup and five required dependency import
surfaces without constructing clients or making requests. Existing shared package
tests now cover three roots, retaining exact distribution ownership, pytest
discovery, and isolated editable imports outside the repository. No Module 1 or
Module 2 application behavior changes.

These checks do not establish genuine vector retrieval, embeddings generation,
LangChain orchestration, remote-service behavior, or complete source evidence.
Those belong to Stories 2–10, along with the Streamlit UI and full traceability.

On October 3, 2026, the fail-fast gates passed on Python 3.12.14:

1. `uv run ruff check .` — exit 0, all checks passed.
2. `uv run pytest` — exit 0, 464 passed in 56.38 seconds (457 existing
   cases, six new Module 3 cases, one additional shared editable-import case).
3. `uv run python -m compileall module-01/src module-01/tests module-01/app.py
   module-02/src module-02/tests module-02/app.py module-03/src module-03/tests`
   — exit 0.
4. `git diff --check` — exit 0, no whitespace errors.

No quality gate failed and no post-failure repair was required. Installation used
uv's automatic copy fallback because cache and repository are on different drives.
No commit was made; the working tree is left for human review.

## Training observations

- **Agent policy:** Read frozen sources before implementation; preserve scope and
  trust boundaries; distinguish dependency readiness from runtime evidence.
- **Reusable skill:** Extend shared package discovery while checking editable
  imports outside pytest's injected source paths. Evolve exact shared packaging
  expectations without removing regression checks for accepted modules.
- **Deterministic automation:** Resolve and lock dependencies on the target Python
  version; check SDK imports offline; run quality gates in fail-fast order and
  repeat the sequence after a repair.
- **Human authority:** Frozen source/architecture changes, unresolved requirement
  ambiguity, and final acceptance remain human decisions. No policy or skill files
  are created from this single observation.
