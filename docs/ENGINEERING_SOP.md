# Default Engineering SOP — Production Quality by Default

## Purpose

This document codifies the default engineering standard used for this repository
and the standard intended to be carried forward into future engineering projects.

The governing default is:

> **Unless a project is explicitly declared `DEMO-ONLY` at the outset, build
> toward production-grade quality and production readiness — not merely a
> working demo, tutorial implementation, proof of concept, or something that
> only looks production-style.**

Production quality is **opt-out, not opt-in**.

A project's authoritative requirements define the minimum acceptable scope.
They are the floor, not the ceiling.

## Scope and precedence

This SOP governs engineering decisions in this repository unless a more specific,
human-approved requirement imposes a stronger constraint.

For source-faithful or externally specified work:

1. authoritative requirements remain authoritative;
2. this SOP may extend the implementation but must not silently omit, replace,
   weaken, reinterpret, or contradict those requirements;
3. genuine conflicts or requirement deviations require human review.

For future repositories, this SOP should be adopted at project inception unless
the project is explicitly classified `DEMO-ONLY`.

A repository-local copy governs only that repository. The broader engineering
practice is to carry this standard forward into each new project rather than
assuming one repository can govern another.

## 1. Requirements fidelity

Satisfy authoritative requirements completely and traceably.

Requirements are the floor, not the ceiling.

Enhancements may extend the required implementation when they preserve source
faithfulness, architectural integrity, security, and proportionality.

Do not silently:

- omit required functionality;
- substitute easier functionality for a required capability;
- weaken acceptance criteria;
- reinterpret requirements merely to match the current implementation;
- modify tests or quality rules simply to obtain a passing result.

## 2. Usable product experience

Provide an appropriate operational interface so the system can actually be used,
evaluated, understood, and demonstrated.

Depending on the project, this may be a:

- web UI;
- desktop or mobile UI;
- API;
- CLI;
- dashboard;
- notebook;
- operational workflow;
- other interface appropriate to the system.

Where a human-facing UI is appropriate, include concise guidance explaining:

1. what the capability does;
2. what action the user should take;
3. what result to expect;
4. what the actual result means;
5. what engineering capability the result demonstrates.

The presentation layer must not become a substitute for sound domain
architecture.

## 3. Real functionality

Prefer genuine integrations and realistic execution paths where practical,
valuable, secure, and fiscally responsible.

Mocks, deterministic fixtures, simulators, injected doubles, and offline
transports remain essential engineering tools. They are appropriate for:

- deterministic automated testing;
- failure injection;
- security testing;
- reproducible CI;
- zero-credential startup;
- cost containment.

They must not unnecessarily become the finished product's functional ceiling.

Where a real external integration is part of the intended capability, provide a
safe real path when reasonably achievable and clearly distinguish:

- deterministic evidence;
- mocked evidence;
- adapter/SDK evidence;
- local integration evidence;
- live external-service evidence.

Only genuine successful live execution may be described as live verification.

## 4. Production engineering

Production engineering is part of implementation, not optional polish.

Apply, where relevant:

- explicit architecture and dependency boundaries;
- typed contracts and validation;
- intentional exception handling;
- actionable errors;
- bounded execution;
- retry and timeout policy;
- failure recovery and safe fallback;
- observability;
- operational logging with redaction;
- configuration management;
- maintainability;
- dependency management;
- deterministic testing;
- integration testing;
- adversarial/security testing;
- performance and resource considerations;
- deployment considerations;
- documentation;
- source-to-evidence traceability;
- release verification.

The exact controls must remain proportional to the system's risks and purpose.
Do not add complexity merely to appear sophisticated.

## 5. Security by design

Greater capability requires stronger controls, not weaker ones.

Production capability never justifies weakening:

- credential protection;
- authentication or authorization;
- least privilege;
- trust boundaries;
- tool permissions;
- input validation;
- output validation;
- prompt-injection defenses;
- data protection;
- secret handling;
- execution boundaries.

External content, model output, tool output, retrieved content, memory, and other
untrusted data remain untrusted until validated at the appropriate boundary.

LLM or external-system output must not directly acquire privileged application
authority.

Secrets must not be committed, logged, exposed in errors, placed in prompts or
traces unnecessarily, or returned through application output.

Security controls and expected failure paths require verification appropriate to
the risk.

## 6. Fiscal responsibility

Production quality does not justify uncontrolled spending.

Protect the project **war chest** through appropriate controls such as:

- bounded agent/tool execution;
- token, request, execution, and resource budgets;
- bounded retries;
- deterministic/local testing;
- mocked transports where they provide sufficient test evidence;
- caching where appropriate;
- explicit opt-in for billable verification;
- user-supplied credentials where appropriate;
- zero-key startup where appropriate;
- cost estimation and measurement where useful;
- cost-conscious model/provider selection;
- explicit limits around automated external calls.

Merely possessing a credential must not implicitly authorize a paid call.

Normal tests, imports, startup, and deterministic demonstrations should not
silently incur external charges.

Potentially billable operations should be intentional, bounded, and attributable
to an explicit user, operator, or approved automation decision.

A system capable of unexpectedly generating uncontrolled costs is not
production-grade.

## 7. Evidence-based claims

Engineering claims must not exceed the evidence.

Describe a capability as production-grade, production-ready, secure, reliable,
live, deployed, integrated, or otherwise operationally mature only to the extent
supported by evidence.

