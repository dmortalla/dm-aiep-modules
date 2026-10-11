# Module 6 Dependency Compatibility

## Purpose

Record the historical resolution baseline and the accepted repository dependency
foundation. Resolution, installation, import checks, regression evidence, and
feature/runtime integration are distinct evidence classes.

## Supported Python Baseline

- Repository contract: Python >=3.12
- Verified project runtime: Python 3.12.14
- Global development shell observed during research: Python 3.14.7
- Module 6 does not require a Python-version migration.
- Python 3.12 remains the project baseline for implementation and verification.

## Historical Pre-Installation Resolution Probes

The following results predate the repository dependency-foundation milestone;
they are not evidence that the final integrated graph runs on Python 3.14.

### Required Dependency Families

| Dependency family | Python 3.12 resolution | Python 3.14 resolution |
| --- | --- | --- |
| LangGraph | PASS | PASS |
| CrewAI | PASS | PASS |
| Google ADK | PASS | PASS |
| LangSmith | PASS | PASS |
| OpenTelemetry API | PASS | PASS |
| OpenTelemetry SDK | PASS | PASS |
| OpenTelemetry OTLP exporter | PASS | PASS |

## Verification Result

- Python 3.12: 7 of 7 required dependency families resolved successfully.
- Python 3.14: 7 of 7 required dependency families resolved successfully.
- Resolution probes did not install dependencies.
- Repository files were not modified by the compatibility probes.

The Python 3.14 result is supplemental forward-compatibility evidence. It does not redefine the supported project baseline.

## Interpretation

Successful dependency resolution establishes package-metadata compatibility for the tested Python targets. It does not by itself prove runtime interoperability, framework integration correctness, or production readiness.

Runtime compatibility must therefore be verified incrementally after installation through the repository quality gates and Module 6 tests.

## Implementation Guardrails

1. Use the repository-managed Python 3.12 environment for Module 6 implementation.
2. Add framework dependencies deliberately rather than treating resolver success as authorization to install every optional package.
3. Preserve provider-neutral application contracts and keep framework-specific behavior behind runtime adapters.
4. Run Ruff before pytest and compileall after dependency or implementation changes.
5. Treat external framework, provider, and model output as untrusted until validated.
6. Preserve bounded execution, retry, concurrency, timeout, and cost controls.
7. Re-run compatibility analysis if dependency constraints materially change.

## Evidence

The compatibility investigation was performed before dependency installation. Transient research artifacts are retained outside the repository under the project evidence workspace.

Verified research state:

- Project runtime: Python 3.12.14
- Python 3.12 dependency resolution: 7/7 PASS
- Python 3.14 dependency resolution: 7/7 PASS
- Dependencies installed during probes: No
- Repository modified during probes: No

## Repository Dependency Foundation — 2026-10-10

Human authorization: Module 6 dependency-foundation handoff, starting from
`feature/module-06-architecture` at
`5f479a813e1b975c44e1b0af74692dd6c090c6dd`, with a clean worktree.
Architecture B+ and ADR-006 remain frozen.

### Direct Dependency Policy

Change `openai>=3.22.1` to `openai>=3.3.0,<4.0.0`. Add
`crewai==0.193.2`, `langgraph`, `google-adk`, `langsmith`,
`opentelemetry-api`, `opentelemetry-sdk`, and `opentelemetry-exporter-otlp`.
The six unpinned families use the coherent uv lock rather than speculative
project-level version constraints. LangGraph, LangSmith, and some OpenTelemetry
packages were already transitive; declaring them directly records architecture
ownership. No transitive packages are manually pinned.

Preserve `pydantic>=2.13.5`, `python-dotenv>=1.2.4`, `chromadb>=1.5.9`, and
Python `>=3.12`. Exact CrewAI metadata allows `openai>=1.13.3`; the supplied
proof also identified Instructor's `>=2.0.0,<4.0.0` and LiteLLM's `>=1.68.2`
constraints. These do not establish that CrewAI itself requires OpenAI 1.x.
The human approved the repository OpenAI range using the complete disposable
resolution and independent OpenAI 3.3.0 regression evidence.

### Actual Repository Lock

The real lock is resolved against all existing repository constraints and can
differ from the disposable proof. It retains compatible existing locked versions
where possible. The locked graph contains 239 packages.

