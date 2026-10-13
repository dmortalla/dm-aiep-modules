"""Additive immutable contracts for the live-model path; no model can run here.

The accepted deterministic contracts are unchanged and keep their meaning: they
still describe zero-call offline execution. These sibling types describe a
future explicitly authorized model-backed run of the accepted sequential plan.
Application code owns authorization, model selection, budgets and evidence;
model-produced schemas hold bounded content only. Nothing in this module reads
the environment, a credential or the network, or constructs a provider.
"""

import unicodedata
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidatorFunctionWrapHandler,
    WrapValidator,
    model_validator,
)

from .contracts import (
    Contract,
    ExecutionStatus,
    GraphRecord,
    GraphRole,
    GraphTopology,
    RuntimeId,
)
from .live_errors import LiveExecutionError, LiveFailureCategory
from .topologies import topology_plan

# The accepted sequential plan fixes the content roles; nothing here adds one.
LIVE_ROLES = topology_plan(GraphTopology.SEQUENTIAL).roles
PLANNED_MODEL_CALLS = len(LIVE_ROLES)
MAX_REPAIR_ATTEMPTS = 1
MAX_MODEL_CALLS = PLANNED_MODEL_CALLS + MAX_REPAIR_ATTEMPTS
# Hard ceilings, not defaults: a budget must still state every value explicitly.
# The deadline ceiling is provisional until a separately authorized measurement.
MAX_DEADLINE_MS = 300_000
MAX_INPUT_CHARS = 4096
MAX_OUTPUT_TOKENS = 4096
MAX_REPLY_BYTES = 16_000
MAX_TOKEN_COUNT = 1_000_000


class ExecutionClass(StrEnum):
    """Application-owned evidence classification; never taken from model output."""

    DETERMINISTIC_OFFLINE = "deterministic_offline"
    LOCAL_MODEL_INFERENCE = "local_model_inference"


def _visible(value: str) -> str:
    """Reject blank text and control, format or line-separator characters."""
    if not value.strip() or any(
        unicodedata.category(char)[0] == "C"
        or unicodedata.category(char) in ("Zl", "Zp")
        for char in value
    ):
        raise ValueError("Model text must be visible single-line text.")
    return value


