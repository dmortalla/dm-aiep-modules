"""Explicit selection, real SDK construction, no fallback, and packaging checks."""

import ast
import importlib
import sys
from pathlib import Path

import pytest
from multi_agent_orchestration import adapters
from multi_agent_orchestration.contracts import RuntimeId, TaskInput, WorkflowRequest
from multi_agent_orchestration.errors import (
    ExecutionFailureError,
    InvalidWorkflowRequestError,
    RuntimeUnavailableError,
    UnknownRuntimeError,
)
from multi_agent_orchestration.execution import execute_workflow
from multi_agent_orchestration.fixture import FixtureRuntime
from multi_agent_orchestration.registry import create_runtime
from multi_agent_orchestration.runtime import Runtime


@pytest.mark.parametrize("identifier", ["unknown", "", None, 5, [], "private-secret"])
def test_unknown_runtime_fails_closed(identifier):
    with pytest.raises(UnknownRuntimeError) as error:
        create_runtime(identifier)
    assert error.value.__cause__ is not None
    assert "private-secret" not in str(error.value)


async def test_default_runtime_never_imports_frameworks(monkeypatch):
    original = __import__

    def guarded(name, *args, **kwargs):
        assert not name.startswith(("crewai", "langgraph", "google.adk", "openai"))
        return original(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", guarded)
    runtime = create_runtime()
    assert isinstance(runtime, FixtureRuntime)
    assert isinstance(runtime, Runtime)
    result = await execute_workflow(WorkflowRequest(task=TaskInput(instruction="test")))
    assert result.evidence.model_calls == result.evidence.external_calls == 0


def test_explicit_fixture_string_selection():
    assert create_runtime("fixture").info.runtime == RuntimeId.FIXTURE


def test_missing_distribution_metadata_fails_closed(monkeypatch):
    from importlib.metadata import PackageNotFoundError

    cause = PackageNotFoundError("langgraph")

    def missing_version(name):
        raise cause

    monkeypatch.setattr(adapters, "version", missing_version)
    with pytest.raises(RuntimeUnavailableError) as error:
        create_runtime(RuntimeId.LANGGRAPH)
    assert error.value.__cause__ is cause


@pytest.mark.parametrize(
    "credential",
    ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "LANGSMITH_API_KEY"],
)
async def test_keys_do_not_change_runtime_or_authorize_calls(monkeypatch, credential):
    monkeypatch.setenv(credential, "dummy-not-a-real-credential")
    result = await execute_workflow(WorkflowRequest(task=TaskInput(instruction="test")))
    assert isinstance(create_runtime(), FixtureRuntime)
    assert result.evidence.actual_runtime == RuntimeId.FIXTURE
    assert result.evidence.model_calls == result.evidence.external_calls == 0
    assert "dummy-not-a-real-credential" not in result.model_dump_json()


@pytest.mark.parametrize(
    "identifier,module,symbol",
    [
        (RuntimeId.LANGGRAPH, "langgraph.graph", "StateGraph"),
        (RuntimeId.CREWAI, "crewai", "Task"),
        (RuntimeId.GOOGLE_ADK, "google.adk.agents", "BaseAgent"),
    ],
)
async def test_real_framework_construction_but_no_execution(identifier, module, symbol):
    runtime = create_runtime(identifier)
    assert isinstance(runtime, Runtime)
    assert isinstance(runtime._native, getattr(importlib.import_module(module), symbol))
    assert runtime.info.runtime == identifier
    assert runtime.info.framework_version
    assert runtime.info.evidence_class == "adapter_construction"
    assert runtime.info.execution_available is False
    req = WorkflowRequest(runtime=identifier, task=TaskInput(instruction="test"))
    with pytest.raises(RuntimeUnavailableError, match="not implemented"):
        await runtime.execute(req)
    with pytest.raises(RuntimeUnavailableError, match="not implemented"):
        await execute_workflow(req, runtime=runtime)
    assert set(runtime.info.model_dump()) == {
        "runtime",
        "execution_available",
        "evidence_class",
        "framework_version",
    }


@pytest.mark.parametrize(
    "identifier", [RuntimeId.LANGGRAPH, RuntimeId.CREWAI, RuntimeId.GOOGLE_ADK]
)
def test_missing_framework_never_falls_back(monkeypatch, identifier):
    cause = ModuleNotFoundError("dependency unavailable")

    def unavailable(*args):
        raise cause

    monkeypatch.setattr(adapters, "import_module", unavailable)
    with pytest.raises(RuntimeUnavailableError, match="uv lock") as error:
        create_runtime(identifier)
    assert error.value.__cause__ is cause


def test_missing_sdk_symbol_fails_closed(monkeypatch):
    monkeypatch.setattr(adapters, "import_module", lambda name: object())
    with pytest.raises(RuntimeUnavailableError) as error:
        create_runtime(RuntimeId.LANGGRAPH)
    assert isinstance(error.value.__cause__, AttributeError)


def test_constructor_failure_retains_cause_not_secret(monkeypatch):
    cause = ValueError("private-secret")

    def fail(**kwargs):
        raise cause

    class FakeModule:
        StateGraph = staticmethod(fail)

    monkeypatch.setattr(adapters, "import_module", lambda name: FakeModule)
    with pytest.raises(ExecutionFailureError) as error:
        create_runtime(RuntimeId.LANGGRAPH)
    assert error.value.__cause__ is cause
    assert "private-secret" not in str(error.value)


async def test_injected_runtime_must_match_explicit_request():
    req = WorkflowRequest(runtime=RuntimeId.CREWAI, task=TaskInput(instruction="test"))
    with pytest.raises(InvalidWorkflowRequestError):
        await execute_workflow(req, runtime=FixtureRuntime())


def test_standalone_source_and_domain_boundaries():
    root = Path(__file__).parents[1] / "src" / "multi_agent_orchestration"
    other_modules = {
        "ai_engineering_foundations",
        "prompt_engineering_systems",
        "rag_engineering_foundations",
        "advanced_rag_evaluation",
        "ai_agent_engineering",
    }
    forbidden = other_modules | {
        "streamlit",
        "prometheus_client",
        "langsmith",
        "openai",
    }
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    alias.name.split(".")[0] not in forbidden for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in forbidden
    assert "multi_agent_orchestration" in sys.modules