| Direct dependency | Locked version |
| --- | --- |
| `crewai` | `0.193.2` |
| `langgraph` | `1.2.12` |
| `google-adk` | `2.11.0` |
| `langsmith` | `0.14.3` |
| `opentelemetry-api` | `1.42.1` |
| `opentelemetry-sdk` | `1.42.1` |
| `opentelemetry-exporter-otlp` | `1.42.1` |
| `openai` | `3.3.0` |

Relevant resolver-selected transitive changes include Instructor 1.17.0,
LiteLLM 1.74.9, ONNX Runtime 1.22.0, protobuf 6.33.6, and aligned OpenTelemetry
semantic conventions/exporters. These are lock decisions, not direct pins.
The protected Pydantic, python-dotenv, and ChromaDB constraints are unchanged.

### Prometheus/Grafana Dependency Boundary

No additional direct Prometheus Python client is required by the accepted docs.
The application exports vendor-neutral OpenTelemetry through OTLP to the
Collector/compatible collection boundary; Prometheus exposure/storage belongs
outside domain logic at that boundary. Adding an application-specific exporter
would be an implementation choice beyond this milestone. Grafana is not a
Python dependency. No Collector, Prometheus, Grafana, or deployment configuration
is added.

LangSmith remains specialist AI tracing. Streamlit remains the unified curated
human-facing observation console. No live model calls or remote tracing are
needed for dependency verification. Credential presence does not authorize paid
execution, and runtime output remains untrusted until application validation.

### Evidence and Limits

The validation below passed on the installed graph. This milestone
establishes dependency installation and regression compatibility, not meaningful
framework use, runtime interoperability, telemetry delivery, distributed
execution, or production readiness. Python 3.14 runtime verification of this
integrated graph is not claimed. New dependencies enlarge the transitive graph;
future Module 6 stories must verify framework behavior and bounded security,
resource, telemetry, and cost controls incrementally.

### Integration Validation

Commands used the repository-managed `.venv` Python 3.12.14. uv 0.12.5 resolved
and synchronized the project; the resolver-selected `uv` Python dependency is
separate from that CLI. Initial sandbox interpreter access was denied; uv and
pytest ran outside that boundary. Offline resolution passed; locked sync fetched
one missing Google ADK wheel. Hardlinking across drives fell back to copying.

| Check | Result |
| --- | --- |
| `uv lock --check --offline --python .venv/Scripts/python.exe` | PASS; 239 locked packages |
| `uv sync --locked --offline --check --python .venv/Scripts/python.exe` | PASS; 216 installed packages; would make no changes |
| `uv pip check --python .venv/Scripts/python.exe` | PASS; all installed packages compatible |
| Seven Module 6 dependency families plus OpenAI import smoke | PASS; telemetry disabled; non-loopback sockets/DNS blocked; zero non-loopback attempts |
| `.venv/Scripts/ruff.exe check .` | PASS; no fixes needed |
| `.venv/Scripts/python.exe -m pytest --basetemp=build/module06-foundation-pytest-20261010` | PASS; 2,114 passed, 6 skipped, 3 warnings in 99.60 seconds |
| `.venv/Scripts/python.exe -m compileall -q module-01 module-02 module-03 module-04/src module-04/tests module-04/examples module-04/app.py module-05/src module-05/tests module-05/app.py` | PASS; exit 0 |
| `git diff --check` | PASS; exit 0 |
| Scope and configuration audit | PASS; only the four intended dependency/documentation files changed |

The six skips preserve existing conditions: four genuine Mem0 checks require
its optional library, and two live-provider checks require explicit opt-in and
credentials. No live-provider verification was performed. The three warnings
are existing ChromaDB legacy embedding-configuration deprecations.
The first import socket guard also blocked loopback and produced Windows asyncio
cleanup warnings; the corrected guard allowed loopback only and completed cleanly.

Modules 1–5 files, Module 6 source requirements/traceability, Architecture B+,
and ADRs 001–006 are unchanged. No feature implementation, credentials, paid
provider enablement, infrastructure, or deployment changes are included.

### Definition-of-Done Assessment for This Bounded Milestone

Requirements: direct dependency policy and all 26 frozen IDs preserved.
Product experience: the unified curated Streamlit design is unchanged; no new UI.
Real functionality: locked install/import and existing regression evidence only.
Reliability: existing regression gates pass; new framework execution is not verified.
Security: no source/authority changes; offline import evidence does not replace
future adversarial or supply-chain review.
Cost: no live inference or remote trace verification authorized by this milestone.
Evidence: the uv, import, lint, test, compilation, whitespace, and isolation checks pass.
Deployment: no deployed framework/telemetry integration or production-ready claim.
