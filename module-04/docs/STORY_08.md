# Story 8 — LangSmith tracing

Status: implemented for independent human review; Stories 1–7 remain accepted.
Authority: SOURCE_REQUIREMENTS.md, frozen ARCHITECTURE.md and its approved
Story 5 amendment, then accepted Story 6/7 evidence contracts.

## Requirement evidence

- **M4-OBS-01 / M4-TOOL-02:** `observability/langsmith_adapter.py` invokes
  genuine LangSmith 0.14.3 `Client.create_run` and `Client.update_run`. Tests spy
  on the real public method without replacing its implementation and inspect
  the SDK's serialized HTTP bodies in an injected Requests adapter.
- **M4-LAB-04:** `uv run python module-04/examples/langsmith_tracing_demo.py`
  emits a workflow root, two measured-stage children, and three completions:
  six SDK requests. Its subprocess contract blocks outbound socket connections.
  Story 11 owns the future UI presentation; no UI completion is claimed here.

## Integration and dependency decision

The root manifest and uv.lock were inspected before implementation. The already
resolved transitive LangSmith 0.14.3 satisfies this boundary. No dependency or
lockfile changes were made by Story 8; Requests is already resolved with the SDK.
The client is loaded lazily on explicit tracer construction. Root package and
adapter imports do not initialize LangSmith. The fixed invalid HTTPS endpoint,
fixture API key, supplied server information, synchronous non-batched execution,
explicit sampling rate, and offline transport keep gates credential-free.
The SDK installs session adapters during construction; the application mounts
its offline adapter afterward. No SDK source is patched or serialization replaced.

This implementation intentionally exposes only offline tracing. There is no
live verification path, credential loader, automatic fallback, or remote delivery
claim. Evidence is `deterministic_offline`; `remote_delivery_verified` is always
false. UUIDs and SDK wall timestamps vary; request structure and numeric fixture
summaries are deterministic. This is integration evidence, not production latency,
remote ingestion, real semantic evaluation quality, or SaaS availability evidence.

## Security and provenance

Raw prompts, answers, references, chunk content, source/case identifiers, stage
names, model identifiers, judge prompts/completions, caller metadata/tags, and
exception messages are excluded before SDK invocation. Metadata/tags must have
bounded primitive shapes and are then discarded, including injection-shaped
endpoint/key/import/execution instructions. Only validated numeric timing/score
summaries, fixed names, sequence numbers and fixed evidence classifications leave
the application. Arbitrary destinations, credentials, imports, filesystem paths,
tracing enablement, or executable behavior cannot derive from trace content.
Requests environment/proxy inheritance is disabled. Both URL schemes are mounted
on the offline adapter. Tests block sockets and supply hostile ambient SDK settings.

Original Story 6 LatencyReport and Story 7 EvaluationResult objects, including
original chunk identity and provenance, remain unchanged and repr-hidden locally.
Telemetry deliberately carries summaries rather than reconstructing provenance.
SDK exceptions return nonfatal unsuccessful evidence and a fixed warning, retaining
an actionable domain exception chained to the actual SDK cause. The cause is
available for deliberate local debugging and may contain sensitive SDK details;
it is not logged or serialized. Partial emission is possible on mid-workflow
failure, and success never attests remote delivery. The SDK timeout is configured
at 1000ms; injected timeout failures are tested. No hard cancellation of an
arbitrarily blocking synchronous transport is claimed. No failure-analysis
vocabulary or Story 9 implementation is introduced.

## Tests and repairs

24 new tests cover genuine public SDK execution/serialization, root/child IDs,
completion payloads, latency/score propagation, retained evaluation/chunk identity,
content exclusion, malformed annotations and evidence, socket/credential isolation,
injection-shaped annotations, nonfatal timeout/connection/unexpected failures,
exception chaining, sanitized logs/repr, truthful evidence labels, transport/type
rejection, import isolation, and the runnable subprocess demonstration.

Bounded repairs were limited to new Story 8 files: safe Ruff import cleanup and
formatting; correcting the post-construction offline adapter mount order after
an initial invalid-host connection failure; and permitting only Windows asyncio's
internal socketpair construction in the evaluation test network guard, following
the accepted Story 7 test pattern. No existing tests, source, frozen architecture,
requirements, dependency versions, or accepted contracts were changed.
The first full suite under the sandbox had 1537 passed / 43 setup errors caused
by access denial to existing pytest temp directories, not assertion failures.
The formal sequence was restarted with filesystem access for those test directories.

## Quality gates

Final results are recorded below after the complete fail-fast sequence.

## Training observations and human authority

- **Agent policy:** inspect the installed SDK's initialization behavior before
  assuming an injected session preserves its adapter; never promote offline
  acceptance to remote-service evidence.
- **Reusable provider-neutral skill:** retain upstream evidence by identity locally,
  emit minimal numeric summaries, and inject transport beneath genuine SDK methods.
- **Deterministic automation:** spy on public SDK calls while inspecting serialized
  payloads, block outbound connections, test executable labs and inherited settings.
- **Human authority:** no prerequisite conflict or accepted behavior repair was
  required. Independent human acceptance is outstanding. UI/later orchestration,
  live credentials and remote ingestion verification remain later explicit work.

No commit, merge, tag, release, or Story 9 work was performed.

### Final gate results — October 5, 2026

1. `uv run ruff check .` — exit 0, all checks passed.
2. `uv run pytest` — exit 0, **1580 passed / 0 failed**, 3 existing ChromaDB
   deprecation warnings, 36.40 seconds; accepted 1556 baseline + 24 new cases.
3. `uv run python -m compileall module-01 module-02 module-03 module-04` —
   exit 0, compilation successful.
4. `git diff --check` — exit 0; existing LF-to-CRLF normalization notices only.
   Module 4 is still untracked in the starting repository, so Git's ordinary
   diff check does not inspect its new files; Ruff/compilation cover Python.

Story 8 added exactly five files: observability/__init__.py,
observability/langsmith_adapter.py, examples/langsmith_tracing_demo.py,
tests/test_langsmith_tracing.py, and docs/STORY_08.md. Pre-existing working-tree
changes remain intact. The lab executed directly with success=True, six captured
SDK requests and two children; its socket-blocked subprocess test also passed.
