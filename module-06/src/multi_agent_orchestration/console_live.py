"""Additive live console definitions; loaded only after run admission.

Deterministic console startup never imports this module (a repository pin
keeps the live contract family out of that bootstrap). The operations console
delegates here inside ``run_live``/``live_runs`` only, after a submission was
admitted. Every contract type used here is from the additive live family.
"""

import asyncio
import time
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import Field, model_validator

from .canonical_contracts import (
    CanonicalWorkflowReceipt,
    EvidenceSource,
    LiveWorkflowEvent,
)
from .contracts import Contract
from .live_contracts import (
    ExecutionClass,
    LiveAuthorization,
    LiveBudget,
    LiveFailure,
    LiveFailureCategory,
    ModelSelection,
)
from .live_errors import LiveValidationError
from .live_observation import LiveTerminalObservation
from .observability import Observability
from .observability_adapters import LocalOpenTelemetry
from .observability_contracts import Outcome

ProjectionStatus = Literal["recorded", "refused", "failed", "unavailable"]


class LiveRequest(Contract):
    """Console submission for the synthetic canonical live demonstration."""

    instruction: Annotated[str, Field(strict=True, min_length=1, max_length=4096)] = (
        Field(repr=False)
    )

    @model_validator(mode="after")
    def bounded_text(self):
        """Mirror the accepted runtime input checks before any execution."""
        if not self.instruction.strip():
            raise ValueError("Synthetic task text is required.")
        try:
            self.instruction.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("Invalid surrogate text.") from None
        return self


class LiveRun(Contract):
    """Temporary curated view of one synthetic canonical live run; not a store."""

    finished_ns: Annotated[int, Field(strict=True, ge=1)]
    outcome: Outcome
    receipt: CanonicalWorkflowReceipt | None = None
    failure: LiveFailure | None = None
    terminal: LiveTerminalObservation | None = None
    events: Annotated[tuple[LiveWorkflowEvent, ...], Field(max_length=32)] = ()
    observation: Literal["local", "degraded", "unavailable"]
    langsmith: ProjectionStatus = "unavailable"
    otel: ProjectionStatus = "unavailable"
    metrics: ProjectionStatus = "unavailable"

    @model_validator(mode="after")
    def correlated(self):
        identity = set()
        for model in (
            self.receipt.result.evidence if self.receipt is not None else None,
            self.failure,
            self.terminal,
        ):
            if model is not None:
                identity.add((model.workflow_id, model.task_id))
        if len(identity) > 1 or (
            self.events
            and (
                not identity
                or any(
                    (event.workflow_id, event.task_id) not in identity
                    for event in self.events
                )
            )
        ):
            raise ValueError("Console live correlation is invalid.")
        if self.outcome == Outcome.COMPLETED:
            if self.receipt is None or self.failure is not None:
                raise ValueError("Completion requires a receipt and no failure.")
            if self.receipt.evidence_source != EvidenceSource.SYNTHETIC_OFFLINE:
                raise ValueError("Console live receipts are synthetic offline only.")
        else:
            if self.receipt is not None:
                raise ValueError("Failure cannot carry a success receipt.")
            if self.outcome == Outcome.CANCELLED:
                if self.failure is not None:
                    raise ValueError("Cancellation cannot carry a failure.")
            elif self.failure is None:
                raise ValueError("A refused outcome requires the sanitized failure.")
        if self.terminal is not None and self.terminal.outcome != self.outcome:
            raise ValueError("Console live terminal correlation is invalid.")
        return self


def live_outcome(category: LiveFailureCategory) -> Outcome:
    """Application-owned explicit mapping from the closed failure category."""
    return {
        LiveFailureCategory.AUTHORIZATION_REFUSED: Outcome.DENIED,
        LiveFailureCategory.BUDGET_REFUSED: Outcome.DENIED,
        LiveFailureCategory.TIMED_OUT: Outcome.TIMED_OUT,
    }.get(LiveFailureCategory(category), Outcome.FAILED)




def validate(raw: object) -> LiveRequest:
    """Revalidate one untrusted console submission as a live request."""
    from .console import fresh

    return fresh(raw, LiveRequest)


