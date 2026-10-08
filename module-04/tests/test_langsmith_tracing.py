"""Story 8 genuine SDK, security, failure, and executable lab contracts."""

import asyncio
import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest
import requests
from advanced_rag_evaluation.corpus import build_corpus
from advanced_rag_evaluation.evaluation.ragas_adapter import (
    EvaluationCase,
    RagasEvaluator,
    build_replay_judge,
)
from advanced_rag_evaluation.observability.langsmith_adapter import (
    LangSmithTracer,
    OfflineTransport,
    TraceInputError,
)
from advanced_rag_evaluation.semantic_retrieval import HashEmbedder
from advanced_rag_evaluation.telemetry.latency import LatencyReport, StageTiming


@pytest.fixture
def isolated(monkeypatch):
    """Reject all outbound sockets and supply hostile ambient SDK settings."""

    original_connect = socket.socket.connect
    original_pair = socket.socketpair
    building_pair = False

    def pair(*args, **kwargs):
        nonlocal building_pair
        building_pair = True
        try:
            return original_pair(*args, **kwargs)
        finally:
            building_pair = False

    def deny(*args, **kwargs):
        if building_pair and args[1][0] == "127.0.0.1":
            return original_connect(*args, **kwargs)
        raise AssertionError("Unexpected outbound socket")

    monkeypatch.setattr(socket, "socketpair", pair)
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    for name, value in {
        "LANGSMITH_ENDPOINT": "https://attacker.invalid",
        "LANGCHAIN_ENDPOINT": "https://attacker.invalid",
        "LANGSMITH_API_KEY": "SECRET-AMBIENT",
        "LANGSMITH_TRACING": "true",
        "LANGSMITH_TRACING_SAMPLING_RATE": "0",
    }.items():
        monkeypatch.setenv(name, value)


def report():
    return LatencyReport(
        (
            StageTiming("SECRET-stage", 0, 0.1),
            StageTiming("https://attacker.invalid", 1, 0.2),
        )
    )


def test_genuine_sdk_structure_and_isolation(isolated, monkeypatch):
    from langsmith import Client

    calls = []
    original = Client.create_run

    def spy(self, *args, **kwargs):
        calls.append(args)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Client, "create_run", spy)
    transport = OfflineTransport()
    latency = report()
    result = LangSmithTracer(transport).trace(
        latency,
        metadata={"api_key": "SECRET", "endpoint": "https://evil"},
        tags=("exec('evil')",),
    )
    assert result.success and len(calls) == 3
    assert result.latency is latency
    assert result.evidence_kind == "deterministic_offline"
    assert result.remote_delivery_verified is False
    assert len(transport.records) == 6
    root = transport.records[0][2]
    assert root["id"] == str(result.run_id)
    for index, child in enumerate(result.child_ids):
        posted = transport.records[1 + index * 2][2]
        assert posted["id"] == str(child)
        assert posted["parent_run_id"] == str(result.run_id)
        assert posted["inputs"] == {"sequence": index}
    serialized = json.dumps(transport.records)
    for excluded in ("SECRET", "attacker", "evil", "api_key", "exec("):
        assert excluded not in serialized
    assert transport.records[-1][2]["outputs"]["total_seconds"] == pytest.approx(0.3)


@pytest.mark.parametrize(
    "failure",
    [
        requests.Timeout("SECRET"),
        requests.ConnectionError("SECRET"),
        RuntimeError("SECRET"),
    ],
)
def test_nonfatal_failure(isolated, caplog, failure):
    transport = OfflineTransport(failure)
    latency = report()
    result = LangSmithTracer(transport).trace(latency)
    assert not result.success
    assert result.latency is latency
    assert result.failure.__cause__ is not None
    assert "SECRET" not in caplog.text
    assert "SECRET" not in repr(result)
    assert not result.remote_delivery_verified


@pytest.mark.parametrize(
    "metadata",
    [[], 1, {1: "x"}, {"x": []}, {"x": "a" * 1025}, {str(i): "x" for i in range(33)}],
)
def test_malformed_metadata(isolated, metadata):
    transport = OfflineTransport()
    with pytest.raises(TraceInputError):
        LangSmithTracer(transport).trace(report(), metadata=metadata)
    assert not transport.records


@pytest.mark.parametrize("tags", [[], "x", (1,), ("x" * 257,), ("x",) * 33])
def test_malformed_tags(isolated, tags):
    transport = OfflineTransport()
    with pytest.raises(TraceInputError):
        LangSmithTracer(transport).trace(report(), tags=tags)
    assert not transport.records


@pytest.mark.parametrize(
    "latency,evaluation", [(None, None), ([], None), (report(), {}), (report(), "x")]
)
def test_invalid_evidence(isolated, latency, evaluation):
    with pytest.raises(TraceInputError):
        LangSmithTracer(OfflineTransport()).trace(latency, evaluation)


def test_evaluation_provenance_and_exclusion(isolated):
    text = "Apples grow in orchards."
    chunk = build_corpus("SECRET-source", (text,))[0]
    case = EvaluationCase("SECRET-case", "Where do apples grow?", text, text, (chunk,))
    judge = build_replay_judge(
        case,
        statements=(text,),
        statement_verdicts=(1,),
        context_verdicts=(1,),
        generated_question=case.question,
    )
    evaluation = asyncio.run(RagasEvaluator(judge, HashEmbedder()).evaluate(case))
    transport = OfflineTransport()
    evidence = LangSmithTracer(transport).trace(report(), evaluation)
    assert evidence.success and evidence.evaluation is evaluation
    assert evidence.evaluation.case.contexts[0] is chunk
    output = transport.records[-1][2]["outputs"]
    assert output["faithfulness"] == evaluation.scores.faithfulness
    assert output["evaluation_evidence_kind"] == evaluation.evidence_kind
    assert text not in json.dumps(transport.records)
    assert "SECRET" not in json.dumps(transport.records)


def test_demo_subprocess():
    path = Path(__file__).resolve().parents[1] / "examples/langsmith_tracing_demo.py"
    script = (
        "import socket,runpy; "
        "socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw("
        "AssertionError('network')); "
        f"runpy.run_path({str(path)!r},run_name='__main__')"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert "success=True requests=6 children=2" in result.stdout
    assert "deterministic_offline" in result.stdout
    assert "Remote delivery verified: False" in result.stdout


def test_import_has_no_sdk_initialization():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; "
            "import advanced_rag_evaluation.observability.langsmith_adapter; "
            "assert 'langsmith' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert result.returncode == 0


def test_transport_rejects_other_destination():
    request = requests.Request("POST", "https://evil.invalid/runs", json={}).prepare()
    with pytest.raises(RuntimeError):
        OfflineTransport().send(request)


def test_rejects_arbitrary_transport():
    with pytest.raises(TraceInputError):
        LangSmithTracer(object())
