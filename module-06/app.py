"""Module 6 presentation only; execution, authority and curation live in services."""

import streamlit as st
from multi_agent_orchestration.cockpit_view import (
    CURATED_LANGSMITH_DELIVERY,
    CURATED_OPERATIONAL_PIPELINE,
    CURATED_RUN_3,
    CURATED_RUN_4,
    CURATED_RUN_5,
    DEFAULT_COCKPIT_STATE,
    GUIDANCE_SECTIONS,
    DeliveryConfirmation,
    EvidenceView,
    ExecutionKind,
    OperationsState,
    PresentationProvenance,
    age_in_seconds,
)
from multi_agent_orchestration.console import (
    ConsoleBusyError,
    ConsoleFaultError,
    ConsoleRequestError,
    ConsoleSession,
    Demonstration,
    ScalingProfile,
    age_seconds,
    failure_message,
    failure_text,
    guidance,
    local_live_capability,
    local_live_failure_guidance,
    local_live_profile,
    scaling_guidance,
)
from multi_agent_orchestration.observability_contracts import Outcome

st.set_page_config(
    page_title="Module 6 operations", page_icon=":material/account_tree:", layout="wide"
)
if type(st.session_state.get("console")) is not ConsoleSession:
    st.session_state.console = ConsoleSession()
console = st.session_state.console

