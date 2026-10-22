# Module 6 operations console

Run from the repository root after synchronizing the accepted environment:

```powershell
uv sync --locked --offline
uv run --locked --offline python module-06/run_console.py
```

Open the loopback URL the launcher prints, normally `http://127.0.0.1:8501`. The
launcher binds to loopback, disables Streamlit usage analytics and automatic
browser launch, suppresses detailed browser exception output and limits
WebSocket messages to 1 MB. No credentials are needed. Do not expose this review console
publicly; authentication, multi-user deployment and aggregate capacity are not
implemented or verified.

Choose one of the eight demonstrations explicitly, enter synthetic text and
select **Run demonstration**. The page explains what each run proves and how to
try bounded failures. Start with eight steps and a 30,000 ms deadline. Text over
4,096 characters, steps outside 1–32 and deadlines outside 1–30,000 ms are
rejected by the application service on submit; nothing is adjusted or run. Fixture,
all four LangGraph choices, CrewAI collaboration, Google ADK orchestration and
real local two-process ADK distribution use their accepted services unchanged.

Results show validated application evidence, local trace references, role
provenance, workflow latency and available call counters. Tokens, monetary cost,
provider billing and remote observability are labeled unavailable. No live
model/provider calls, paid execution or remote telemetry delivery is enabled.

Recent results are limited to eight temporary views in each browser session.
Clearing results removes those views. Refreshing or selecting controls does not
execute; successful and failed runs remain distinct. Input text is not copied
into result history or telemetry. Use synthetic text rather than secrets.

[Console design and verification](docs/OPERATIONS_CONSOLE.md) records security,
scope, acceptance evidence and limitations. The console does not complete the
module or its requirements; all 26 source requirements remain Planned.

[Local-model provider adapter](docs/LOCAL_MODEL_ADAPTER.md) documents the additive
offline implementation candidate and synthetic process-runtime verification.
One separately authorized post-repair real Ollama response was verified at the
accepted adapter baseline; this does not verify the three-role workflow. The
console still offers the eight deterministic demonstrations plus the synthetic
canonical live workflow demonstration; no real canonical live control is added.

[Canonical live workflow candidate](docs/CANONICAL_LIVE_WORKFLOW.md) documents the
application API for Researcher → Analyst → Critic and its synthetic offline
verification. Real canonical execution requires independent offline acceptance
and fresh human HITL; no live console control is added. The first authorized
live run failed closed at the Researcher (malformed output after one repair).
After the structured-output remediation, a second authorized run completed one
bounded real Researcher → Analyst → Critic execution (3 calls, 0 repairs,
0 retries). Its Analyst assessment reached the 400-character maximum and
appeared incomplete (cause unproven), so an offline prose-completeness candidate
follows; that candidate is **not yet live-verified**.

The console also has a separate **canonical live workflow (synthetic)**
demonstration: it runs the accepted canonical workflow through the supervised
live process path with a fixed module-level synthetic gateway, so no real
provider connection, credential or delivery occurs. Receipts stay classified
synthetic offline, role content is labeled unverified model-shaped synthetic
text, and the page presents validated accounting, local observation and
post-run projection statuses without any delivery or export.
