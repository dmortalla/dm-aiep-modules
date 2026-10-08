# Story 1: Source freeze, approved architecture, and package scaffold

The implementation follows the source requirements and architecture frozen in
this story, built on repository baseline `fcd9c8eb446df57fe609e47d52700250c512b59e`
on `main`. This story establishes requirement freeze, architecture freeze, and
installation/import readiness only; all Module 4 source-level runtime
integration requirements (`M4-*`) remain Pending.

## Scope

- Freeze [SOURCE_REQUIREMENTS.md](SOURCE_REQUIREMENTS.md): 29 stable Module 4
  requirement IDs, all `Pending`.
- Freeze [ARCHITECTURE.md](ARCHITECTURE.md), including the eight approved
  human resolutions from the prior architecture-review turn.
- Create the `module-04/src/advanced_rag_evaluation` package scaffold. Its
  initializer does not load SDKs, initialize clients, or access credentials.
  No domain contracts or errors are introduced before the stories that own
  their validation and failure boundaries (matching Module 3's Story 1
  precedent).
- Register `module-04/src` and `module-04/tests` in the root
  `pyproject.toml` pytest/setuptools configuration, alongside the existing
  Module 1-3 roots.
- Extend the existing shared packaging-contract test
  (`module-02/tests/test_package_contract.py`) to include
  `advanced_rag_evaluation` in `PACKAGE_ROOTS`, `testpaths`, and `pythonpath`,
  so its editable-import-outside-the-repository coverage applies to Module 4
  without a duplicate test.
- Add `module-04/tests/test_package_contract.py` with an isolated-import
  check confirming the package loads no SDK (including Module 4's future
  BM25/RAGAS/LangSmith/LangFuse/cross-encoder dependencies, named explicitly
  so the check fails loudly once those are introduced without boundary
  discipline).

## Explicitly excluded from this story

BM25, hybrid retrieval, reranking, context filtering, caching, dynamic
retrieval, latency/cost measurement, RAGAS, LangSmith, LangFuse, failure
analysis, the `HybridRagResult` orchestration, and the Streamlit UI/dashboard
are not implemented. No new third-party dependency is added in Story 1;
dependencies are added in the stories that own each integration boundary.

## Dependencies

No new dependency was added. `uv sync` was re-run only to register the new
editable `advanced_rag_evaluation` package mapping; `uv.lock` records no
package-version change.

## Verification scope

Module 4 tests check isolated package startup only: that importing
`advanced_rag_evaluation` loads none of Module 3's or the future Module 4
integrations' SDKs, and (via the extended shared test) that the package
resolves through the installed editable distribution, not through pytest's
injected source paths. No Module 1, Module 2, or Module 3 application
behavior changes; their source files were not edited.

These checks do not establish BM25, hybrid retrieval, reranking, RAGAS,
LangSmith, LangFuse, or any other Module 4 source requirement. Those belong
to Stories 2-11, along with the Streamlit UI/dashboard and full traceability.

## Results — October 5, 2026

Fail-fast gate sequence, root `pyproject.toml` quality-gate order:

1. `uv run ruff check .` — exit 0, all checks passed.
2. `uv run pytest` — **1 failed, 1055 passed, 5 warnings in 62.58s.** The one
   failure, `module-03/tests/test_closeout.py::test_frozen_architecture_and_module_roadmap`,
   is a **pre-existing failure unrelated to this story**: it was reproduced
   identically against a clean stash of the unmodified baseline commit before
   any Story 1 file was created or edited. It asserts that `README.md`
   contains a specific Module 3 release-status table row that is not present
   in the current `README.md`; neither `README.md` nor any Module 3 file was
   touched during that initial run. The repair was initially deferred for
   human review because it required semantic changes outside the original
   Story 1 scaffold scope. Explicit human authorization subsequently permitted
   the repair: the Module 3 closeout test was aligned with the already-published
   Module 3 release state. The release action created/published the tag;
   `fcd9c8e` subsequently recorded that release in the README.
   `uv run pytest module-04 -q` in isolation: **1 passed**.
3. `uv run python -m compileall module-01/src module-01/tests module-01/app.py
   module-02/src module-02/tests module-02/app.py module-03/src
   module-03/tests module-03/app.py module-04/src module-04/tests` — exit 0.
4. `git diff --check` — exit 0, no whitespace errors.

The initial results above are retained as the audit trail, not the final
acceptance outcome. After the explicitly authorized Module 3 semantic repair,
Story 1's final acceptance baseline was **1056 passed / 0 failed**. Later
Story 2–6 suite totals do not replace this historical baseline.

No Ruff finding required a fix (mechanical or otherwise); no gate repair was
performed on Module 4's own additions. The pre-existing Module 3 closeout
assertion was repaired only after explicit human authorization.

## Training observations

- **Agent policy:** Freeze requirements and architecture, including every
  human-approved resolution, as a single reviewable commit-ready change
  before any runtime code; keep Story 1 strictly to scaffold/discovery, never
  front-loading later-story dependencies "for convenience."
- **Reusable skill:** Extend the existing shared `PACKAGE_ROOTS`/
  `testpaths`/`pythonpath` contract test to cover a new module root instead
  of duplicating editable-import-outside-repository coverage per module;
  keep each module's own `test_package_contract.py` scoped to its own
  SDK-isolation check only.
- **Deterministic automation:** `uv sync` to register a new editable package
  mapping; run quality gates in fail-fast order; when a gate failure is
  found, first reproduce it against the clean baseline (e.g. `git stash`) to
  classify it as pre-existing versus newly introduced before deciding whether
  a repair is in scope.
- **Human authority:** Repairing the pre-existing
  `test_frozen_architecture_and_module_roadmap` README mismatch required a human
  decision outside Story 1's original authorized scope. Explicit human
  authorization permitted that semantic repair to match the already-published
  Module 3 release state; it did not create or publish a new release.
  No policy, skill, or
  `AGENTS.md`/`CLAUDE.md`/`SKILL.md` file is generalized from this single
  story.
