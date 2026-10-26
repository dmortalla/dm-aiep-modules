"""S5 trusted local embedding seam and payload-free current-run presentation.

Default public rendering has no capability. Only trusted application embedding
code may supply the context; never use a widget, environment flag or credential
to populate it. This is not a public deployment identity/authorization boundary.
Live contracts, SDKs and the canonical service load only after explicit action.
"""

import asyncio
import threading
import time
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from .cockpit_view import EvidenceView, ExecutionKind, PresentationProvenance
from .contracts import Contract

ACTION = "Run authorized local live workflow"
TASK = "Review a bounded plan for reliable multi-agent orchestration."
PROFILE_TEXT = (
    "NORMAL (ADR-008): Ollama · qwen2.5-coder:7b · 200,000 ms wall-clock · "
    "45,000 ms per call · 3 expected / 4 maximum calls · 1 repair maximum · "
    "0 retries · concurrency 1 · input 4,096 characters · output 4,096 tokens · "
    "reply 16,000 bytes. No provider escalation or automatic rerun."
)
_LOCAL: ContextVar["TrustedLocalRuntime | None"] = ContextVar("s5_local", default=None)


# Accepted closed ``LiveFailureCategory`` values, mirrored as plain strings so the
# presentation packet loads without importing live dependencies on render.
AcceptedCategory = Literal[
    "authorization_refused",
    "budget_refused",
    "budget_exhausted",
    "malformed_output",
    "output_too_large",
    "timed_out",
    "provider_authentication_failed",
    "provider_authorization_failed",
    "rate_limited",
    "provider_service_failed",
    "connection_failed",
    "unexpected_provider_failure",
]
Failure = Literal[
    "unavailable",
    "authorization_refused",
    "busy",
    "runtime_failure",
    "validation_failure",
    "provider_unavailable",
    "budget_exhausted",
    "timed_out",
]
_GUIDANCE: dict[str, str] = {
    "unavailable": (
        "No trusted private-operator capability is supplied in this posture. "
        "Nothing ran. Use Demo, or launch the cockpit through a trusted private "
        "embedding that supplies the capability."
    ),
    "authorization_refused": (
        "Fresh execution authority was refused or no longer valid. Nothing "
        "further ran; select the action again to issue new authority."
    ),
    "busy": (
        "Another local execution is in progress. Nothing else ran; wait for it "
        "to finish before a new explicit action."
    ),
    "runtime_failure": (
        "The local runtime could not complete the attempt. Check that the "
        "trusted runtime and its live dependencies are installed, then retry "
        "explicitly."
    ),
    "validation_failure": (
        "Model output or execution evidence failed application validation and "
        "was discarded. No unvalidated output is shown."
    ),
    "provider_unavailable": (
        "The local provider/model did not complete the call. Check that Ollama "
        "is running with qwen2.5-coder:7b available, then retry explicitly."
    ),
    "budget_exhausted": (
        "The NORMAL call/repair budget was spent. No further model call was made."
    ),
    "timed_out": (
        "The NORMAL deadline or per-call bound was reached; the run failed "
        "closed. A cold model load can cause this; retry only explicitly."
    ),
}


def failure_guidance(failure: str) -> str:
    """Return fixed actionable wording for one closed failure value.

    Args:
        failure: A closed ``CurrentLocalRun.failure`` value.

    Returns:
        Application-owned guidance; never diagnostic or provider text.

    Raises:
        KeyError: The value is not one of the closed failure values.
    """
    return _GUIDANCE[failure]


class LocalIntentError(ValueError):
    """Fixed refusal; no external diagnostic or authority material."""