orientation, _, operations_state = DEFAULT_COCKPIT_STATE
# S1 postures for this render: only an injected trusted capability enables local live.
live_capability = local_live_capability()
# MODULE_6_USER_COCKPIT_SHARED_STYLES
st.markdown(
    """
    <style>
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.35rem;
        padding: 0.45rem;
        border-radius: 0.75rem;
        background: rgba(30, 41, 59, 0.78);
        border: 1px solid rgba(148, 163, 184, 0.20);
    }

    .stTabs [data-baseweb="tab"] {
        min-height: 2.75rem;
        padding-left: 1rem;
        padding-right: 1rem;
        border-radius: 0.55rem;
        background: transparent;
    }

    .stTabs [aria-selected="true"] {
        background: rgba(59, 130, 246, 0.18);
    }

    .stButton > button[kind="primary"] {
        border-radius: 0.55rem;
        font-weight: 600;
    }

    .stButton > button[kind="primary"]:not(:disabled) {
        background: #2563eb;
        border-color: #2563eb;
        color: #ffffff;
    }

    .stButton > button[kind="primary"]:not(:disabled):hover {
        background: #1d4ed8;
        border-color: #1d4ed8;
        color: #ffffff;
    }

    .stButton > button:disabled {
        opacity: 0.55;
        cursor: not-allowed;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

def render_page_intro(title: str, purpose: str) -> None:
    """Render a consistent presentation heading for a cockpit page.

    Args:
        title: Human-facing page title.
        purpose: Concise explanation of the page's purpose.
    """
    st.subheader(title)
    st.info(purpose)


def render_techademy_footer() -> None:
    """Render the standard Techademy attribution for the active cockpit page."""
    st.divider()
    left, center, right = st.columns([1.0, 3.4, 1.2])
    with left:
        st.markdown("**🎓 Techademy**")
    with center:
        st.caption(
            "Developed from Techademy AI Engineering program requirements. "
            "Independent implementation with production-grade engineering "
            "enhancements; the public reviewer deployment is verified, and "
            "final release and LinkedIn closeout remain pending."
        )
    with right:
        st.caption("Module 6  |  User Cockpit v0.6.0")

st.title("Multi-Agent Orchestration System: User Cockpit")
st.caption(
    "Production-grade multi-agent orchestration • deterministic local "
    "execution • the Demo needs no credentials"
)
st.info(
    "Demo is the baseline posture of this cockpit: real LangGraph, CrewAI and ADK "
    "runtime paths with deterministic agents; no model or LLM inference is "
    "performed, and no paid inference or external telemetry delivery is enabled. "
    "New here? Read the Guide tab, then choose a demonstration below and select "
    "Run demonstration. Nothing runs, queries or delivers until you select an "
    "action."
)
st.caption(
    "Observability • AI/agent tracing: LangSmith • Operational: OpenTelemetry → "
    "Collector → Prometheus → Grafana (verified end-to-end locally; not hosted) • "
    "Unified reviewer view: This Streamlit cockpit"
)
st.caption(
    f"Mode: {orientation.value.title()} (baseline) • Local live/BYOK: "
    f"{'available' if live_capability.local_live_available else 'unavailable'} • "
    "Public live: "
    + ("available" if live_capability.deployed_public_live_available else "unavailable")
    + " • "
    f"Operations queries: {operations_state.state.value} (nothing is queried until "
    "you select a check on the Operations tab)"
)

guide_tab, demo_tab, live_tab, ops_tab, tracing_tab, implementation_tab = st.tabs(
    [
        "Guide",
        "Deterministic Demo",
        "Live / BYOK",
        "Operations",
        "LangSmith Tracing",
        "Implementation Evidence",
    ]
)

with demo_tab:
    st.caption(
        "Purpose: run the accepted multi-agent runtimes with deterministic agents, "
        "offline and without keys."
    )
    st.caption(
        "Action: choose a demonstration, keep or edit the synthetic text, then "
        "select Run demonstration."
    )
    st.caption(
        "Expected result: a validated result with its evidence label, role order "
        "and local trace, or a named denial or timeout with no fallback."
    )
    st.caption(
        "What it proves: real runtime scheduling, validated hand-offs, bounded "
        "failure handling and evidence creation. It does not prove model "
        "reasoning, hosted operation or production capacity."
    )
    mode = st.selectbox(
        "Demonstration",
        tuple(Demonstration),
        index=None,
        placeholder="Choose explicitly…",
        key="demonstration",
    )
    if mode in tuple(Demonstration):
        st.caption(guidance(mode))
    with st.form("execution", clear_on_submit=True):
        text = st.text_area(
            "Synthetic task text",
            value="Review this deterministic orchestration example.",
            key="task_text",
            help=(
                "Use non-sensitive sample text of at most 4,096 characters; it is "
                "never echoed in results or telemetry."
            ),
        )
        with st.expander("Execution bounds and failure demonstrations"):
            # Bounds are stated as guidance only. Widget-level limits would let the
            # framework truncate or reset a submitted value before the application
            # service can reject it, so the service remains the only authority.
            steps = st.number_input("Step budget (1 to 32)", value=8, key="steps")
            deadline = st.number_input(
                "Deadline (1 to 30,000 ms)", value=30000, key="deadline"
            )
            st.caption(
                "Start with 8 steps and 30,000 ms. Try a graph with one step "
                "to observe a denial, or a very short deadline to observe "
                "timeout. No automatic retry. Out-of-range values are rejected "
                "on submit, not adjusted."
            )
        submitted = st.form_submit_button(
            "Run demonstration",
            key="run",
            type="primary",
            disabled=mode is None,
            icon=":material/play_arrow:",
        )
    rejected = False
    if submitted:
        with st.spinner("Running bounded local execution…"):
            try:
                console.run(
                    {
                        "mode": mode,
                        "instruction": text,
                        "max_steps": steps,
                        "timeout_ms": deadline,
                    }
                )
                # Select the new outcome before rendering the result widget, so a
                # prior success cannot remain the apparent result of a failed run.
                st.session_state["recent_result"] = len(console.runs) - 1
            except ConsoleRequestError:
                rejected = True
                st.error(
                    "Nothing ran. Choose a demonstration and nonblank text of at most "
                    "4,096 characters, with 1 to 32 steps and a 1 to 30,000 "
                    "ms deadline."
                )
            except ConsoleBusyError:
                rejected = True
                st.warning(
                    "Nothing ran. Wait for the current run in this session to finish."
                )
            except ConsoleFaultError:
                rejected = True
                st.error(
                    "The run ended without a recordable result. No automatic fallback "
                    "or retry ran."
                )

    if st.button("Clear recent results", key="clear", icon=":material/delete:"):
        try:
            console.clear()
        except ConsoleBusyError:
            st.warning("Wait for the current run to finish before clearing results.")

    runs = console.runs
    with st.container(horizontal=True):
        st.metric("Recent runs", len(runs), border=True)
        st.metric(
            "Completed",
            sum(run.outcome == Outcome.COMPLETED for run in runs),
            border=True,
        )
        st.metric(
            "Other outcomes",
            sum(run.outcome != Outcome.COMPLETED for run in runs),
            border=True,
        )
    st.caption(
        "Observation window: the last eight results in this browser session. "
        "No cross-session telemetry storage or global health claim. Scaling evidence "
        "comes only from the local scaling benchmark on this tab."
    )
    demo_evidence = EvidenceView(execution_kind=ExecutionKind.DETERMINISTIC_DEMO)
    if runs and rejected:
        # A submission that did not run must not appear to own an earlier result.
        st.caption(
            "This submission produced no result. Earlier results are retained and "
            "reappear on the next interaction."
        )
    elif runs:
        st.subheader("Validated result and evidence")
        chosen = st.selectbox(
            "Recent result",
            tuple(reversed(range(len(runs)))),
            format_func=lambda index: (
                f"{runs[index].mode.value} · {runs[index].workflow_id.hex[:8]}"
            ),
            key="recent_result",
        )
        if type(chosen) is not int or not 0 <= chosen < len(runs):
            st.error("Choose a valid recent result.")
            st.stop()
        view = runs[chosen]
        age = age_seconds(view)
        st.caption(
            f"Snapshot age: {age} s. {'Stale' if age > 60 else 'Recent'}; "
            "refresh does not execute."
        )
        st.caption(
            "Evidence class: "
            f"{demo_evidence.execution_kind.value} · provenance: — · "
            f"source: {demo_evidence.source.value}. "
            "Validated application facts of a real deterministic execution; no "
            "model/provider ran and no delivery happened."
        )
        if view.outcome == Outcome.COMPLETED:
            st.success(failure_message(view.outcome))
            st.text(view.output)
        else:
            st.error(failure_message(view.outcome))
        st.text(
            f"Workflow: {view.workflow_id}\nTask: {view.task_id}\n"
            f"Outcome: {view.outcome.value}"
        )
        if view.evidence is not None:
            with st.expander("Application-validated evidence"):
                st.json(view.evidence.model_dump(mode="json"))
        st.subheader("Curated local observation")
        st.caption(
            f"Local observation: {view.observation}."
            " External observability is unavailable."
        )
        if view.trace is not None:
            trace = view.trace
            with st.container(horizontal=True):
                st.metric(
                    "Workflow latency (ms)",
                    f"{trace.duration_ms:.2f}",
                    border=True,
                )
                st.metric(
                    "Model calls",
                    str(trace.accounting.model_calls)
                    if trace.accounting.model_calls is not None
                    else "Unavailable",
                    border=True,
                )
                st.metric(
                    "External calls",
                    str(trace.accounting.external_calls)
                    if trace.accounting.external_calls is not None
                    else "Unavailable",
                    border=True,
                )
            st.text(f"Local trace: {trace.trace_id}\nRoot span: {trace.span_id}")
            if trace.steps:
                st.table(
                    [
                        {
                            "Validated role": step.role.value,
                            "Order": step.sequence,
                            "Local span": step.span_id,
                            "Worker PID": step.worker_pid or "Not applicable",
                        }
                        for step in trace.steps
                    ]
                )
            st.caption(
                "Role rows prove validated completion provenance, not per-agent "
                "latency. Distributed evidence reports actual worker PIDs and "
                "reaping."
            )
        else:
            st.warning(
                "Local observation is unavailable; execution status above remains "
                "authoritative."
            )
        st.caption(
            "Token usage, estimated cost and provider-reported billing: unavailable. "
            "Zero model calls does not mean local CPU/process resources are free."
        )
    else:
        st.caption(
            "No runs yet. Selecting controls or refreshing never executes a workflow."
        )

    with st.container(border=True):
        st.subheader("Canonical live workflow (synthetic)")
        st.caption(
            "Purpose: runs the accepted canonical workflow (researcher, analyst and "
            "critic, with bounded repair) through the supervised live process path, "
            "with a fixed synthetic gateway."
        )
        st.caption(
            "Action: submit nonblank task text of at most 4,096 characters and select "
            "the run control. Authorization and budget are application-owned and "
            "fixed; the supplied text is never echoed back. A first run may hit the "
            "run deadline while the local child process warms up; retry manually."
        )
        st.caption(
            "Expected result: a synthetic offline receipt with validated role "
            "content, per-role accounting, and local observation projections; or a "
            "fixed sanitized failure. No automatic retry."
        )
        st.caption(
            "What it proves: validated role content, repair, usage accounting and "
            "live observation through the accepted canonical boundary, without any "
            "model or LLM inference."
        )
        st.caption(
            "What it does not prove: live inference, hosted execution, remote "
            "delivery, or that the synthetic content reflects any model's reasoning. "
            "No trace delivery or credential handling occurs here."
        )
        live_text = st.text_area(
            "Live task text",
            key="live_text",
            help=(
                "Use non-sensitive sample text of at most 4,096 characters. It is "
                "never echoed in results, observations or telemetry."
            ),
        )
        live_rejected = False
        if st.button(
            "Run live workflow demonstration",
            key="run_live",
            type="primary",
            icon=":material/bolt:",
        ):
            with st.spinner("Running the bounded canonical live workflow…"):
                try:
                    console.run_live({"instruction": live_text})
                    st.session_state["recent_live"] = len(console.live_runs) - 1
                except ConsoleRequestError:
                    live_rejected = True
                    st.error(
                        "Nothing ran. Submit nonblank text of at most 4,096 "
                        "characters without invalid surrogate sequences."
                    )
                except ConsoleBusyError:
                    live_rejected = True
                    st.warning(
                        "Nothing ran. Wait for the current run in this session to "
                        "finish."
                    )
                except ConsoleFaultError:
                    live_rejected = True
                    st.error(
                        "The live demonstration ended without a recordable result. "
                        "No automatic fallback or retry ran."
                    )
        live_runs = console.live_runs
        live_evidence = EvidenceView(
            execution_kind=ExecutionKind.CANONICAL_LIVE_DEMO,
            provenance=PresentationProvenance.SYNTHETIC_OFFLINE,
            delivery_confirmation=DeliveryConfirmation.NOT_SENT,
        )
        if live_runs and live_rejected:
            st.caption(
                "This submission produced no live run. Earlier live runs are "
                "retained and reappear on the next interaction."
            )
        elif live_runs:
            chosen_live = st.selectbox(
                "Recent live run",
                tuple(reversed(range(len(live_runs)))),
                format_func=lambda index: (
                    f"{live_runs[index].outcome.value} · "
                    + (
                        live_runs[index].terminal.span_id[:8]
                        if live_runs[index].terminal
                        else "no-observation"
                    )
                ),
                key="recent_live",
            )
            if type(chosen_live) is not int or not 0 <= chosen_live < len(live_runs):
                st.error("Choose a valid recent live run.")
                st.stop()
            run = live_runs[chosen_live]
            age = age_seconds(run)
            st.caption(
                f"Snapshot age: {age} s. {'Stale' if age > 60 else 'Recent'}; "
                "refresh does not execute."
            )
            st.caption(
                "Evidence class: "
                f"{live_evidence.execution_kind.value} · provenance: "
                f"{live_evidence.provenance.value} · confirmation: "
                f"{live_evidence.delivery_confirmation.value}"
                f" · source: {live_evidence.source.value}. Synthetic gateway "
                "content is unverified text; no model inference occurred."
            )
            if run.receipt is not None:
                st.success(
                    "Synthetic canonical run completed; receipt classified "
                    f"{run.receipt.evidence_source.value} (synthetic gateway; no "
                    "inference ran)."
                )
                st.caption(
                    "Role content below is unverified model-shaped synthetic text "
                    "produced by the demo gateway, never a claim of model reasoning."
                )
                content = run.receipt.result
                st.text(f"Research findings: {'; '.join(content.research.findings)}")
                st.text(f"Assessment: {content.analysis.assessment}")
                st.text(
                    "Support witnesses: "
                    + ", ".join(str(item) for item in content.analysis.supports)
                )
                st.text(f"Advisory verdict: {content.critique.advisory_verdict}")
                st.text(f"Advisory rationale: {content.critique.rationale}")
                accounting = content.evidence.accounting
                with st.container(horizontal=True):
                    st.metric("Model calls", accounting.model_calls, border=True)
                    st.metric(
                        "Repair attempts", accounting.repair_attempts, border=True
                    )
                    st.metric(
                        "Input tokens",
                        (
                            accounting.usage.input_tokens
                            if accounting.usage.input_tokens is not None
                            else "Unavailable"
                        ),
                        border=True,
                    )
                    st.metric(
                        "Output tokens",
                        (
                            accounting.usage.output_tokens
                            if accounting.usage.output_tokens is not None
                            else "Unavailable"
                        ),
                        border=True,
                    )
                    st.metric(
                        "Transport retries", accounting.transport_retries, border=True
                    )
            elif run.failure is not None:
                st.error(failure_text(run.failure.category))
            else:
                st.warning(failure_message(run.outcome))
            if run.terminal is not None:
                st.subheader("Curated live observation")
                st.caption(f"Local observation: {run.observation}.")
                st.text(
                    f"Local trace: {run.terminal.trace_id}\n"
                    f"Root span: {run.terminal.span_id}"
                )
                if run.terminal.roles:
                    st.table(
                        [
                            {
                                "Validated role": row.role.value,
                                "Order": row.sequence,
                                "Local span": row.span_id,
                                "Model calls": row.model_calls,
                                "Repair attempts": row.repair_attempts,
                            }
                            for row in run.terminal.roles
                        ]
                    )
                st.caption(
                    "Role rows record validated completion instants, not role "
                    "latency. Timing is descriptive, never a capacity claim."
                )
            if run.events:
                st.caption("Observation events (bounded local retention):")

                def live_event(event):
                    if (
                        event.role is None
                        or event.model_calls is None
                        or event.repair_attempts is None
                    ):
                        return event.phase
                    return (
                        f"{event.phase}({event.role.value}, "
                        f"calls {event.model_calls}, repairs {event.repair_attempts})"
                    )

                st.text(" → ".join(live_event(event) for event in run.events))
            st.caption(
                "Post-run projections from the terminal observation — LangSmith: "
                f"{run.langsmith} · local OpenTelemetry: {run.otel} · local metric "
                f"window: {run.metrics}. No delivery, export or external "
                "collection occurred."
            )
        else:
            st.caption(
                "No live run yet. Submitting text or refreshing never executes."
            )

    with st.container(border=True):
        st.subheader("Local scaling benchmark")
        for label, text in scaling_guidance():
            st.caption(f"{label}: {text}")
        profile = st.selectbox(
            "Benchmark profile",
            tuple(ScalingProfile),
            index=None,
            placeholder="Choose explicitly…",
            key="scaling_profile",
        )
        unrecorded = False
        if st.button(
            "Run scaling benchmark",
            key="run_scaling",
            disabled=profile is None,
            type="primary",
            icon=":material/speed:",
        ):
            with st.spinner("Running bounded local worker processes…"):
                try:
                    console.run_scaling({"profile": profile})
                except ConsoleRequestError:
                    unrecorded = True
                    st.error("Nothing ran. Choose one of the two benchmark profiles.")
                except ConsoleBusyError:
                    unrecorded = True
                    st.warning(
                        "Nothing ran. Wait for the current run in this "
                        "session to finish."
                    )
                except ConsoleFaultError:
                    unrecorded = True
                    st.error(
                        "The benchmark ended without a recordable result. No automatic "
                        "fallback or retry ran."
                    )
        scaling = console.scaling
        if scaling is not None and unrecorded:
            # A submission that did not run must not appear to own an earlier report.
            st.caption(
                "This submission produced no report. The earlier report is retained "
                "and reappears on the next interaction."
            )
        elif scaling is not None:
            report = scaling.report
            age = age_seconds(scaling)
            st.caption(
                f"{scaling.profile.value}. Snapshot age: {age} s. "
                f"{'Stale' if age > 60 else 'Recent'}; refresh does not execute."
            )
            st.caption(
                "Evidence class: deterministic_demo · source: "
                f"{demo_evidence.source.value}. Single-host deterministic local "
                "scaling benchmark evidence."
            )
            if report.passed:
                st.success(
                    "All benchmark invariants held: every workflow completed and was "
                    "revalidated, and each cap was respected."
                )
            else:
                st.error(
                    "A benchmark invariant did not hold. No throughput or speedup is "
                    "reported for a failed level, and later caps did not run."
                )

            def shown(value, digits=2):
                return "Not derived" if value is None else f"{value:.{digits}f}"

            st.table(
                [
                    {
                        "Cap": level.cap,
                        "Completed": f"{level.completed} / {level.requested}",
                        "Wall s": shown(level.wall_seconds),
                        "Per second": shown(level.throughput_per_second, 3),
                        "Median s": shown(level.duration_median_seconds),
                        "Peak in flight": level.peak_in_flight,
                        "Overlap": shown(level.overlap_factor),
                        "Speedup vs cap 1": shown(level.speedup_vs_cap_1),
                        "Workers reaped": level.workers_reaped,
                        "Invariants": "Held" if level.passed else "Not held",
                    }
                    for level in report.levels
                ]
            )
            cpus = report.host.logical_cpus
            calls = "0" if report.model_calls == 0 else "Unavailable: benchmark failed"
            st.text(
                f"Classification: {report.classification} ({report.evidence_class})\n"
                f"Host: {report.host.system}, Python {report.host.python}, "
                f"logical CPUs: {'unknown' if cpus is None else cpus}\n"
                f"Warm-up completed: {report.warmup_completed}\n"
                f"Model, provider and external calls and retries: {calls}"
            )
            st.caption(
                "Deterministic, local, single-host, machine-specific, "
                "bounded-concurrency evidence measured by this run. Speedup is not a "
                "pass criterion and is not typical or portable performance. This is "
                "not production capacity, a service level, or cloud, horizontal or "
                "remote-cluster scaling."
            )
        else:
            st.caption(
                "No benchmark report yet. Selecting a profile or refreshing never "
                "starts worker processes."
            )

    with st.expander("How to review these demonstrations", expanded=True):
        st.markdown(
            "1. Run the fixture to check the zero-key request/result boundary.\n"
            "2. Select a runtime or topology and inspect validated role order "
            "and evidence.\n"
            "3. Change synthetic text to compare deterministic results; try "
            "bounded failure controls.\n"
            "4. Run local distribution to inspect two independent worker PIDs "
            "and managed cleanup.\n"
            "5. Run the local scaling benchmark to compare admission caps on "
            "this machine.\n"
            "6. Run the canonical live workflow demonstration: it validates role "
            "content, accounting and observation through the synthetic gateway "
            "without inference."
        )
        st.table(
            [
                {"Demonstration": item.value, "What it does and proves": guidance(item)}
                for item in Demonstration
            ]
        )
        st.caption(
            "The demonstrations prove local runtime scheduling, validated "
            "context and evidence. "
            "Every agent is deterministic: no model or LLM inference runs anywhere "
            "in these paths. "
            "They do not prove live AI reasoning, remote-host distribution, "
            "production capacity or hosted deployment. Requirement status is "
            "recorded in the Module 6 traceability document, not on this page."
        )

    render_techademy_footer()

with live_tab:
    st.info(
        "Purpose: Local Live runs the accepted Researcher → Analyst → Critic "
        "workflow with real local inference through Ollama, for a trusted private "
        "operator only; Demo stays deterministic and needs no keys. Local Ollama "
        "inference does not itself require a credential. Public/deployed live "
        "execution is unavailable by design: no deployment authority boundary is "
        "accepted, so a public visitor can never spend an operator's compute or "
        "any credential. BYOK means the operator's trusted runtime brings its own "
        "provider connectivity, supplying a credential only where a provider needs "
        "one and never as a secret pasted into this page; credentials and model "
        "availability are connectivity, not execution authority."
    )
    with st.container(border=True):
        st.markdown("**Execution profile**")
        st.code(local_live_profile(), language=None)
    st.caption(
        "Action: select Run authorized local live workflow. Each click explicitly "
        "authorizes one fresh, bounded NORMAL execution of a fixed application "
        "task. No approval is remembered; rerenders never execute."
    )
    st.caption(
        "Expected result: validated role, call, timing and cleanup facts plus "
        "local projection states — not raw model output and not external delivery."
    )
    st.caption(
        "What it proves: the control plane — explicit intent → fresh authority → "
        "bounded canonical workflow → local model → validated result → sanitized "
        "evidence → local observability projection. It does not prove model "
        "quality, hosted-provider support or delivery to LangSmith."
    )
    if not live_capability.local_live_available:
        # The default posture, not an alert: warnings signal attempted actions.
        st.caption(
            "Local live unavailable: no trusted private-operator capability was "
            "supplied by the embedding runtime. No readiness probe or credential "
            "lookup was performed. Demo and recorded historical evidence "
            "remain available."
        )
    if st.button(
        "Run authorized local live workflow",
        key="local_live_run",
        disabled=not live_capability.local_live_available,
        type="primary",
    ):
        with st.spinner("One bounded local execution; no automatic retry…"):
            try:
                console.run_authorized_local()
            except ConsoleBusyError:
                st.warning("A session operation is already active; nothing else ran.")
    current_local = console.current_local
    if current_local is None:
        st.caption(
            "No current local Live attempt in this session. "
            "Historical runs below are separate."
        )
    else:
        st.subheader("Current local Live attempt (this session)")
        st.caption(
            f"Finished {age_in_seconds(current_local.finished_ns)} s ago · "
            f"execution_kind: {current_local.evidence.execution_kind.value} · "
            f"source: {current_local.evidence.source.value} · delivery: "
            f"{current_local.evidence.delivery_confirmation.value}. LangSmith, "
            "OTel and metrics states are local projections only; no current "
            "operational health or LangSmith service-read confirmation is inferred."
        )
        if current_local.failure:
            st.warning(
                f"Current attempt: {current_local.outcome} "
                f"({current_local.category or current_local.failure}). "
                + (
                    failure_text(current_local.category) + " "
                    if current_local.category
                    else ""
                )
                + local_live_failure_guidance(current_local.failure)
                + " No historical result replaces this failure."
            )
        else:
            st.success("Canonical local workflow completed with validated evidence.")
        st.json(current_local.model_dump(mode="json"))
    with st.expander("Recorded historical real-local runs (not current)"):
        historical_records = (
            ("Run 3 · Out-of-policy observation", CURATED_RUN_3),
            ("Run 4 · Authorized real-local verification", CURATED_RUN_4),
            ("Run 5 · Live-model LangSmith projection", CURATED_RUN_5),
        )
        for index, (label, record) in enumerate(historical_records):
            if index:
                st.divider()
            st.markdown(f"**{label}**")
            st.caption(f"Accepted classification: {record.accepted_classification}")
            st.caption(
                f"source: {record.source.value} · kind: "
                f"{record.execution_kind.value} · provenance: "
                f"{record.provenance.value if record.provenance else 'none'} · "
                "delivery confirmation: "
                + (
                    record.delivery_confirmation.value
                    if record.delivery_confirmation
                    else "none"
                )
            )
            st.text(
                f"{record.summary}\nrecorded reference: "
                f"{record.reference_id or 'none recorded'}"
            )

    render_techademy_footer()

with ops_tab:
    st.caption(
        "Purpose: operational observability — OpenTelemetry instruments the "
        "application → the OpenTelemetry Collector ingests → Prometheus stores "
        "metrics and alert rules → Grafana is the specialist dashboard. "
        "Streamlit only curates results here and never embeds those services."
    )
    st.caption(
        "Action: read the recorded verification, then optionally select Check "
        "current local observability stack. Expected result: fresh current-host "
        "values when the local stack is running, otherwise an honest unavailable "
        "state. What it proves: what this host's stack reports at that moment — "
        "not hosted telemetry, public Grafana or any service level."
    )
    record = CURATED_OPERATIONAL_PIPELINE
    st.subheader("Recorded verification (not a current check)")
    st.caption(
        "Evidence class: "
        f"{record.source.value} · kind: {record.execution_kind.value} · "
        f"classification: {record.accepted_classification}. Preserved from the "
        "accepted deterministic local operational-telemetry verification "
        "records: not a fresh health probe, not proof that the services are "
        "running now, and not production, hosted or SLA evidence."
    )
    st.text(record.summary)
    st.subheader("Fresh current-host check (explicit action)")
    st.caption(
        "localhost means the host running this Streamlit application — in a "
        "deployment, the deployed host or container, never your personal "
        "machine or the visitor's workstation. A public deployment cannot "
        "inspect services on your computer, and this UI will not pretend to."
    )
    st.caption(
        "Fixed read-only endpoints only: 127.0.0.1 Prometheus (9090) and "
        "Grafana (3000), one bounded attempt, validated untrusted responses, "
        "no retries, no polling, no background refresh."
    )
    if st.button(
        "Check current local observability stack",
        key="ops_query",
        type="primary",
        icon=":material/query_stats:",
    ):
        with st.spinner("Bounded read-only local check…"):
            try:
                console.check_operations()
            except ConsoleFaultError:
                st.error(
                    "The check could not produce a validated observation. "
                    "No historical value is substituted and nothing executed "
                    "beyond read-only requests."
                )
    try:
        stored = console.operations
    except ConsoleFaultError:
        stored = None
        st.warning(
            "A retained operational observation was not revalidatable and "
            "was cleared. Nothing ran on this render; request a new check."
        )
    if stored is None:
        st.caption(
            "Not activated: nothing has been queried in this session. The "
            "recorded verification above stays historical; no fresh values "
            "are shown until you request a check."
        )
    else:
        age = age_in_seconds(stored.happened_ns)
        obs = stored.observation
        st.caption(
            f"Checked {age} s ago on this host. Source: fresh_execution — "
            "a read-only local observation, NOT the recorded pipeline "
            "verification and not current production health."
        )
        if obs is None:
            st.error(
                "The check produced no observation. The deterministic demo "
                "remains fully available; nothing was fabricated."
            )
        elif obs.query_state == OperationsState.UNAVAILABLE:
            st.warning(
                "The local observability stack was not reachable on this "
                "host. The deterministic demo remains available; no values "
                "are fabricated and no historical value is substituted."
            )
        else:
            st.metric(
                "Finished workflows (local Prometheus)",
                (
                    "Unavailable"
                    if obs.finished_total is None
                    else f"{obs.finished_total:g}"
                ),
                border=True,
            )
            st.metric(
                "Alert rules loaded",
                (
                    obs.alert_rules_loaded
                    if obs.alert_rules_loaded is not None
                    else "Unavailable"
                ),
                border=True,
            )
            st.metric(
                "Grafana healthy",
                (
                    "True"
                    if obs.grafana_healthy
                    else "False"
                    if obs.grafana_healthy is False
                    else "Unavailable"
                ),
                border=True,
            )
            st.metric(
                "Dashboard provisioned",
                (
                    "True"
                    if obs.dashboard_provisioned
                    else "False"
                    if obs.dashboard_provisioned is False
                    else "Unavailable"
                ),
                border=True,
            )
            st.metric(
                "Finished workflows (via Grafana data source)",
                (
                    "Unavailable"
                    if obs.grafana_datasource_total is None
                    else f"{obs.grafana_datasource_total:g}"
                ),
                border=True,
            )
            if obs.dashboard_reference:
                # Validated loopback reference for the CURRENT HOST; shown as
                # inert text. Never usable from a visitor's browser host.
                st.text(f"Dashboard (current host only): {obs.dashboard_reference}")

    render_techademy_footer()

with tracing_tab:
    st.info(
        "Purpose: AI/agent observability. LangSmith remains the specialist "
        "AI/agent tracing system; this tab presents accepted recorded evidence "
        "natively and never fetches, iframes or delivers anything from a page "
        "render."
    )
    st.caption(
        "From this console, no trace has been delivered: no console action sends "
        "anything. Service-read verification of the recorded live-model trace "
        "(Run 5) is pending; it remains unverified_write. Recorded module "
        "evidence is shown below, clearly labelled recorded/historical."
    )
    st.caption(
        "Action: compare the two recorded deliveries, then optionally select "
        "Check current LangSmith evidence. Expected result here: an honest "
        "unavailable state, because this page supplies no read capability. What "
        "the records prove: exactly their accepted classifications, no more."
    )
    langsmith_records = (
        ("Deterministic delivery verification", CURATED_LANGSMITH_DELIVERY),
        ("Live-model LangSmith delivery", CURATED_RUN_5),
    )
    for label, record in langsmith_records:
        st.subheader(f"Recorded · {label}")
        st.caption(f"Accepted classification: {record.accepted_classification}")
        st.caption(
            f"evidence class: {record.source.value} · delivery confirmation: "
            f"{record.delivery_confirmation.value} — "
            + (
                "the service returned the recorded root run under the "
                "accepted read contract"
                if record.service_read_confirmed
                else "the write was accepted with HTTP 2xx and no "
                "programmatic service read-back exists for this event; it "
                "never implies a service-read confirmation"
            )
        )
        st.text(f"{record.summary}\nrecorded trace: {record.reference_id}")
    st.text(
        "Recorded LangSmith project: module6-verification · "
        "destination: api.smith.langchain.com"
    )
    st.caption(
        "service_read means the service returned the requested recorded "
        "evidence; unverified_write means only that the delivery write was "
        "accepted. They are different confirmed facts and this tab never "
        "merges them into a generic delivered state."
    )
    st.caption(
        "This build offers no dashboard link from the console: the LangSmith "
        "project UI stays the specialist trace drill-down, and Grafana is the "
        "specialist operational drill-down (see the Operations tab)."
    )
    st.subheader("Current evidence check (explicit action)")
    st.caption(
        "A current read is read-only, allowlisted to the accepted recorded "
        "traces, and requires a read capability supplied by a trusted runtime; "
        "this page supplies none, so this check reports honest unavailability "
        "instead of touching credentials or endpoints. No credential is read "
        "from any store by this console."
    )
    if st.button(
        "Check current LangSmith evidence",
        key="langsmith_read",
        type="primary",
        icon=":material/manage_search:",
    ):
        with st.spinner("Bounded read-only recorded-trace check…"):
            try:
                console.inspect_langsmith()
            except ConsoleFaultError:
                st.error(
                    "The inspection could not produce a validated "
                    "observation. No historical value is substituted and no "
                    "write or delivery occurred."
                )
    try:
        stored_read = console.langsmith_read
    except ConsoleFaultError:
        stored_read = None
        st.warning(
            "A retained inspection was not revalidatable and was cleared. "
            "Nothing ran on this render; request a new check."
        )
    if stored_read is None:
        st.caption(
            "Not activated: no current LangSmith read has been requested in "
            "this session; the recorded evidence above stays historical."
        )
    else:
        obs = stored_read.observation
        age = age_in_seconds(stored_read.happened_ns)
        st.caption(
            f"Checked {age} s ago · source: fresh_execution — a current "
            "inspection of a recorded trace: not a new "
            "execution, not a new delivery, and not an authority."
        )
        if obs is None or obs.read_state == "unavailable":
            # This page never supplies a read capability, so no read is attempted.
            st.warning(
                "Not available in this posture: no trusted read capability is "
                "supplied here, so no service read was attempted (this is not a "
                "failed read). The recorded evidence remains historical and "
                "available; nothing was fabricated."
            )
        else:
            st.metric(
                "Recorded service-read confirmed",
                "True" if obs.service_read else "False",
                border=True,
            )
            st.text(f"Inspected recorded trace: {obs.target_trace_id}")

    render_techademy_footer()

with guide_tab:
    st.info(
        "**Welcome to the Multi-Agent Orchestration System**  \n"
        "This application demonstrates a secured, human-in-the-loop multi-agent "
        "orchestration system using LangGraph, CrewAI and Google ADK, with "
        "operational observability through OpenTelemetry → Collector → Prometheus "
        "→ Grafana and AI/agent tracing through LangSmith."
    )

    capabilities, exploration = st.columns(2, gap="medium")

    with capabilities:
        with st.container(border=True):
            st.subheader("What this module demonstrates")
            st.markdown(
                "- ✅ Multi-agent orchestration with clear roles and boundaries\n"
                "- ✅ Deterministic local Demo with no model inference\n"
                "- ✅ Operator-only live model workflow (BYOK)\n"
                "- ✅ Operational observability with OpenTelemetry, Prometheus "
                "and Grafana\n"
                "- ✅ AI/agent tracing with LangSmith\n"
                "- ✅ Security, safety and human-approval controls"
            )

    with exploration:
        with st.container(border=True):
            st.subheader("How to explore")
            st.markdown(
                "1. **Guide** — understand the system and workflow\n"
                "2. **Deterministic Demo** — run a complete offline workflow\n"
                "3. **Live / BYOK** — inspect the trusted-local live boundary\n"
                "4. **Operations** — inspect local operational observability\n"
                "5. **LangSmith Tracing** — inspect recorded AI/agent evidence\n"
                "6. **Implementation Evidence** — inspect architecture-to-code proof"
            )

    st.markdown(
        "**Important**  \n"
        "This is a demonstration environment. No model or LLM inference is "
        "performed on the Deterministic Demo tab. Live model execution requires "
        "separate trusted-local operator authorization. Local Ollama inference does "
        "not itself need a credential; where a provider does, the operator's trusted "
        "runtime supplies it and none is ever entered on this page; credential "
        "presence alone never grants authority. Public live execution is not "
        "enabled."
    )

    with st.expander("Evidence and deployment boundaries"):
        st.markdown(
            "- **Recorded evidence** is historical and is never presented as a "
            "fresh current-host check.\n"
            "- **Operations** can perform only an explicit bounded read-only check "
            "of the Streamlit host's allowlisted local Prometheus/Grafana endpoints.\n"
            "- **LangSmith Tracing** separates recorded delivery evidence from any "
            "explicit current read capability.\n"
            "- The verified local observability stack does **not** prove hosted "
            "production scale, public observability, SLA performance or a "
            "production deployment.\n"
            "- Rendering this Guide performs no probes, model calls, credential "
            "reads or external telemetry delivery."
        )

    for section in GUIDANCE_SECTIONS:
        st.subheader(section.title)
        st.write(section.body)

    render_techademy_footer()
with implementation_tab:
    render_page_intro(
        "Implementation Evidence",
        "Inspect selected production-source evidence behind the orchestration, "
        "tracing and operational-observability capabilities demonstrated by " +
        "this system.",
    )

    st.caption(
        "These are curated, abridged architecture-to-code excerpts from the accepted "
        "Module 6 implementation (`...` marks omitted code; lines shown are copied "
        "verbatim). Each names its source file and function rather than line numbers, "
        "which change as files evolve. They are evidence of implementation "
        "structure—not claims of hosted production scale, delivery, or current "
        "external-service state."
    )

    st.subheader("Orchestration frameworks")

    with st.expander(
        "LangGraph — graph topology compilation and execution", expanded=True
    ):
        st.markdown(
            "**Requirement:** Sequential, parallel and hierarchical multi-agent "
            "orchestration.  \n"
            "**Technology:** LangGraph  \n"
            "**Implementation:** `_langgraph_topologies.py` compiles application-owned "
            "topologies into a real graph and executes the compiled graph through the "
            "native async scheduler."
        )
        st.code(
            '''graph.add_edge("__start__", "fanout")
graph.add_edge("fanout", "left")
graph.add_edge("fanout", "right")
graph.add_edge(["left", "right"], "aggregate")
graph.add_edge("aggregate", "__end__")
return graph.compile()''',
            language="python",
        )
        st.caption(
            "Source: `src/multi_agent_orchestration/_langgraph_topologies.py` · "
            "`compile_topology` (parallel topology)."
        )
        st.markdown(
            "**What this proves:** The parallel demonstration uses an implemented "
            "fan-out/fan-in graph with a synchronization barrier—not a UI simulation."
        )

    with st.expander("CrewAI — collaborative multi-agent workflow"):
        st.markdown(
            "**Requirement:** Collaborative AI workflow with shared validated " +
            "context.  \n"
            "**Technology:** CrewAI  \n"
            "**Implementation:** `_crewai_adapter.py` constructs genuine CrewAI "
            "`BaseAgent`, `Task` and `Crew` objects while keeping model execution "
            "disabled for the deterministic demonstration."
        )
        st.code(
            '''crew = Crew(
    agents=agents,
    tasks=tasks,
    process=Process.sequential,
    memory=False,
    cache=False,
    planning=False,
    tracing=False,
    verbose=False,
)
...
output = crew.kickoff()''',
            language="python",
        )
        st.caption(
            "Source: `src/multi_agent_orchestration/_crewai_adapter.py` · "
            "`build_crew` and `run_crew`."
        )
        st.markdown(
            "**What this proves:** CrewAI owns the collaborative task scheduling while "
            "application contracts validate role order, context and final output."
        )

    with st.expander("Google ADK — native workflow and session execution"):
        st.markdown(
            "**Requirement:** Google ADK orchestration and delegated agent " +
            "execution.  \n"
            "**Technology:** Google Agent Development Kit (ADK)  \n"
            "**Implementation:** `_adk_adapter.py` creates native ADK agents and a "
            "`Workflow`, then executes it through an `InMemoryRunner` with validated "
            "application state."
        )
        st.code(
            'return Workflow(name="bounded_adk", '
            "edges=[(START, *agents)], max_concurrency=1)\n"
            "...\n"
            "async with InMemoryRunner(node=workflow, app_name=app_name) as runner:\n"
            "    await runner.session_service.create_session(\n"
            "        ...",
            language="python",
        )
        st.caption(
            "Source: `src/multi_agent_orchestration/_adk_adapter.py` · "
            "`build_workflow` and `run_adk`."
        )
        st.markdown(
            "**What this proves:** The ADK demonstration uses native workflow, agent, "
            "runner and session primitives rather than an application-only imitation."
        )

    st.subheader("AI / agent tracing")

    with st.expander("LangSmith — bounded trace delivery and verification"):
        st.markdown(
            "**Requirement:** Execution tracing with externally verifiable AI/agent "
            "evidence.  \n"
            "**Technology:** LangSmith  \n"
            "**Implementation:** `langsmith_delivery.py` builds a sanitized, "
            "payload-free run tree and uses the LangSmith client for one bounded "
            "batch ingestion; the same module implements a bounded read-back "
            "check."
        )
        st.code(
            '''client = sdk.Client(
    api_url=ORIGIN,
    api_key=key,
    auto_batch_tracing=False,
    ...
    retry_config=Retry(total=0),
    ...
    hide_inputs=True,
    hide_outputs=True,
    ...
)
...
client.batch_ingest_runs(create=runs)''',
            language="python",
        )
        st.caption(
            "Source: `src/multi_agent_orchestration/langsmith_delivery.py` · "
            "`LangSmithTraceDelivery._run`."
        )
        st.markdown(
            "**What this proves:** LangSmith is implemented as the specialist AI/agent "
            "tracing boundary with explicit delivery controls; it is not presented "
            "as an orchestration framework. This excerpt does not show that any "
            "delivery happened or was read back: the recorded `service_read` and "
            "`unverified_write` events are shown, separately classified, on the "
            "LangSmith Tracing tab."
        )

    st.subheader("Operational observability")

    with st.expander(
        "OpenTelemetry → Collector → Prometheus → Grafana — operational metrics"
    ):
        st.markdown(
            "**Requirement:** Vendor-neutral operational telemetry with a local "
            "collection, metrics and dashboard pipeline.  \n"
            "**Technology:** OpenTelemetry / OTLP, OpenTelemetry Collector, "
            "Prometheus and Grafana  \n"
            "**Implementation:** `telemetry_delivery.py` constrains OTLP metric "
            "delivery to an operator-selected loopback endpoint and constructs a "
            "bounded `OTLPMetricExporter` with environment-derived transport settings "
            "disabled."
        )
        st.code(
            '''session = requests.Session()
session.trust_env = False
exporter = OTLPMetricExporter(
    endpoint=config.endpoint,
    headers={"X-Module6-Delivery": config.mode},
    timeout=timeout_ms / 1000,
    compression=Compression.NoCompression,
    session=session,
)''',
            language="python",
        )
        st.caption(
            "Source: `src/multi_agent_orchestration/telemetry_delivery.py` · "
            "`OtlpMetricDelivery.__init__`."
        )
        st.markdown(
            "**What this proves:** The application contains a real bounded "
            "OTLP metrics handoff. Separately, the recorded local verification "
            "(2026-10-23; see the Operations tab) exercised the downstream "
            "Collector → Prometheus → Grafana pipeline end to end; this excerpt "
            "does not show that run or the state of any service now."
        )

    st.info(
        "**Evidence boundary**  \n"
        "The excerpts above establish implemented framework and observability "
        "boundaries. Runtime and delivery claims remain governed by the separately "
        "labelled deterministic, local, recorded and externally verified evidence "
        "shown elsewhere in this cockpit. No code excerpt alone is treated as proof "
        "of a current external service state or hosted production deployment."
    )

    render_techademy_footer()