Evidence may include:

- automated tests;
- integration tests;
- adversarial/security tests;
- runtime verification;
- live-provider verification;
- deployment evidence;
- observability evidence;
- performance evidence;
- architecture review;
- traceability;
- human review where human authority is required.

Document important limitations explicitly.

A passing deterministic test is not evidence of successful remote delivery.
A mocked SDK transport is not a live provider call.
A UI rendering successfully is not proof that every underlying integration is
production-ready.

## 8. Explicit `DEMO-ONLY` exception

A project may intentionally be a prototype, tutorial, experiment, proof of
concept, or demonstration.

That exception must be explicit.

Declare:

> **DEMO-ONLY**

at project inception, or through an explicit later human decision that records
the scope change.

A `DEMO-ONLY` project may deliberately relax production-readiness requirements,
but must not make unsupported production claims.

Security requirements appropriate to the demonstrated capability still apply.
`DEMO-ONLY` is not permission to expose secrets, perform unsafe actions, or
misrepresent evidence.

## Production-Grade Definition of Done

Unless the project is explicitly `DEMO-ONLY`, functional completion is not
project completion.

Before declaring a project or major milestone complete, evaluate all applicable
gates in this order:

**Requirements → Product Experience → Real Functionality → Reliability →
Security → Cost → Evidence → Deployment**

### Requirements

- Authoritative requirements are satisfied.
- Requirement coverage is traceable where appropriate.
- Enhancements do not weaken or contradict the source contract.

### Product Experience

- The system has an appropriate usable interface.
- A new user or reviewer can understand how to operate it.
- Important functionality can be meaningfully demonstrated.

### Real Functionality

- Real execution paths exist where practical and valuable.
- Mocks/test doubles have not accidentally become the product ceiling.
- Evidence classifications accurately distinguish deterministic, mocked,
  local, adapter, and live behavior.

### Reliability

- Expected failures are bounded and handled intentionally.
- Retry, timeout, fallback, recovery, state, and resource controls are integrated
  where relevant rather than existing only as disconnected demonstrations.
- Failure paths have appropriate automated coverage.

### Security

- Trust and authority boundaries are explicit.
- Credentials and sensitive data are protected.
- Relevant adversarial cases are tested.
- Additional functionality does not bypass established controls.

### Cost

- Paid/resource-consuming operations are bounded.
- Default execution does not incur surprise charges.
- Automated loops cannot create uncontrolled spend.
- Live verification is explicit and proportionate.

### Evidence

- Claims are supported by current evidence.
- Quality gates pass.
- Limitations are documented.
- Production terminology matches the evidence actually obtained.

### Deployment

- Deployment behavior matches the intended operational claim.
- Important production functionality is available in the deployed experience
  where that is part of the project's purpose.
- Deployment-specific security, configuration, and cost boundaries are
  understood and documented.

A project may therefore be **functionally complete but not yet production-grade**.

## Production terminology

Use these terms deliberately:

### Production-grade

The North Star.

Architecture, implementation, reliability, security, maintainability, testing,
observability, and operational controls are engineered to a standard appropriate
for real-world use.

The claim must remain proportional to verified evidence.

### Production-ready

The system has reached an appropriate threshold for its intended deployment
environment, with required operational dependencies and deployment-specific
controls verified.

### Production-style

May describe an intermediate implementation that follows some production
patterns.

It is not the target and must not be used as a substitute for production
readiness.

### Demo-only

An explicit exception whose purpose and limitations are intentionally narrower
than production readiness.

## Engineering lifecycle

For non-demo projects, use this lifecycle unless authoritative requirements
require something stronger:

1. capture authoritative requirements;
2. establish architecture and trust boundaries;
3. define evidence and Definition of Done;
4. implement the smallest sufficient vertical capability;
5. provide an appropriate usable interface;
6. exercise genuine functionality where practical;
7. run fail-fast quality gates;
8. test expected failure and security paths;
9. evaluate reliability and operational behavior;
10. evaluate fiscal exposure;
11. reconcile requirements against implementation;
12. perform the Production-Grade Definition-of-Done review;
13. document limitations;
14. obtain required human approvals;
15. publish/deploy only claims supported by evidence.

## Quality-gate discipline

When Python is used and the repository does not specify stronger gates, prefer
the fail-fast sequence:

1. Ruff;
2. pytest;
3. compileall against the relevant source/application/test directories.

A later passing gate never overrides an earlier failure.

Safe deterministic repairs may be automated.

Unsafe fixes must not be automatically applied.

Tests, security controls, requirements, or quality rules must never be weakened
merely to obtain green status.

## Human authority

Human approval is required for genuine decisions involving matters such as:

- requirement interpretation or deviation;
- architecture exceptions;
- meaningful security tradeoffs;
- expansion of privileged authority;
- acceptance of material production limitations;
- consequential or unexpectedly costly external actions;
- release/publishing decisions where project governance requires approval.

Mechanical verification, deterministic bookkeeping, evidence gathering, and
previously authorized implementation should not be unnecessarily blocked on
human approval.

## Governing principle

The engineering objective is not:

> "Make the demo look production-like."

It is:

> **Build the smallest system that satisfies its requirements while advancing it
> as far toward secure, reliable, fiscally responsible, evidence-backed
> production quality as reasonably achievable.**

Production-grade quality is the North Star.

Security and fiscal responsibility are properties of production engineering,
not exceptions to it.
