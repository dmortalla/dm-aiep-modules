# Module 6 Runtime Foundation

## Scope and Authority

This is the historical foundation record. Current LangGraph execution supersedes
its construction-only limitation in
[LANGGRAPH_COORDINATOR_WORKER.md](LANGGRAPH_COORDINATOR_WORKER.md).
Fixture defaults and Google ADK construction-only behavior remain intact.
CrewAI now executes the separately documented
[deterministic collaborative slice](CREWAI_COLLABORATION.md).

This milestone follows AGENTS.md, the engineering SOP, the 26 frozen source
requirements, Architecture B+, and ADRs 001â€“006. Starting state:
`feature/module-06-architecture` at
`ff179a38209541920d5f10dff147f90eb52603a6`, subject
`build: integrate module 6 dependency foundation`, with a clean worktree.
No architecture or dependency decision changes are introduced.

## Package and Public Boundaries

`src/multi_agent_orchestration` is standalone from Modules 1â€“5:

| Module | Responsibility |
| --- | --- |
| `contracts.py` | Frozen, extra-field-rejecting Pydantic input, limits, runtime IDs, status, task result, candidate output, evidence, validated result, and runtime capabilities |
| `runtime.py` | Application-owned async Runtime protocol: capability information and execute(request) -> candidate output |
| `registry.py` | Explicit fixture/LangGraph/CrewAI/Google ADK selection; lazy SDK construction; no credential selection or fallback |
| `fixture.py` | One fixed offline task result, no instruction evaluation, models, retries, or network |
| `adapters.py` | Private native SDK construction objects; application-owned metadata only; explicit execution refusal |
| `execution.py` | Revalidation, selection checks, cooperative deadline/cancellation, candidate validation, and application-created evidence |
| `errors.py` | Typed, sanitized application errors with lower-level causes retained where appropriate |
| `__init__.py` | Minimal package startup without SDK/provider imports |

The Runtime protocol returns no SDK-specific types. Caller/framework input
crosses application validation before becoming accepted state. Requests are
immutable and contain a UUID workflow identity, UUID task identity, bounded task
instruction, explicit runtime (fixture by default), and execution limits.

The foundation completes one fixture step. `max_steps` accepts strict integers
from 1 to 32; `timeout_ms` accepts strict integers from 1 to 30,000. There are no
retry/model/tool/delegation loops. The deadline cancels cooperative async work;
it is not a sandbox or preemption guarantee for arbitrary blocking adapter code.
The built-in fixture has fixed bounded work. Future SDK execution requires its
own cancellation, resource, concurrency, and provider budget integration.

## Framework Compatibility Evidence

| Adapter | Real native object constructed | Execution status |
| --- | --- | --- |
| LangGraph | StateGraph builder | Not compiled or invoked; explicitly unavailable |
| CrewAI | Static Task definition | No agent, LLM, crew, or kickoff; explicitly unavailable |
| Google ADK | BaseAgent definition | No runner, model, delegation, or distribution; explicitly unavailable |

These objects prove SDK construction compatibility with the accepted locked
versions. They are not fake framework execution and do not satisfy meaningful
framework-use requirements. LangGraph can support later offline graph execution;
that behavior is not implemented here. CrewAI/ADK model-backed integration awaits
application-owned model, policy, workflow, and budget boundaries. No paid/live
provider is needed or authorized by this milestone.

Unknown selection raises UnknownRuntimeError. Missing packages/symbols/metadata
raise RuntimeUnavailableError with an actionable sync instruction. Construction
and invocation failures retain internal causes under ExecutionFailureError.
Unsupported execution never returns a fixture under a framework name.

## Trust, Evidence, and Cost

`execute_workflow` revalidates even preconstructed Pydantic requests/results to
reject model_construct/model_copy bypasses. It checks selected/requested runtime,
workflow/task correlation, completed status, allowed fixture agent, and exact
fixture content. Unknown fields cannot grant authority, choose providers, enable
paid execution, inject policy, or supply trusted evidence.

Successful evidence is built by the application, outside runtime output. It
contains workflow/task UUIDs, requested/actual fixture runtime, completed status,
deterministic_offline mode, one consumed step, configured bounds, and zero
retries/model/external calls. It contains no instruction, raw output, credential,
or arbitrary metadata fields. Repeating the same validated request produces an
identical result/evidence serialization; new default identities separate requests.

Optional runtime injection is a trusted code dependency for testing/integration,
not a field in caller/model data. Adapters are trusted code; their output is not.
No execution provider, external tracing, Prometheus, Grafana, or LangSmith client
is selected. The existing vendor-neutral OTel collection and curated Streamlit
architecture remains unchanged.

Application error messages omit input/output payloads. Chained validation/SDK
causes may retain sensitive input internally: do not expose or indiscriminately
log full tracebacks/causes in a future UI, telemetry, or public error response.
The foundation performs no logging or remote telemetry. Pydantic schemas are
validation boundaries, not authentication or protection from hostile Python code.

## Operation and Tests

Use the existing repository Python 3.12.14 environment. Root `pyproject.toml`
is the authoritative pytest and packaging configuration for Modules 1–6.
`multi_agent_orchestration` is included in the synchronized editable project
package. The redundant Module 6 `pytest.ini` was removed; targeted testing from
Module 6 discovers the parent configuration.

