"""Canonical content-free evidence export; no automatic file or external writes."""

import hashlib
import json
from typing import Literal, Self

from pydantic import ConfigDict, Field, ValidationError, model_validator

from ..contracts import StrictContract
from ..errors import EvaluationError
from .metrics import CaseResult, Metrics, aggregate


def fingerprint(value: StrictContract) -> str:
    """Hash validated configuration/case data without including raw text in export.

    Args:
        value: Application-owned validated bounded contract.

    Returns:
        SHA-256 identity, not a secrecy guarantee for guessable synthetic inputs.
    """
    canonical = json.dumps(
        value.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class EvaluationReport(StrictContract):
    """Versioned results with recomputed metrics and canonical identity order."""

    model_config = ConfigDict(frozen=True)
    format_version: Literal[1] = 1
    configuration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    results: tuple[CaseResult, ...] = Field(max_length=32)
    metrics: Metrics

    @model_validator(mode="after")
    def integrity(self) -> Self:
        """Reject altered metrics, duplicate results or noncanonical ordering."""
        if self.metrics != aggregate(self.results):
            raise ValueError("Evidence metrics do not match outcomes.")
        if tuple(item.case_id for item in self.results) != tuple(
            sorted(item.case_id for item in self.results)
        ):
            raise ValueError("Evidence case order must be canonical.")
        return self


def export_evidence(report: EvaluationReport) -> str:
    """Return deterministic JSON after revalidation, never exporting raw content.

    Args:
        report: Typed report, including reports constructed/copied without validation.

    Returns:
        Canonical serializable evidence with fixed fields and safe classifications.

    Raises:
        EvaluationError: For corrupt evidence or contradictory metrics/results.
    """
    try:
        checked = EvaluationReport.model_validate(report)
    except (ValidationError, EvaluationError):
        raise EvaluationError(
            "Correct evaluation evidence integrity before export."
        ) from None
    return json.dumps(
        checked.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
