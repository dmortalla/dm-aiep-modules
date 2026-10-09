"""Domain exceptions for the AI Agent Engineering module."""


class AgentEngineeringError(Exception):
    """Base exception for Module 5 domain failures."""


class InvalidStateTransitionError(AgentEngineeringError):
    """Raised when an agent lifecycle transition is not permitted."""

    def __init__(self, current_status: str, target_status: str) -> None:
        """Initialize an invalid-transition error.

        Args:
            current_status: Current lifecycle status.
            target_status: Requested lifecycle status.
        """
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(
            f"Invalid agent lifecycle transition: "
            f"{current_status} -> {target_status}."
        )