From the repository root, the fail-fast verification sequence is:

```powershell
uv run --locked --offline ruff check .
uv run --locked --offline pytest --basetemp=build/module06-root-integration-20261010
uv run --locked --offline python -m compileall -q module-01 module-02 module-03 module-04/src module-04/tests module-04/examples module-04/app.py module-05/src module-05/tests module-05/app.py module-06/src module-06/tests
git diff --check
```

For targeted testing from Module 6, run `uv run --locked --offline pytest tests`.
The full root suite includes all 81 Module 6 tests. Those tests disable tracing/
telemetry and block/count every non-loopback socket/DNS attempt, including caught
SDK attempts. Loopback remains available for Windows asyncio internals. No keys
are required. Dummy credential tests prove fixture selection and zero-call
behavior are unchanged.

Tests cover schemas, strict limits, nested immutability, sensitive repr exclusion,
repeatability, state separation, credential-independent selection, real SDK
construction, unsupported/missing runtimes, output forgery and Pydantic bypasses,
exception chaining/sanitization, timeout cancellation without retries, caller
cancellation, and source isolation. Final validation results are recorded below.

## Limits and Next Story

All 26 source requirements remain Planned. A fixture task is not sequential
agents, workflow state management, execution tracing, coordinator-worker,
collaboration, distribution, scaling, an operations console, or production
telemetry. No production readiness or deployment claim is made.

Next: implement the smallest bounded LangGraph coordinator-worker vertical slice
with application-owned typed state/transitions, deterministic worker behavior,
validated results, and failure evidence. Keep model/provider integration separate
until explicitly authorized and governed by existing security/cost policy.

## Definition-of-Done Assessment

Requirements: source IDs preserved; framework use and labs not complete.
Product experience: no UI delivered; source operation/test guidance provided.
Real functionality: genuine fixture execution and SDK construction only.
Reliability: single-step bounds, deadline, cancellation, and typed failure tests.
Security: input/output validation, authority-field rejection, sanitized outer errors;
full platform security/adversarial and deployment controls remain unverified.
Cost: no model/remote telemetry execution; zero external attempts in Module 6 tests.
Evidence: only the final quality-gate results justify this bounded milestone.
Deployment: no deployed runtime/platform or production-ready claim.

## Original Runtime-Foundation Verification — 2026-10-10

| Gate/evidence | Result |
| --- | --- |
| Ruff, repository-wide | PASS; initial E501 formatting findings repaired safely; no unsafe fixes |
| Module 6 pytest suite | 81 passed, zero skips/warnings, 8.04 seconds |
| Existing root pytest suite | 2,114 passed, 6 skipped, 3 warnings, 94.91 seconds |
| Combined pytest outcomes across both required invocations | 2,195 passed, 6 skipped, 3 warnings |
| compileall over existing modules plus Module 6 source/tests | PASS; exit 0 |
| git diff --check and new-file whitespace review | PASS; exit 0/no trailing whitespace or missing final newlines |
| Module 6 network guard | PASS; zero non-loopback DNS/connection attempts, including caught SDK attempts |
| Module/source/architecture isolation | PASS; changes confined to Module 6; Modules 1–5 and frozen architecture/ADRs/source unchanged |
| Source requirement identity/status integrity | PASS; all 26 original ID/description/status rows unchanged |
| Dependency integrity | PASS; root pyproject.toml/uv.lock unchanged; uv lock --check --offline and uv pip check passed |

The existing six skips require optional genuine Mem0 support or explicitly
opted-in live-provider verification. The three warnings are existing ChromaDB
legacy embedding-configuration deprecations. No new suite warning remains.
Ruff passed before both final pytest invocations, then compileall passed.
No tests, security controls, quality rules, or source requirements were weakened.

## Root Integration Verification — 2026-10-10

Human authorization permits exactly three additions in
`module-02/tests/test_package_contract.py`: the Module 6 package root and exact
pytest test/source paths. Exact ownership/list equality and existing isolated
installed-import parameterization remain strict; the new root adds one import
case. No Module 2 application behavior or other historical tests changed.

- Root `uv run --locked --offline pytest --collect-only -q`: **2,202 collected**.
- Root `uv run --locked --offline pytest`: **2,196 passed, 6 skipped, 3 existing
  ChromaDB warnings**, 129.70 seconds; includes all 81 Module 6 cases.
- Targeted `uv run --locked --offline pytest tests` from Module 6: **81 passed**,
  16.25 seconds, using parent `pyproject.toml` without local configuration.
- Ruff and compileall over all six modules: PASS; no fixes needed.
- Installed imports for all six packages outside the repository under isolated
  Python: PASS. Locked sync rebuilt only the editable project; sync check, lock
  check, and installed dependency check: PASS. `uv.lock` and dependency constraints
  are unchanged. The cross-drive hardlink fallback only affected copy performance.
- Whitespace and scope checks: PASS. Changes are limited to root package/test
  configuration, the authorized Module 2 contract additions, removal of redundant
  Module 6 pytest configuration, and these two Module 6 documentation records.

Runtime behavior, Architecture B+, ADRs, and all 26 source requirement IDs/statuses
remain unchanged. Root integration does not establish framework execution,
workflow completion, live telemetry, or production readiness.
