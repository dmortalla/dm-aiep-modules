"""Module 6 presentation only; execution, authority and curation live in services."""

import streamlit as st
from multi_agent_orchestration.cockpit_view import (
    CURATED_OPERATIONAL_PIPELINE,
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
    scaling_guidance,
)
from multi_agent_orchestration.observability_contracts import Outcome

st.set_page_config(
    page_title="Module 6 operations", page_icon=":material/account_tree:", layout="wide"
)
if type(st.session_state.get("console")) is not ConsoleSession:
    st.session_state.console = ConsoleSession()
console = st.session_state.console

orientation, live_capability, operations_state = DEFAULT_COCKPIT_STATE
st.title("Module 6 reviewer cockpit")
st.caption(
    "Multi-agent orchestration • deterministic local execution • no credentials needed"
)
st.info(
    "Choose a demonstration, use synthetic task text, then select Run demonstration. "
    "These real runtime paths use deterministic agents; "
    "no model or LLM inference is performed. "
    "No paid inference or external telemetry delivery is enabled. "
    "Demo is the baseline posture of this cockpit."
)
st.caption(
    f"Mode: {orientation.value} (baseline) • live/BYOK posture: "
    f"{'available' if live_capability.local_live_available else 'unavailable'} • "
    f"operations queries: {operations_state.state.value} (nothing probes until an "
    "explicit request is offered by a later story)"
)

demo_tab, live_tab, ops_tab, tracing_tab, guide_tab = st.tabs(
    ["Deterministic demo", "Live / BYOK", "Operations", "LangSmith tracing", "Guide"]
)

with demo_tab:
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

with live_tab:
    st.info(
        "Live/BYOK execution is not offered by this candidate build. The "
        "reviewer-experience contract reserves it for the secure local live "
        "presentation story (S5); a deployed public application reports live as "
        "unavailable unless a separately verified deployment-compatible "
        "authority boundary is enabled. Nothing executes from rendering this "
        "tab, and no credential is requested, accepted or stored."
    )
    st.caption(
        "What this build demonstrates instead: the Deterministic demo tab and "
        "the synthetic canonical live workflow demonstration."
    )

with ops_tab:
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
            if obs.dashboard_reference:
                # Validated loopback reference for the CURRENT HOST; shown as
                # inert text. Never usable from a visitor's browser host.
                st.text(f"Dashboard (current host only): {obs.dashboard_reference}")

with tracing_tab:
    st.info(
        "LangSmith aggregation is not offered by this candidate build "
        "(reserved for a later story, S4). The application itself delivers "
        "nothing from a page render and performs no LangSmith fetch."
    )
    st.caption(
        "From this console, no trace has been delivered and live verification "
        "is pending: no console action sends anything. Recorded module "
        "evidence, kept in documentation and labelled there: one "
        "independently accepted deterministic sanitized-trace delivery "
        "(POST /runs/batch, 202, four runs accepted, service_read receipt) "
        "and one recorded live-model projection and delivery under the "
        "committed unverified_write contract (not independently confirmed "
        "authority-consumption). This console presents no fresh LangSmith "
        "evidence in this build."
    )
    st.caption(
        "This build offers no dashboard link from the console; Grafana remains "
        "the specialist drill-down for recorded operational evidence while "
        "the operations presentation story is pending."
    )

with guide_tab:
    st.caption(
        "Guidance essentials for this candidate build; the complete "
        "reviewer-guidance surface arrives with the later polish story (S6). "
        f"Current mode: {orientation.value}."
    )
    wanted = {
        "What Module 6 demonstrates",
        "Demo mode (offline, no keys)",
        "Evidence classes",
        "Historical versus fresh evidence",
        "What the evidence does not prove",
    }
    for section in GUIDANCE_SECTIONS:
        if section.title in wanted:
            st.subheader(section.title)
            st.write(section.body)
