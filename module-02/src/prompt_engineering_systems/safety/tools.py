"""Authorize and execute two pure local tools under an application-owned session.

Proposals are plain JSON data, never callables or executable expressions. The
fixed registry accepts bounded integer addition and text counts. No detector is
consulted. Sessions are sequential counters, not wall-clock or concurrency limits.
Trusted Python code can create sessions; external content cannot reset a session,
replace its policy, register handlers, or acquire capabilities from a valid shape.
"""

from types import MappingProxyType

from pydantic import ConfigDict, Field, ValidationError

from ..contracts import JSONValue, StrictContract, ValidationLimits
from ..errors import (
    JSONParsingError,
    SafetyInputError,
    ToolAuthorizationError,
    ToolBudgetError,
    ValidationLimitError,
)
from ..structured._bounds import inspect_json
from .policy import SafetyPolicy, ToolIdentifier


class ActionProposal(StrictContract):
    """Strict untrusted action envelope; matching shape grants no permission.

    Attributes:
        tool: Nonempty opaque tool identifier, at most 128 characters.
        arguments: At most two named plain JSON values; tool contracts validate
            exact names/types/bounds after envelope preflight.

    Raises:
        ValidationError: For malformed direct construction. Session errors are safe.
    """

    tool: str = Field(min_length=1, max_length=128)
    arguments: dict[str, JSONValue] = Field(max_length=2)


class AddArguments(StrictContract):
    """Two bounded integers; no expressions, coercion, booleans, or extra fields.

    Attributes:
        left: Integer in -1,000,000..1,000,000.
        right: Integer in -1,000,000..1,000,000.

    Raises:
        ValidationError: For invalid direct construction.
    """

    left: int = Field(ge=-1_000_000, le=1_000_000)
    right: int = Field(ge=-1_000_000, le=1_000_000)


class TextStatisticsArguments(StrictContract):
    """Literal bounded text, further restricted by trusted session policy.

    Attributes:
        text: At most 4,096 Python characters, including empty text.

    Raises:
        ValidationError: For invalid direct construction.
    """

    text: str = Field(max_length=4_096)


class ToolResult(StrictContract):
    """Numerical results only; tool content and secret-like text are not echoed.

    Attributes:
        tool: Application-registered identifier that was authorized.
        values: Sum or character/whitespace-delimited word counts.

    Raises:
        ValidationError: For invalid direct construction.
    """

    model_config = ConfigDict(frozen=True)
    tool: ToolIdentifier
    values: dict[str, int]


_REGISTRY = MappingProxyType(
    {"add": AddArguments, "text_statistics": TextStatisticsArguments}
)


def _execute_local(arguments: AddArguments | TextStatisticsArguments) -> dict[str, int]:
    """Dispatch only application-owned contracts to pure bounded operations."""
    if isinstance(arguments, AddArguments):
        return {"sum": arguments.left + arguments.right}
    return {"characters": len(arguments.text), "words": len(arguments.text.split())}


class ToolSession:
    """Trusted owner of an immutable policy snapshot and a private step counter.

    Keep this object in application code, outside user/model deserialization.
    Python private state is an API boundary, not isolation from arbitrary Python
    code. Creating another session is an application authority decision.

    Attributes:
        policy: Read-only immutable, revalidated policy snapshot.
        used_executions: Number of authorized validated handler attempts. Unexpected
            handler failure still consumes one attempt; rejected inputs consume none.
    """

    def __init__(self, policy: SafetyPolicy) -> None:
        """Capture application policy, without accepting external policy mappings.

        Args:
            policy: Trusted application-authored SafetyPolicy instance.

        Raises:
            SafetyInputError: For wrong policy type or invalid copied policy fields.
        """
        if type(policy) is not SafetyPolicy:
            raise SafetyInputError(
                "Create the session with an application-owned SafetyPolicy."
            )
        try:
            self._policy = SafetyPolicy.model_validate(policy)
        except ValidationError:
            raise SafetyInputError(
                "Correct the strict safety policy fields and limits."
            ) from None
        self._used_executions = 0

    @property
    def policy(self) -> SafetyPolicy:
        """Return the immutable trusted snapshot.

        Returns:
            Application policy, without a replacement setter.
        """
        return self._policy

    @property
    def used_executions(self) -> int:
        """Return the execution counter without providing a reset operation.

        Returns:
            Authorized handler attempts charged to this session.
        """
        return self._used_executions

    def execute(self, proposal: JSONValue) -> ToolResult:
        """Validate and independently authorize plain JSON before local execution.

        Preflight uses Story 2 inspection: 16 KiB UTF-8, four container levels,
        16 JSON nodes. Tool contracts then enforce exact arguments. Policy and
        execution state never come from proposal fields or detection results.

        Args:
            proposal: Untrusted plain JSON object with tool and arguments fields.

        Returns:
            Bounded numerical result from an authorized application-owned operation.

        Raises:
            SafetyInputError: For malformed JSON values/envelope or invalid arguments.
            ToolAuthorizationError: For unknown tools or tools absent from policy.
            ToolBudgetError: When the trusted execution allowance is exhausted.
                Unexpected validator/handler defects propagate unchanged.
        """
        try:
            inspect_json(
                proposal,
                ValidationLimits(max_text_bytes=16_384, max_depth=4, max_nodes=16),
            )
        except (JSONParsingError, ValidationLimitError):
            raise SafetyInputError(
                "Supply a small, finite, plain JSON action object."
            ) from None
        try:
            action = ActionProposal.model_validate(proposal)
        except ValidationError:
            raise SafetyInputError(
                "Supply only tool and arguments with strict field types."
            ) from None
        if (
            action.tool not in _REGISTRY
            or action.tool not in self._policy.allowed_tools
        ):
            raise ToolAuthorizationError(
                "Tool is not registered and authorized by application policy."
            )
        try:
            arguments = _REGISTRY[action.tool].model_validate(action.arguments)
        except ValidationError:
            raise SafetyInputError(
                "Correct the selected tool's argument names, types, or bounds."
            ) from None
        if isinstance(arguments, TextStatisticsArguments) and (
            len(arguments.text) > self._policy.max_text_characters
        ):
            raise SafetyInputError(
                "Text argument exceeds the application character budget."
            )
        if self._used_executions >= self._policy.max_executions:
            raise ToolBudgetError(
                "Local execution budget exhausted; stop this session."
            )
        self._used_executions += 1
        return ToolResult(tool=action.tool, values=_execute_local(arguments))
