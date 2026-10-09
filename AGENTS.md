# AGENTS.md

## Purpose

This file defines repository-level policy for Codex and other compatible coding
agents operating in this repository.

## Authority

The canonical engineering standard is:

- [`docs/ENGINEERING_SOP.md`](docs/ENGINEERING_SOP.md)

Read and follow that document before planning, implementing, reviewing, repairing,
or declaring engineering work complete.

Authoritative project/module source requirements remain the functional contract.
The engineering SOP extends those requirements but must not silently replace,
omit, weaken, reinterpret, or contradict them.

## Default project classification

Unless explicit human-approved project documentation declares `DEMO-ONLY`,
assume the target is production-grade quality and production readiness.

Do not treat successful functionality, passing tests, or a runnable UI alone as
proof that work is complete.

Apply the Production-Grade Definition of Done in `docs/ENGINEERING_SOP.md`.

## Mandatory policy

1. Preserve requirements fidelity.
2. Prefer the smallest sufficient architecture.
3. Keep UI/presentation concerns separate from domain logic.
4. Prefer genuine functionality where practical, secure, and fiscally
   responsible.
5. Keep deterministic/mock evidence distinct from live evidence.
6. Treat external, model, tool, retrieved, and memory output as untrusted until
   validated.
7. Never grant LLM output privileged authority merely because the model proposed
   an action.
8. Never expose, commit, log, or unnecessarily propagate credentials.
9. Bound retries, execution, external calls, and cost exposure.
10. Do not allow credential presence alone to trigger paid operations.
11. Do not weaken tests, security controls, requirements, or quality rules to
    obtain green status.
12. Make production claims only when supported by evidence.
13. Preserve standalone module boundaries where the repository requires them.
14. Escalate genuine requirement, architecture, security, authority, or material
    cost decisions to the human.
15. Do not block deterministic work on unnecessary approval when authority has
    already been granted.

## Quality gates

Use repository-specific gates when defined.

For Python work without a stronger local rule, use fail-fast:

1. Ruff
2. pytest
3. compileall

A later passing gate does not override an earlier failure.

## Completion

Before recommending release or declaring a major milestone complete, explicitly
evaluate:

**Requirements → Product Experience → Real Functionality → Reliability →
Security → Cost → Evidence → Deployment**

Functional completion may be reported separately from production-grade
completion.

## Provider-neutral alignment

`AGENTS.md` and `CLAUDE.md` must remain semantically aligned on mandatory
engineering policy.

Detailed reusable procedures may later move into provider-neutral `SKILL.md`
workflows when repeated evidence justifies that abstraction.