class CurrentLocalRun(Contract):
    """Only bounded presentation facts; no payload, client, grant or authority.

    Attributes:
        finished_ns: Wall-clock marker of when the attempt finished.
        evidence: S1 evidence view: ``canonical_real_local`` with
            ``local_provider_execution`` and ``not_sent``, or ``unavailable``
            for a refusal that executed nothing.
        outcome: Closed workflow outcome of this attempt.
        failure: Coarse closed failure value, ``None`` only on completion.
        category: The accepted ``LiveFailureCategory`` verbatim, when the
            canonical boundary reported one.
        workflow_id: Application-owned correlation identifier.
        task_id: Application-owned task identifier.
        trace_id: Correlated finalized local trace identifier.
        model_calls: Model calls, bounded by the NORMAL profile.
        repair_attempts: Repairs, bounded by the NORMAL profile.
        transport_retries: Always zero when known.
        duration_ms: Observed workflow duration.
        input_tokens: Provider-reported input tokens, when available.
        output_tokens: Provider-reported output tokens, when available.
        validated_roles: Number of roles that passed validation.
        cleanup: Supervised child cleanup state.
        langsmith: Local LangSmith projection status (never a delivery).
        otel: Local OpenTelemetry projection status (never an export).
        metrics: Local metric-window status (never a delivery).
    """

    finished_ns: Annotated[int, Field(strict=True, ge=1)]
    evidence: EvidenceView
    outcome: Literal["completed", "failed", "timed_out", "cancelled", "denied"]
    failure: Failure | None = None
    # The accepted closed category when the canonical boundary reported one.
    category: AcceptedCategory | None = None
    workflow_id: UUID | None = None
    task_id: UUID | None = None
    trace_id: UUID | None = None
    model_calls: Annotated[int, Field(strict=True, ge=0, le=4)] | None = None
    repair_attempts: Annotated[int, Field(strict=True, ge=0, le=1)] | None = None
    transport_retries: Literal[0] | None = None
    duration_ms: Annotated[float, Field(ge=0, le=302000)] | None = None
    # Mirror accepted MAX_TOKEN_COUNT without importing live dependencies on render.
    input_tokens: Annotated[int, Field(strict=True, ge=0, le=1_000_000)] | None = None
    output_tokens: Annotated[int, Field(strict=True, ge=0, le=1_000_000)] | None = None
    validated_roles: Annotated[int, Field(strict=True, ge=0, le=3)] = 0
    cleanup: Literal["not_started", "reaped", "failed", "unknown"] | None = None
    langsmith: Literal["recorded", "refused", "failed", "unavailable"] = "unavailable"
    otel: Literal["recorded", "refused", "failed", "unavailable"] = "unavailable"
    metrics: Literal["recorded", "refused", "failed", "unavailable"] = "unavailable"

    @model_validator(mode="after")
    def observational_only(self) -> "CurrentLocalRun":
        """Reject delivery claims and completions lacking correlated NORMAL facts.

        Raises:
            ValueError: An unavailable packet carries execution facts, a
                current packet claims delivery, outcome and failure disagree,
                or a completion lacks correlated NORMAL-profile facts.
        """
        if self.evidence.execution_kind == ExecutionKind.UNAVAILABLE:
            if self.outcome != "denied" or self.trace_id is not None:
                raise ValueError("Unavailable is not execution evidence.")
        elif (
            self.evidence.execution_kind != ExecutionKind.CANONICAL_REAL_LOCAL
            or self.evidence.delivery_confirmation != "not_sent"
        ):
            raise ValueError("Current local presentation cannot claim delivery.")
        if (self.outcome == "completed") != (self.failure is None) or (
            self.category is not None and self.failure is None
        ):
            raise ValueError("Current outcome and failure must agree.")
        if self.outcome == "completed" and (
            any(
                identity is None or identity.int == 0
                for identity in (self.workflow_id, self.task_id, self.trace_id)
            )
            or self.repair_attempts is None
            or self.model_calls != 3 + self.repair_attempts
            or self.validated_roles != 3
            or self.cleanup != "reaped"
            or self.duration_ms is None
            or self.duration_ms > 200000
        ):
            raise ValueError("Completed presentation requires correlated NORMAL facts.")
        return self


