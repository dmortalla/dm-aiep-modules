# Module 2 Architecture

## Module

**Prompt Engineering & Structured Output Systems**

## Architectural Goal

Implement the authoritative Module 2 source requirements as an independently
demonstrable system while preserving the already-published Module 1 architecture
and behavior.

Module 2 must remain source-faithful while using production-oriented separation
of concerns, validation, testing, observability, safety boundaries, and a
runnable demonstration UI.

## Repository Strategy

Module 1 is already published and must not be reorganized merely to make the
repository structurally symmetrical.

The repository should evolve from a Module-1-specific Python configuration into
a multi-module configuration that supports both modules without breaking
existing Module 1 imports, tests, or runtime behavior.

Target layout:

    module-01/
        src/
            ai_engineering_foundations/

    module-02/
        app.py
        docs/
            SOURCE_REQUIREMENTS.md
            ARCHITECTURE.md
        src/
            prompt_engineering_systems/
        tests/

The root `pyproject.toml` remains the shared dependency and tooling authority.

## Module 2 Package Boundaries

The package `prompt_engineering_systems` should use focused components whose
exact filenames may evolve during implementation while preserving these
responsibilities.

### Prompt Construction

Responsible for:

- prompt anatomy
- instruction hierarchy
- context engineering
- role prompting
- few-shot prompting
- chain-of-thought concepts
- tree-of-thought concepts
- self-consistency
- ReAct prompting
- LangChain PromptTemplate integration

Prompt construction must remain separate from UI concerns.

### Structured Output

Responsible for:

- typed output contracts
- Pydantic models
- JSON schema generation/enforcement
- output validation
- malformed-output failure handling
- OpenAI JSON Mode integration

Model output is untrusted until successfully validated.

### Evaluation

Responsible for:

- repeatable prompt evaluation workflows
- evaluation cases
- evaluation results
- structured evaluation evidence
- PromptLayer integration

Evaluation logic must not depend on the Streamlit UI.

### Safety and Adversarial Testing

Responsible for:

- prompt-injection defense
- jailbreak detection
- safety boundaries
- bounded prompt-injection simulation
- repeatable red-team cases

Untrusted prompt/model content must never acquire application authority.

Adversarial demonstrations must remain safe, local/bounded where appropriate,
and must not expose credentials or privileged behavior.

### Provider / Integration Boundary

External systems such as OpenAI, LangChain, and PromptLayer must be isolated
behind clear integration boundaries so that:

- tests can run without mandatory live API calls;
- external failures can be translated into actionable domain errors;
- credentials are not logged or exposed;
- live verification can be performed separately from deterministic tests.

### Demonstration UI

`module-02/app.py` provides the runnable presentation layer.

The UI should allow a reviewer to directly inspect and demonstrate meaningful
Module 2 capabilities, including structured prompting, structured output/schema
validation, evaluation, and bounded safety/adversarial behavior.

The UI must call package functionality rather than duplicate business logic.

## Dependency Direction

Preferred dependency direction:

    Streamlit UI
         |
         v
    Application / workflow services
         |
         +-------------------+
         |                   |
         v                   v
    Prompt system       Evaluation system
         |                   |
         v                   v
    Structured output   Safety controls
         \                   /
          \                 /
           v               v
          External integration boundaries

Core domain models and validation must not depend on Streamlit.

## Python Engineering Standards

All Python implementation must follow the standards established in
`SOURCE_REQUIREMENTS.md`, including:

- Google-style docstrings for modules, classes, public functions, and public
  methods where appropriate;
- `Args`, `Returns`, and `Raises` sections when applicable;
- type hints throughout public interfaces;
- intentional exception handling at genuine failure boundaries;
- specific and actionable domain errors;
- exception chaining where appropriate;
- tested expected failure paths;
- no silent blanket exception swallowing.

## Testing Strategy

Module 2 requires deterministic tests covering at least:

