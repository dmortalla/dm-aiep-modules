"""Operator command: deliver one sanitized deterministic trace to LangSmith.

Nothing is sent unless ``--deliver`` is given. ``--preview`` prints the exact run
bodies that would be sent and uses neither the network nor a credential. The
destination is fixed. The credential is read only from the LANGSMITH_API_KEY
environment variable of this process and is never printed, logged or stored. No
model, provider or paid call is made: the traced workflow uses deterministic
agents.
"""

import argparse
import asyncio
import json


def traced_workflow():
    """Run one accepted deterministic workflow offline and return its trace."""
    from multi_agent_orchestration.contracts import (
        ExecutionLimits,
        GraphTopology,
        RuntimeId,
        TaskInput,
        WorkflowRequest,
    )
    from multi_agent_orchestration.observability import Observability
    from multi_agent_orchestration.observed_execution import execute_observed_workflow

    observer = Observability()
    result = asyncio.run(
        execute_observed_workflow(
            WorkflowRequest(
                runtime=RuntimeId.LANGGRAPH,
                topology=GraphTopology.SEQUENTIAL,
                task=TaskInput(instruction="Synthetic LangSmith verification text."),
                limits=ExecutionLimits(max_steps=8, timeout_ms=30000),
            ),
            observer=observer,
        )
    )
    return result, observer.records[-1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--deliver", action="store_true", help="required to send")
    action.add_argument(
        "--preview", action="store_true", help="print the run bodies; send nothing"
    )
    args = parser.parse_args(argv)
    if not (args.deliver or args.preview):
        print(
            "Nothing ran. Delivery is opt-in: pass --preview to inspect the trace "
            "or --deliver to send it."
        )
        return 2

    from multi_agent_orchestration.langsmith_delivery import (
        API_KEY_VARIABLE,
        ORIGIN,
        PROJECT,
        LangSmithDeliveryConfig,
        LangSmithTraceDelivery,
        TraceDeliveryError,
        credential_configured,
        credential_usable,
    )

    result, trace = traced_workflow()
    delivery = LangSmithTraceDelivery(LangSmithDeliveryConfig(mode="langsmith-live"))
    output = result.result.output
    print(f"Workflow result (deterministic, no model inference): {output}")
    print(f"Destination: {ORIGIN}; project: {PROJECT}; runs: {1 + len(trace.steps)}")
    print("Write: one POST /runs/batch through the SDK batch method; no retry")
    configured = "not set"
    if credential_configured():
        # Only whether the format is usable is shown; never content or length.
        form = "valid" if credential_usable() else "invalid"
        configured = f"set (format {form})"
    print(f"Credential variable {API_KEY_VARIABLE}: {configured}")
    if args.preview:
        print("Preview only. Nothing was sent. Exact runs of the batch:")
        print(json.dumps(delivery.preview(trace), indent=2, sort_keys=True))
        return 0
    try:
        receipt = delivery.deliver(trace)
    except TraceDeliveryError as error:
        # Category and message are fixed application wording, never remote text.
        print(f"Delivery failed [{error.category}]: {error}")
        hint = error.reply_hint
        if hint is not None:
            # Fixed labels and application-owned names only; no reply text.
            mentions = ", ".join(hint.mentions) or "none"
            print(
                f"Reply classification: declared {hint.declared}; observed "
                f"{hint.observed}; complete: {hint.complete}; "
                f"mentions: {mentions}"
            )
            sent = "yes" if error.workspace_header_sent else "no"
            print(f"Workspace header sent: {sent}")
        print("The workflow result above is unaffected.")
        return 1
    print(receipt.model_dump_json(indent=2))
    if receipt.confirmation != "service_read":
        print(
            "LangSmith accepted every run, but the trace could not be read back "
            f"in the bounded window [{receipt.read_failure}]. Delivery is not "
            "confirmed."
        )
        return 3
    print("Delivery confirmed: LangSmith returned the delivered root run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
