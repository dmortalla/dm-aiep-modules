"""Module 6 presentation only; execution, authority and curation live in services."""

import streamlit as st
from multi_agent_orchestration.console import (
    ConsoleBusyError,
    ConsoleFaultError,
    ConsoleRequestError,
    ConsoleSession,
    Demonstration,
    ScalingProfile,
    age_seconds,
    failure_message,
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

st.title("Module 6 operations")
st.caption(
    "Multi-agent orchestration • deterministic local execution • no credentials needed"
)
st.info(
    "Choose a demonstration, use synthetic task text, then select Run demonstration. "
    "These real runtime paths use deterministic agents; "
    "no model or LLM inference is performed. "
    "No paid inference or external telemetry delivery is enabled."
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
            "Use non-sensitive sample text of at most 4,096 characters. It is never "
            "echoed in results or telemetry."
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
            "Start with 8 steps and 30,000 ms. Try a graph with one step to observe "
            "a denial, or a very short deadline to observe timeout. No automatic "
            "retry. Out-of-range values are rejected on submit, not adjusted."
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
                "4,096 characters, with 1 to 32 steps and a 1 to 30,000 ms deadline."
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
        "Completed", sum(run.outcome == Outcome.COMPLETED for run in runs), border=True
    )
    st.metric(
        "Other outcomes",
        sum(run.outcome != Outcome.COMPLETED for run in runs),
        border=True,
    )
st.caption(
    "Observation window: the last eight results in this browser session. "
    "No cross-session telemetry storage or global health claim. Scaling evidence "
    "comes only from the local scaling benchmark below."
)
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
        f"Local observation: {view.observation}. External observability is unavailable."
    )
    if view.trace is not None:
        trace = view.trace
        with st.container(horizontal=True):
            st.metric("Workflow latency (ms)", f"{trace.duration_ms:.2f}", border=True)
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
            "Role rows prove validated completion provenance, not per-agent latency. "
            "Distributed evidence reports actual worker PIDs and reaping."
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
                    "Nothing ran. Wait for the current run in this session to finish."
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
        "this machine."
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
with st.container(border=True):
    st.subheader("Specialist observability")
    st.text(
        "LangSmith: offline SDK tracing evidence only; no trace has been "
        "delivered and live verification is pending.\n"
        "Grafana: specialist drill-down through the separate opt-in local stack; "
        "this console offers no dashboard link.\n"
        "OpenTelemetry → OTLP collection → Prometheus → Grafana remains "
        "the approved path."
    )
    st.caption("This console presents curated evidence. It is not telemetry storage.")
