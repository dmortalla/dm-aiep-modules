"""Local evaluation entry points; no UI, live clients or external writes."""

from .cases import CaseSuite, EvaluationCase, load_cases
from .evidence import EvaluationReport, export_evidence
from .runner import FixtureResponse, StructuredFixtureExecutor, run_evaluation

__all__ = [
    "CaseSuite",
    "EvaluationCase",
    "EvaluationReport",
    "FixtureResponse",
    "StructuredFixtureExecutor",
    "export_evidence",
    "load_cases",
    "run_evaluation",
]