class LiveContract(Contract):
    """Internal typed primitive: closed, frozen, with nested revalidation.

    Hidden input values are defense in depth, not safe error serialization:
    attacker-controlled field names can remain in raw validation errors.
    Constructors and Pydantic validators/accessors are internal operations;
    services use the sanitized boundaries in live_validation, or the dedicated
    authorization/reply boundaries. Never log or expose raw validation errors.
    Nested contract instances are
    always revalidated, so an object built with ``model_construct`` is never
    trusted merely for being an instance of the right type.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class ModelProduced(LiveContract):
    """Base for content a model wrote: bounded data, never policy or authority.

    Unknown fields are rejected, so output cannot carry a provider, model,
    budget, tool, capability or authorization. Public parsing sanitizes errors.
    """


class ResearchOutput(ModelProduced):
    """Researcher content: one to three short findings for the analyst."""

    findings: Annotated[
        tuple[
            Annotated[
                str,
                Field(strict=True, min_length=1, max_length=160),
                AfterValidator(_visible),
            ],
            ...,
        ],
        Field(min_length=1, max_length=3),
    ] = Field(repr=False)


class AnalysisOutput(ModelProduced):
    """Analyst content; ``supports`` cites validated findings by one-based index."""

    assessment: Annotated[
        str, Field(strict=True, min_length=1, max_length=400), AfterValidator(_visible)
    ] = Field(repr=False)
    supports: Annotated[
        tuple[Annotated[int, Field(strict=True, ge=1, le=3)], ...],
        Field(min_length=1, max_length=3),
    ]

    @model_validator(mode="after")
    def distinct_supports(self) -> "AnalysisOutput":
        """A finding may be cited once; repetition is not additional support."""
        if len(set(self.supports)) != len(self.supports):
            raise ValueError("Cited findings must be distinct.")
        return self


class CritiqueOutput(ModelProduced):
    """Critic content. The verdict is advisory: it is reported, never acted on."""

    advisory_verdict: Literal["sound", "needs_revision"]
    rationale: Annotated[
        str, Field(strict=True, min_length=1, max_length=240), AfterValidator(_visible)
    ] = Field(repr=False)


def role_schema(role: GraphRole) -> type[ModelProduced]:
    """Return the one content schema a planned live role may produce.

    Raises:
        ValueError: The role is not part of the accepted sequential plan.
    """
    schemas = dict(
        zip(LIVE_ROLES, (ResearchOutput, AnalysisOutput, CritiqueOutput), strict=True)
    )
    if type(role) is not GraphRole or role not in schemas:
        raise ValueError("Only a planned live role has a content schema.")
    return schemas[role]


class ModelSelection(LiveContract):
    """Application-owned provider and model identity; never a credential.

    Only local open-weight execution is representable. Hosted execution would
    need a deliberate, human-approved change to this contract, so no value of
    any field can escalate a run to a billable provider.
    """

    execution_class: Literal[ExecutionClass.LOCAL_MODEL_INFERENCE]
    provider: Annotated[str, Field(strict=True, pattern=r"^[a-z][a-z0-9_]{0,31}$")]
    # A name, optional path segments and one optional tag; never a URL.
    model: Annotated[
        str,
        Field(
            strict=True,
            max_length=96,
            pattern=(
                r"^[a-z0-9][a-z0-9._-]*(/[a-z0-9][a-z0-9._-]*)*"
                r"(:[a-z0-9][a-z0-9._-]*)?$"
            ),
        ),
    ]


class LiveBudget(LiveContract):
    """Application-owned per-run limits; every value must be stated explicitly.

    Attributes:
        max_model_calls: Hard total of model calls, repair included.
        max_repair_attempts: Malformed-output repairs allowed in the whole run.
        max_concurrency: Model calls in flight at once; the plan is sequential.
        deadline_ms: Wall-clock bound for the whole run.
        call_timeout_ms: Wall-clock bound for one model call.
        max_input_chars: Bound on task text accepted for a live run.
        max_output_tokens: Output limit requested from the provider per call.
            A provider enforces it; the application-enforced bound is
            ``max_reply_bytes``.
        max_reply_bytes: Hard bound on one reply the application will read.
    """

    max_model_calls: Annotated[
        int, Field(strict=True, ge=PLANNED_MODEL_CALLS, le=MAX_MODEL_CALLS)
    ]
    max_repair_attempts: Annotated[
        int, Field(strict=True, ge=0, le=MAX_REPAIR_ATTEMPTS)
    ]
    max_concurrency: Annotated[int, Field(strict=True, ge=1, le=1)]
    deadline_ms: Annotated[int, Field(strict=True, ge=1, le=MAX_DEADLINE_MS)]
    call_timeout_ms: Annotated[int, Field(strict=True, ge=1, le=MAX_DEADLINE_MS)]
    max_input_chars: Annotated[int, Field(strict=True, ge=1, le=MAX_INPUT_CHARS)]
    max_output_tokens: Annotated[int, Field(strict=True, ge=1, le=MAX_OUTPUT_TOKENS)]
    max_reply_bytes: Annotated[int, Field(strict=True, ge=1, le=MAX_REPLY_BYTES)]

    @model_validator(mode="after")
    def consistent(self) -> "LiveBudget":
        """The call total is exactly the planned roles plus permitted repairs."""
        if self.max_model_calls != PLANNED_MODEL_CALLS + self.max_repair_attempts:
            raise ValueError("Model calls must equal planned roles plus repairs.")
        if self.call_timeout_ms > self.deadline_ms:
            raise ValueError("One call cannot outlast the run deadline.")
        return self


class LiveAuthorization(LiveContract):
    """Explicit operator authorization for one live run; there is no default.

    Its absence is deterministic execution. It carries no credential and is
    built only by trusted operator code. A running model service, an installed
    model, a configured provider or model name, a present credential and model
    output are all unable to produce or alter one.
    """

    mode: Literal["live-model"]
    selection: ModelSelection
    budget: LiveBudget


def _declared(value: object, schema: type[Contract]) -> dict:
    """Copy the declared fields of an exact instance out as untrusted data.

    Being an instance proves nothing: ``model_construct`` and direct attribute
    writes both produce one without validation. Only the copied values are
    used, and only after they pass normal validation from plain data.
    """
    if type(value) is not schema or set(value.__dict__) != set(schema.model_fields):
        raise ValueError("Not an exact application contract with declared fields.")
    return dict(value.__dict__)


def require_live_authorization(candidate: object) -> LiveAuthorization:
    """Establish a validated authorization or refuse before anything runs.

    Authority comes from this function's validation, never from the identity
    or provenance of the object supplied. The candidate is untrusted input: its
    declared fields are copied out as plain data, nested contracts included,
    and passed through normal ``LiveAuthorization`` validation. The supplied
    object is then discarded and only the newly validated instance is returned.

    An object made with ``model_construct`` is therefore neither trusted nor
    refused for how it was made. It is accepted only when every copied value
    passes full validation, exactly as if an operator had written those values,
    and refused otherwise. Subclasses, mappings, objects holding undeclared
    state and anything else that is not exactly a ``LiveAuthorization`` are
    refused, so model-produced content can never be supplied as authority.

    A future live service calls this before any gateway, provider or model
    object exists. It reads no environment variable, credential or network
    state, so availability cannot substitute for authorization.

    Args:
        candidate: Untrusted value.

    Returns:
        A new instance validated from plain data; never the candidate itself.

    Raises:
        LiveExecutionError: ``authorization_refused`` when no exact, valid
            authorization is supplied; ``budget_refused`` when only its budget
            is not an exact, valid ``LiveBudget``. Neither carries input values.
    """
    selection_valid = False
    try:
        raw = _declared(candidate, LiveAuthorization)
        if type(raw["mode"]) is not str or raw["mode"] != "live-model":
            raise ValueError("Live mode was not selected.")
        selection = _declared(raw["selection"], ModelSelection)
        ModelSelection.model_validate(selection)
        selection_valid = True
    except (ValueError, TypeError, AttributeError, KeyError):
        pass
    if not selection_valid:
        raise LiveExecutionError(LiveFailureCategory.AUTHORIZATION_REFUSED) from None
    budget_valid = False
    try:
        budget = _declared(raw["budget"], LiveBudget)
        LiveBudget.model_validate(budget)
        budget_valid = True
    except (ValueError, TypeError, AttributeError):
        pass
    if not budget_valid:
        raise LiveExecutionError(LiveFailureCategory.BUDGET_REFUSED) from None
    try:
        # The one canonical path: plain data through normal validation.
        return LiveAuthorization.model_validate(
            {"mode": raw["mode"], "selection": selection, "budget": budget}
        )
    except ValueError:
        pass
    raise LiveExecutionError(LiveFailureCategory.AUTHORIZATION_REFUSED) from None


TokenCount = Annotated[int, Field(strict=True, ge=0, le=MAX_TOKEN_COUNT)]


class ModelUsage(LiveContract):
    """Provider-reported token counts; ``None`` means unavailable, never zero."""

    input_tokens: TokenCount | None = None
    output_tokens: TokenCount | None = None


class LiveAccounting(LiveContract):
    """Application-counted calls plus provider-reported usage when available.

    No monetary amount is representable: local inference has no provider
    charge, and that is a statement about billing, not about compute being free.
    """

    model_calls: Annotated[
        int, Field(strict=True, ge=PLANNED_MODEL_CALLS, le=MAX_MODEL_CALLS)
    ]
    repair_attempts: Annotated[int, Field(strict=True, ge=0, le=MAX_REPAIR_ATTEMPTS)]
    transport_retries: Literal[0] = 0
    usage: ModelUsage
    cost_status: Literal["no_provider_charge_local_compute"] = (
        "no_provider_charge_local_compute"
    )

    @model_validator(mode="after")
    def repairs_are_counted_calls(self) -> "LiveAccounting":
        """A repair is a model call inside the hard total, never beside it."""
        if self.model_calls != PLANNED_MODEL_CALLS + self.repair_attempts:
            raise ValueError("Model calls must equal planned roles plus repairs.")
        return self


def _canonical_record(
    value: object, handler: ValidatorFunctionWrapHandler
) -> GraphRecord:
    """Rebuild one plan record from plain declared data; never keep the input.

    ``GraphRecord`` is an accepted contract without nested revalidation, so a
    supplied instance proves nothing. Only an exact ``GraphRecord`` is read,
    and only its declared fields; subclasses and other models are refused.
    Plain data takes the normal validation path unchanged. The validated
    record is then rebuilt from its own JSON, so no caller object, primitive
    subclass, undeclared state or custom behavior survives.
    """
    if isinstance(value, BaseModel):
        state = value.__dict__
        if type(value) is not GraphRecord or any(
            name not in state for name in GraphRecord.model_fields
        ):
            raise ValueError("Not an exact plan record with declared fields.")
        value = {name: state[name] for name in GraphRecord.model_fields}
    record = handler(value)
    canonical = None
    try:
        canonical = GraphRecord.model_validate_json(record.model_dump_json())
    except ValueError:
        pass
    if canonical is None:
        # Raised after the handler so no nested diagnostic is chained.
        raise ValueError("Plan record has no canonical form.")
    return canonical


def _canonical_uuid(value: UUID) -> UUID:
    """Copy a validated identifier value without caller identity or behavior.

    Pydantic accepts UUID subclasses without copying them. Read the built-in
    UUID slot directly, bypassing subclass attributes/methods, and normalize
    its integer with the built-in operation before constructing an exact UUID.
    Input syntax/type acceptance remains the normal UUID validator's decision.
    """
    canonical = None
    try:
        canonical = UUID(int=int.__int__(UUID.int.__get__(value, UUID)))
    except (ValueError, TypeError, AttributeError):
        pass
    if canonical is None:
        raise ValueError("Identifier has no canonical UUID value.")
    return canonical


CanonicalUUID = Annotated[UUID, AfterValidator(_canonical_uuid)]


class LiveEvidence(LiveContract):
    """Application-created, payload-free evidence of one completed live run.

    It holds no prompt, task text, model output, provider payload, credential
    or free-form metadata. Classification is fixed by the application. Every
    contribution is a newly validated exact ``GraphRecord``; a supplied record
    instance is never retained.
    """

    workflow_id: CanonicalUUID
    task_id: CanonicalUUID
    execution_class: Literal[ExecutionClass.LOCAL_MODEL_INFERENCE]
    runtime: Literal[RuntimeId.LANGGRAPH]
    topology: Literal[GraphTopology.SEQUENTIAL]
    status: Literal[ExecutionStatus.COMPLETED]
    selection: ModelSelection
    budget: LiveBudget
    accounting: LiveAccounting
    duration_ms: Annotated[float, Field(strict=True, ge=0, le=MAX_DEADLINE_MS)]
    contributions: Annotated[
        tuple[Annotated[GraphRecord, WrapValidator(_canonical_record)], ...],
        Field(min_length=PLANNED_MODEL_CALLS, max_length=PLANNED_MODEL_CALLS),
    ]
    trace_id: CanonicalUUID | None = None

    @model_validator(mode="after")
    def within_authorized_bounds(self) -> "LiveEvidence":
        """Evidence cannot describe more than the plan and budget permitted."""
        plan = topology_plan(GraphTopology.SEQUENTIAL)
        expected = tuple(
            GraphRecord(
                workflow_id=self.workflow_id,
                task_id=self.task_id,
                role=role,
                sequence=index + 1,
                parent=plan.parents[index],
                sources=plan.sources[index],
            )
            for index, role in enumerate(plan.roles)
        )
        # Compared as canonical JSON text so no supplied object's equality runs.
        if (
            tuple(record.model_dump_json() for record in self.contributions)
            != tuple(record.model_dump_json() for record in expected)
            or self.selection.execution_class != self.execution_class
            or self.accounting.model_calls > self.budget.max_model_calls
            or self.accounting.repair_attempts > self.budget.max_repair_attempts
            or self.duration_ms > self.budget.deadline_ms
        ):
            raise ValueError("Live evidence contradicts its plan or budget.")
        return self


class LiveWorkflowResult(LiveContract):
    """Validated role content with its evidence; content is unverified model text.

    The critic's verdict is carried as content only. No field of the evidence
    depends on it, so it cannot become an execution-control decision.
    """

    research: ResearchOutput
    analysis: AnalysisOutput
    critique: CritiqueOutput
    evidence: LiveEvidence

    @model_validator(mode="after")
    def analysis_cites_existing_findings(self) -> "LiveWorkflowResult":
        """An analysis may cite only findings that were actually validated."""
        if max(self.analysis.supports) > len(self.research.findings):
            raise ValueError("Analysis cites a finding that does not exist.")
        return self


class LiveFailure(LiveContract):
    """Sanitized evidence of a refused or failed live run; no remote text."""

    workflow_id: CanonicalUUID
    task_id: CanonicalUUID
    category: LiveFailureCategory
    selection: ModelSelection | None = None
    model_calls: Annotated[int, Field(strict=True, ge=0, le=MAX_MODEL_CALLS)] = 0
    repair_attempts: Annotated[
        int, Field(strict=True, ge=0, le=MAX_REPAIR_ATTEMPTS)
    ] = 0

    @model_validator(mode="after")
    def truthful_accounting(self) -> "LiveFailure":
        """A refusal made no call; a repair is one of at least two calls."""
        refused = self.category in (
            LiveFailureCategory.AUTHORIZATION_REFUSED,
            LiveFailureCategory.BUDGET_REFUSED,
        )
        if (
            (refused and (self.model_calls or self.repair_attempts))
            or (self.repair_attempts and self.model_calls < 2)
            or (self.selection is None and not refused)
        ):
            raise ValueError("Failure accounting contradicts its category.")
        return self