def refused(reason: Failure) -> CurrentLocalRun:
    """Build a nonexecuted refusal without historical data.

    Args:
        reason: One application-owned closed failure category.

    Returns:
        Payload-free current-attempt evidence.
    """
    return CurrentLocalRun(
        finished_ns=time.time_ns(),
        evidence=EvidenceView(execution_kind=ExecutionKind.UNAVAILABLE),
        outcome="denied",
        failure=reason,
    )


class _Permit:
    """Ephemeral owner-bound grant; intentionally never serializable UI state."""

    def __init__(self, authorization: object) -> None:
        self.authorization = authorization
        self.workflow_id, self.task_id = uuid4(), uuid4()
        self.issued = time.monotonic()

    def __repr__(self) -> str:
        return "<execution-scoped local intent>"


class TrustedLocalRuntime:
    """Capability supplied only by a trusted private-local embedding.

    Args:
        posture: Explicit private-operator declaration, never visitor input.
        executor: Trusted offline test seam; None reuses the accepted canonical
            real-local service with its existing default gateway.

    No readiness probe, credential discovery or authority is created here.
    Embeddings must restrict access to trusted operators; this object must not
    be installed in a public app or in Streamlit session state.
    """

    def __init__(
        self,
        *,
        posture: Literal["trusted-private-local"],
        executor: Callable[..., Awaitable[object]] | None = None,
    ) -> None:
        if type(posture) is not str or posture != "trusted-private-local":
            raise LocalIntentError("A trusted private local runtime is required.")
        self._executor = executor
        self._lock = threading.Lock()
        self._pending: _Permit | None = None

    def issue(self, *, explicit_action: str) -> _Permit:
        """Issue fresh NORMAL authority only for an immediately approved action.

        Args:
            explicit_action: Exact application action associated with human submit.

        Returns:
            A short-lived owner-bound permit; never place it in session state.

        Raises:
            LocalIntentError: Missing intent, busy runtime or outstanding grant.
        """
        if type(explicit_action) is not str or explicit_action != ACTION:
            raise LocalIntentError("Fresh explicit local execution intent is required.")
        if not self._lock.acquire(blocking=False):
            raise LocalIntentError("The local runtime is busy.")
        try:
            if (
                self._pending is not None
                and time.monotonic() - self._pending.issued < 30
            ):
                raise LocalIntentError("An execution intent is already outstanding.")
            from .live_contracts import LiveAuthorization, LiveBudget, ModelSelection

            # S5 action-scoped construction, not a default/factory in policy data.
            authorization = LiveAuthorization(
                mode="live-model",
                selection=ModelSelection(
                    execution_class="local_model_inference",
                    provider="ollama",
                    model="qwen2.5-coder:7b",
                ),
                # State every approved value at this fresh action call site.
                # Policy data must never be consumed as execution authority.
                budget=LiveBudget(
                    max_model_calls=4,
                    max_repair_attempts=1,
                    max_concurrency=1,
                    deadline_ms=200_000,
                    call_timeout_ms=45_000,
                    max_input_chars=4096,
                    max_output_tokens=4096,
                    max_reply_bytes=16000,
                ),
            )
            self._pending = _Permit(authorization)
            return self._pending
        finally:
            self._lock.release()

    def consume(self, permit: object) -> CurrentLocalRun:
        """Consume exactly once before delegating to the accepted live boundary.

        The pending grant and its authorization are cleared before validation
        or execution, so a failed, timed-out or cancelled attempt can never
        reopen it. Every failure becomes a closed refusal or outcome value.

        Args:
            permit: Exact outstanding owner-bound intent, at most 30 seconds old.

        Returns:
            Sanitized current evidence or fixed refusal; never the authority.
        """
        if not self._lock.acquire(blocking=False):
            return refused("busy")
        try:
            if type(permit) is not _Permit or permit is not self._pending:
                return refused("authorization_refused")
            self._pending = None  # consume even if expired, invalid or execution fails
            authorization, permit.authorization = permit.authorization, None
            if not 0 <= time.monotonic() - permit.issued < 30:
                return refused("authorization_refused")
            from .live_contracts import require_live_authorization
            from .live_errors import LiveExecutionError, LiveValidationError

            try:
                checked = require_live_authorization(authorization)
                if (
                    checked.budget.model_dump()
                    != dict(
                        max_model_calls=4,
                        max_repair_attempts=1,
                        max_concurrency=1,
                        deadline_ms=200_000,
                        call_timeout_ms=45_000,
                        max_input_chars=4096,
                        max_output_tokens=4096,
                        max_reply_bytes=16000,
                    )
                    or checked.selection.provider != "ollama"
                    or checked.selection.model != "qwen2.5-coder:7b"
                ):
                    return refused("authorization_refused")
            except (ValueError, LiveExecutionError, LiveValidationError):
                return refused("authorization_refused")
            try:
                return _execute(
                    self._executor, checked, permit.workflow_id, permit.task_id
                )
            except (Exception, asyncio.CancelledError):
                # Missing dependencies or malformed infrastructure cannot expose
                # diagnostics or reopen consumed authority at this public seam.
                return refused("runtime_failure")
        finally:
            self._lock.release()