def runs(records) -> tuple[LiveRun, ...]:
    """Revalidate retained live views; a corrupted one clears the whole set."""
    from .console import fresh

    try:
        return tuple(fresh(record, LiveRun) for record in records)
    except (ValueError, TypeError):
        records.clear()
        return ()


def execute(session, command: LiveRequest) -> LiveRun:
    """Run the canonical live workflow with the synthetic gateway only."""
    from .canonical_workflow import (
        CanonicalWorkflowError,
        execute_canonical_workflow,
    )
    from .console import (
        ConsoleFaultError,
        ConsoleRequestError,
        fresh,
    )
    from .live_langsmith import project_live_observation as project_langsmith
    from .live_metrics import LiveOperationalMetrics
    from .live_otel import project_live_observation as project_otel
    from .synthetic_gateway import synthetic_gateway_factory

    authorization = LiveAuthorization(
        mode="live-model",
        selection=ModelSelection(
            execution_class=ExecutionClass.LOCAL_MODEL_INFERENCE,
            provider="ollama",
            model="qwen2.5-coder:7b",
        ),
        budget=LiveBudget(
            max_model_calls=4,
            max_repair_attempts=1,
            max_concurrency=1,
            deadline_ms=30000,
            call_timeout_ms=5000,
            max_input_chars=4096,
            max_output_tokens=256,
            max_reply_bytes=4096,
        ),
    )
    observer = Observability()
    workflow_id, task_id = uuid4(), uuid4()
    try:
        receipt = fresh(
            asyncio.run(
                execute_canonical_workflow(
                    command.instruction,
                    authorization=authorization,
                    gateway_factory=synthetic_gateway_factory,
                    observer=observer,
                    workflow_id=workflow_id,
                    task_id=task_id,
                )
            ),
            CanonicalWorkflowReceipt,
        )
        outcome, failure = Outcome.COMPLETED, None
    except CanonicalWorkflowError as error:
        receipt, failure = None, fresh(error.failure, LiveFailure)
        outcome = live_outcome(error.failure.category)
    except asyncio.CancelledError:
        receipt, outcome, failure = None, Outcome.CANCELLED, None
    except LiveValidationError as refused:
        # Runtime input checks run here before process creation; only a
        # runtime that never recorded observation is a caller input refusal.
        if observer.live_records or observer.live_terminal_records:
            raise ConsoleFaultError(
                "The live demonstration ended without a recordable result."
            ) from refused
        raise ConsoleRequestError(
            "The submitted synthetic text was refused before execution."
        ) from refused
    terminal = None
    records = observer.live_terminal_records
    if records:
        terminal = fresh(records[-1], LiveTerminalObservation)
    events = tuple(
        fresh(event, LiveWorkflowEvent) for event in observer.live_records
    )
    langsmith, otel, metrics_status = (
        "unavailable",
        "unavailable",
        "unavailable",
    )
    adapter = None
    if terminal is not None:
        try:
            project_langsmith(terminal)
            langsmith = "recorded"
        except LiveValidationError:
            langsmith = "refused"
        except (Exception, asyncio.CancelledError):
            langsmith = "unavailable"
        try:
            adapter = LocalOpenTelemetry()
            otel = project_otel(observer, terminal.trace_id, adapter=adapter).status
        except (Exception, asyncio.CancelledError):
            pass
        finally:
            try:
                if adapter is not None:
                    adapter.close()
            except (Exception, asyncio.CancelledError):
                otel = "unavailable"
        window = None
        try:
            window = LiveOperationalMetrics()
            metrics_status = window.record(observer, terminal.trace_id).status
        except (Exception, asyncio.CancelledError):
            pass
        finally:
            try:
                if window is not None:
                    window.close()
            except (Exception, asyncio.CancelledError):
                metrics_status = "unavailable"
    observation = "unavailable" if terminal is None else (
        "local" if langsmith == "recorded" and otel == "recorded" else "degraded"
    )
    try:
        view = LiveRun(
            finished_ns=time.time_ns(),
            outcome=outcome,
            receipt=receipt,
            failure=failure,
            terminal=terminal,
            events=events,
            observation=observation,
            langsmith=langsmith,
            otel=otel,
            metrics=metrics_status,
        )
    except ValueError:
        raise ConsoleFaultError(
            "The live demonstration ended without a recordable result."
        ) from None
    session._live.append(view)
    return view