- prompt construction and technique behavior;
- PromptTemplate integration;
- Pydantic models and typed outputs;
- JSON schema validation;
- malformed structured output;
- OpenAI JSON Mode request construction/integration boundary;
- evaluation workflow behavior;
- PromptLayer integration boundary;
- prompt-injection defense;
- jailbreak detection;
- safety boundaries;
- red-team cases;
- UI contract behavior;
- external integration failure paths.

Tests must not require live credentials for the normal quality gate.

Live provider/integration verification is separate evidence where required.

## Quality Gates

Quality gates are fail-fast:

1. `uv run ruff check .`
2. `uv run pytest`
3. `uv run python -m compileall` against the relevant source, application,
   and test directories.

A later passing gate does not override an earlier failure.

Safe deterministic Ruff fixes may be automated before the formal gate.
Unsafe fixes must never be applied automatically.

## Self-Healing Boundary

The future automated builder should:

1. detect a failed gate;
2. classify the failure;
3. apply deterministic safe repair when available;
4. otherwise provide the exact diagnostic and relevant implementation context
   to a coding-agent repair loop;
5. bound repair attempts;
6. rerun the failed gate;
7. rerun the complete fail-fast sequence before declaring success.

Tests, source requirements, and quality rules must not be weakened merely to
obtain green status.

## Source Traceability

Every requirement ID in `SOURCE_REQUIREMENTS.md` must ultimately map to
implementation evidence and verification evidence.

Module completion requires both:

- green engineering quality gates; and
- complete source-to-evidence traceability.

Neither substitutes for the other.

## Agent Automation Architecture

The future module-lifecycle automation will support both coding agents:

### Codex

Codex will operate under repository engineering policy expressed through
`AGENTS.md`.

### Claude Code

Claude Code will operate under equivalent repository engineering policy
expressed through `CLAUDE.md`.

### Shared Skills

Large procedural workflows should not be independently duplicated across the
two agent instruction files.

Where repeated evidence supports abstraction, reusable provider-neutral
procedures should be implemented as relevant `SKILL.md` workflows.

Candidate skills include source-requirement extraction, architecture review,
implementation, quality-gate execution, failure classification, bounded repair,
security review, source traceability, and release verification.

These skill boundaries remain provisional until repeated module evidence
justifies extraction.

## Automation Responsibility Model

Module-development observations should continue to be classified into four
categories:

1. **Agent policy**
   Persistent non-negotiable rules shared by `AGENTS.md` and `CLAUDE.md`.

2. **Reusable skill**
   Procedural workflows suitable for provider-neutral `SKILL.md` files.

3. **Deterministic automation**
   Mechanical operations better enforced by scripts and tooling.

4. **Human authority**
   Source interpretation, architecture exceptions, security decisions, and
   requirement deviations requiring explicit human judgment.

## Architecture Invariants

1. Preserve published Module 1 behavior.
2. Module 2 source requirements remain authoritative.
3. UI code must not become the domain implementation.
4. Model and external content remains untrusted until validated.
5. LLM output cannot directly acquire privileged application authority.
6. Normal automated tests must not require live credentials.
7. Secrets must not be committed, logged, or included in model prompts/results.
8. External integrations require explicit boundaries and actionable errors.
9. Source completeness and test success are independently verified.
10. Source deviations require explicit human approval.

## Definition of Done for Architecture Phase

- [x] Authoritative source requirements captured.
- [x] Traceable requirement IDs established.
- [x] Existing Module 1 architecture inspected.
- [x] Existing Module 1 quality baseline verified.
- [x] Module 2 package boundary defined.
- [x] Structured-output boundary defined.
- [x] Evaluation boundary defined.
- [x] Safety/adversarial boundary defined.
- [x] External integration boundary defined.
- [x] Runnable UI boundary defined.
- [x] Python engineering standards incorporated.
- [x] Quality-gate policy defined.
- [x] Self-healing boundary defined.
- [x] Codex / Claude / shared-SKILL automation model documented.
- [x] Human architecture approval.