@contextmanager
def trusted_local_context(runtime: TrustedLocalRuntime) -> Iterator[None]:
    """Inject a private operator capability for this execution context only.

    Trusted embedding code owns caller identity/access, never a reviewer widget.
    This does not implement or verify a deployment-compatible authority boundary.

    Args:
        runtime: Application-owned capability for an already private operator UI.

    Yields:
        A render context, restored even if rendering fails.

    Raises:
        LocalIntentError: The supplied capability is not the exact owned type.
    """
    if type(runtime) is not TrustedLocalRuntime:
        raise LocalIntentError("An owned private local capability is required.")
    token = _LOCAL.set(runtime)
    try:
        yield
    finally:
        _LOCAL.reset(token)


def current_runtime() -> TrustedLocalRuntime | None:
    """Return only an explicitly injected context; never discover one.

    Returns:
        Trusted runtime, or None in the default/public posture.
    """
    runtime = _LOCAL.get()
    return runtime if type(runtime) is TrustedLocalRuntime else None


def run_explicit_action() -> CurrentLocalRun:
    """Application submit boundary; fresh authority and no automatic retry.

    Returns:
        Sanitized current evidence or refusal; never a grant/authorization.
    """
    runtime = current_runtime()
    if runtime is None:
        return refused("unavailable")
    try:
        permit = runtime.issue(explicit_action=ACTION)
        return runtime.consume(permit)
    except LocalIntentError:
        return refused("authorization_refused")


def _execute(
    executor: Callable[..., Awaitable[object]] | None,
    authorization: object,
    workflow_id: UUID,
    task_id: UUID,
) -> CurrentLocalRun:
    """Run the accepted canonical boundary once and keep only closed facts.

    Args:
        executor: Trusted offline seam, or None for the accepted canonical
            service with its default local gateway.
        authorization: Freshly validated execution-scoped authority.
        workflow_id: Application-owned correlation identifier for this action.
        task_id: Application-owned task identifier for this action.

    Returns:
        Payload-free current evidence. Expected failures are outcome values.
    """
    from .canonical_contracts import CanonicalWorkflowReceipt, EvidenceSource
    from .canonical_workflow import CanonicalWorkflowError, execute_canonical_workflow
    from .console import fresh
    from .live_contracts import LiveFailure
    from .live_errors import LiveValidationError
    from .observability import Observability

    observer = Observability()
    outcome, failure, receipt, category = "failed", None, None, None
    try:
        raw = asyncio.run(
            (executor or execute_canonical_workflow)(
                TASK,
                authorization=authorization,
                observer=observer,
                workflow_id=workflow_id,
                task_id=task_id,
            )
        )
        receipt = fresh(raw, CanonicalWorkflowReceipt)
        evidence = receipt.result.evidence
        if (
            receipt.evidence_source != EvidenceSource.LOCAL_PROVIDER_EXECUTION
            or evidence.workflow_id != workflow_id
            or evidence.task_id != task_id
            or evidence.budget != authorization.budget
            or evidence.selection != authorization.selection
        ):
            raise LiveValidationError()
        outcome = "completed"
    except CanonicalWorkflowError as error:
        try:
            report = fresh(error.failure, LiveFailure)
            if (
                report.workflow_id != workflow_id
                or report.task_id != task_id
                or error.evidence_source != EvidenceSource.LOCAL_PROVIDER_EXECUTION
            ):
                raise LiveValidationError()
            category = report.category.value
            outcome = (
                "timed_out"
                if category == "timed_out"
                else "denied"
                if category in ("authorization_refused", "budget_refused")
                else "failed"
            )
            failure = (
                "timed_out"
                if category == "timed_out"
                else "authorization_refused"
                if outcome == "denied"
                else "validation_failure"
                if category in ("malformed_output", "output_too_large")
                else "budget_exhausted"
                if category == "budget_exhausted"
                else "provider_unavailable"
            )
        except (ValueError, TypeError, LiveValidationError):
            failure = "validation_failure"
    except LiveValidationError:
        failure = "validation_failure"
    except asyncio.CancelledError:
        outcome, failure = "cancelled", "runtime_failure"
    except Exception:
        # Real application failure boundary: no raw exception retained or rendered.
        failure = "runtime_failure"
    terminal = next(
        (
            r
            for r in observer.live_terminal_records
            if r.workflow_id == workflow_id
            and r.task_id == task_id
            and r.evidence_source == EvidenceSource.LOCAL_PROVIDER_EXECUTION
            and r.outcome.value == outcome
        ),
        None,
    )
    values = {}
    if (
        terminal is not None
        and outcome == "completed"
        and (
            terminal.trace_id != receipt.result.evidence.trace_id
            or terminal.facts.model_calls
            != receipt.result.evidence.accounting.model_calls
            or terminal.facts.repair_attempts
            != receipt.result.evidence.accounting.repair_attempts
        )
    ):
        terminal = None
    if terminal is not None:
        values = dict(
            trace_id=terminal.trace_id,
            model_calls=terminal.facts.model_calls,
            repair_attempts=terminal.facts.repair_attempts,
            transport_retries=terminal.facts.transport_retries,
            duration_ms=terminal.duration_ms,
            input_tokens=terminal.facts.usage.input_tokens,
            output_tokens=terminal.facts.usage.output_tokens,
            validated_roles=len(terminal.roles),
            cleanup=terminal.facts.cleanup.value,
        )
        for name, operation in (
            ("langsmith", lambda: _project_smith(terminal)),
            ("otel", lambda: _project_otel(observer, terminal)),
            ("metrics", lambda: _project_metrics(observer, terminal)),
        ):
            try:
                values[name] = operation()
            except (Exception, asyncio.CancelledError):
                values[name] = (
                    "unavailable"  # projection failure is not workflow failure
                )
    if outcome == "completed" and terminal is None:
        outcome, failure = "failed", "validation_failure"
    return CurrentLocalRun(
        finished_ns=time.time_ns(),
        evidence=EvidenceView(
            execution_kind=ExecutionKind.CANONICAL_REAL_LOCAL,
            provenance=PresentationProvenance.LOCAL_PROVIDER_EXECUTION,
            delivery_confirmation="not_sent",
        ),
        outcome=outcome,
        failure=failure,
        category=category,
        workflow_id=workflow_id,
        task_id=task_id,
        **values,
    )


def _project_smith(terminal) -> str:
    from .live_langsmith import project_live_observation

    project_live_observation(terminal)
    return "recorded"


def _project_otel(observer, terminal) -> str:
    from .live_otel import project_live_observation
    from .observability_adapters import LocalOpenTelemetry

    adapter = LocalOpenTelemetry()
    try:
        return project_live_observation(
            observer, terminal.trace_id, adapter=adapter
        ).status
    finally:
        adapter.close()


def _project_metrics(observer, terminal) -> str:
    from .live_metrics import LiveOperationalMetrics

    window = LiveOperationalMetrics()
    try:
        return window.record(observer, terminal.trace_id).status
    finally:
        window.close()
