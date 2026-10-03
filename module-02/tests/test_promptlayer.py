"""Actual observability orchestration exercised only with httpx.MockTransport."""

import json
import socket
import traceback
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from prompt_engineering_systems.errors import ToolAuthorizationError
from prompt_engineering_systems.evaluation import (
    CaseSuite,
    EvaluationCase,
    EvaluationReport,
    FixtureResponse,
    StructuredFixtureExecutor,
    export_evidence,
    run_evaluation,
)
from prompt_engineering_systems.integrations.promptlayer import (
    LOG_PATH,
    SCORE_PATH,
    LogWindow,
    PromptLayerAdapter,
    PromptLayerConfiguration,
    PromptLayerError,
    Score,
    observe_evaluation,
)
from prompt_engineering_systems.prompts.construction import ApplicationInstructions
from prompt_engineering_systems.safety.policy import SafetyPolicy
from prompt_engineering_systems.safety.tools import ToolSession

CANARY = "synthetic-private-canary"
KEY = "synthetic-key-only"


def report(mode: str = "offline") -> EvaluationReport:
    """Produce real Story 7 evidence; raw request/context/response contain canaries."""
    case = EvaluationCase(
        case_id="case-a",
        version=1,
        request=CANARY,
        context=CANARY,
        expected_answer=CANARY,
    )
    app = ApplicationInstructions(
        policy="Keep policy.", task="Answer.", output_contract="Return JSON."
    )
    executor = StructuredFixtureExecutor(
        app,
        (FixtureResponse(case_id="case-a", text=json.dumps({"answer": CANARY})),),
        mode=mode,
    )
    return run_evaluation(CaseSuite(cases=(case,)), executor)


def window() -> LogWindow:
    """Return explicit deterministic synthetic UTC artifact timestamps."""
    start = datetime(2026, 10, 2, tzinfo=UTC)
    return LogWindow(start=start, end=start + timedelta(seconds=1))


def adapter(
    handler: Callable[[httpx.Request], httpx.Response], **bounds: object
) -> PromptLayerAdapter:
    """Create a mocked, explicitly credentialed test session."""
    return PromptLayerAdapter(
        PromptLayerConfiguration(mode="mocked", **bounds),
        api_key=KEY,
        transport=httpx.MockTransport(handler),
    )


def successful(request: httpx.Request) -> httpx.Response:
    """Return documented shapes without external contact."""
    if request.url.path == LOG_PATH:
        return httpx.Response(
            201, json={"id": 123, "prompt_version": None, "status": "SUCCESS"}
        )
    return httpx.Response(200, json={"success": True, "message": CANARY})


@pytest.mark.parametrize(
    "updates",
    [
        {"base_url": "http://api.promptlayer.com"},
        {"base_url": "https://example.invalid"},
        {"base_url": "https://key@api.promptlayer.com"},
        {"timeout_seconds": 0.0},
        {"timeout_seconds": float("nan")},
        {"max_requests": 6},
        {"max_response_bytes": 65537},
    ],
)
def test_invalid_configuration_revalidated_safely(updates: dict[str, object]) -> None:
    """Forged configuration cannot select arbitrary URLs or bypass hard bounds."""
    invalid = PromptLayerConfiguration().model_copy(update=updates)
    with pytest.raises(PromptLayerError, match="Correct bounded"):
        PromptLayerAdapter(invalid)


def test_explicit_credentials_no_ambient_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Offline needs no key; environment cannot supply missing mocked credentials."""
    monkeypatch.setenv("PROMPTLAYER_API_KEY", CANARY)
    with PromptLayerAdapter() as offline:
        outcome = observe_evaluation(report(), offline, window())
        assert outcome.logging.state == "skipped" and outcome.scores == ()
        assert offline.used_requests == 0
    for key in (None, "", "bad\nheader", "x" * 257):
        with pytest.raises(PromptLayerError):
            PromptLayerAdapter(
                PromptLayerConfiguration(mode="mocked"),
                api_key=key,
                transport=httpx.MockTransport(successful),
            )
    with pytest.raises(PromptLayerError):
        PromptLayerAdapter(PromptLayerConfiguration(mode="mocked"), api_key=KEY)
    with pytest.raises(PromptLayerError):
        PromptLayerAdapter(
            PromptLayerConfiguration(mode="live"),
            api_key=KEY,
            transport=httpx.MockTransport(successful),
        )


@pytest.mark.parametrize("mode", ["offline", "mocked"])
def test_logging_shape_sanitization_provenance_and_scores(mode: str) -> None:
    """Validated evidence stays content-free while contact provenance remains mocked."""
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return successful(request)

    evidence = report(mode)
    before = export_evidence(evidence)
    with adapter(handler) as client:
        outcome = observe_evaluation(evidence, client, window())
        assert client.used_requests == 4
    assert export_evidence(evidence) == before
    assert outcome.logging.remote_id == "123" and outcome.logging.mode == "mocked"
    payload = json.loads(requests[0].content)
    assert requests[0].url == "https://api.promptlayer.com/log-request"
    assert requests[0].headers["X-API-KEY"] == KEY
    assert requests[0].extensions["timeout"] == dict.fromkeys(
        ("connect", "read", "write", "pool"), 10.0
    )
    assert set(payload) == {
        "provider",
        "model",
        "input",
        "output",
        "request_start_time",
        "request_end_time",
        "status",
        "tags",
        "metadata",
    }
    assert payload["input"]["messages"][0]["content"][0]["type"] == "text"
    logged_evidence = json.loads(payload["output"]["messages"][0]["content"][0]["text"])
    assert logged_evidence == json.loads(before)
    assert payload["metadata"]["evidence_modes"] == mode
    assert payload["metadata"]["correlation_id"] == outcome.correlation_id
    assert (
        CANARY not in requests[0].content.decode()
        and KEY not in requests[0].content.decode()
    )
    assert (
        CANARY not in outcome.model_dump_json() and KEY not in outcome.model_dump_json()
    )
    assert all(request.url.path == SCORE_PATH for request in requests[1:])
    assert [json.loads(request.content) for request in requests[1:]] == [
        {"request_id": 123, "score": 100, "name": name}
        for name in ("completion", "structured_validity", "correctness")
    ]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"id": True, "status": "SUCCESS"},
        {"id": "123", "status": "SUCCESS"},
        {"id": 0, "status": "SUCCESS"},
        {"id": 10**18, "status": "SUCCESS"},
        {"id": 1, "status": "OTHER"},
        {"id": 1},
        [],
    ],
)
def test_invalid_logging_receipts_prevent_score_submission(body: object) -> None:
    """Untrusted identifiers/statuses cannot establish a logging receipt."""
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(201, json=body)

    with adapter(handler) as client:
        outcome = observe_evaluation(report(), client, window())
    assert outcome.logging.state == "failed" and outcome.logging.failure == "response"
    assert outcome.scores == () and len(requests) == 1


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "authentication"),
        (403, "permission"),
        (429, "rate_limit"),
        (503, "http"),
        (302, "http"),
    ],
)
def test_http_failures_preserve_successful_evaluation(status: int, code: str) -> None:
    """Remote bodies/redirects never leak or retroactively alter evaluation."""
    evidence = report()
    before = export_evidence(evidence)
    with adapter(
        lambda request: httpx.Response(
            status, text=CANARY, headers={"Location": "https://example.invalid"}
        )
    ) as client:
        outcome = observe_evaluation(evidence, client, window())
        assert client.used_requests == 1
    assert outcome.logging.failure == code and outcome.scores == ()
    assert evidence.metrics.correct == 1 and export_evidence(evidence) == before
    assert CANARY not in outcome.model_dump_json()


@pytest.mark.parametrize(
    "failure,code", [(httpx.ReadTimeout, "timeout"), (httpx.ConnectError, "connection")]
)
def test_expected_transport_failures_are_content_safe(
    failure: type[Exception], code: str
) -> None:
    """Transport errors containing request/private text have suppressed chains."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise failure(CANARY, request=request)

    with adapter(handler) as client:
        with pytest.raises(PromptLayerError) as caught:
            client.log(report(), window())
    assert caught.value.code == code
    rendered = "".join(traceback.format_exception(caught.value))
    assert CANARY not in rendered and KEY not in rendered


@pytest.mark.parametrize(
    "body", [b"not JSON", b"\xff", b'{"id":1,"id":2}', b"x" * 16385]
)
def test_malformed_and_oversized_response_rejected(body: bytes) -> None:
    """Strict parsing and streaming caps reject malformed/duplicate/excess content."""
    with adapter(lambda request: httpx.Response(201, content=body)) as client:
        outcome = observe_evaluation(report(), client, window())
    assert outcome.logging.failure == "response"


def test_stream_ceiling_and_compressed_response_rejection() -> None:
    """Streaming stops at the bound and compressed responses cannot expand first."""
    consumed = []

    class Stream(httpx.SyncByteStream):
        """Yield bounded chunks to exercise the actual streaming ceiling."""

        def __iter__(self) -> Iterator[bytes]:
            for index in range(20):
                consumed.append(index)
                yield b"x" * 4096

    with adapter(lambda request: httpx.Response(201, stream=Stream())) as client:
        assert (
            observe_evaluation(report(), client, window()).logging.failure == "response"
        )
    assert len(consumed) == 5
    with adapter(
        lambda request: httpx.Response(
            201, headers={"Content-Encoding": "gzip"}, stream=Stream()
        )
    ) as client:
        assert (
            observe_evaluation(report(), client, window()).logging.failure == "response"
        )
    assert len(consumed) == 5


def test_unexpected_programming_defect_propagates() -> None:
    """Programming errors cannot masquerade as PromptLayer availability failures."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise RuntimeError("defect")

    with adapter(handler) as client, pytest.raises(RuntimeError, match="defect"):
        observe_evaluation(report(), client, window())


def test_invalid_score_and_identifier_before_contact() -> None:
    """Names, integer ranges and decimal identifier bounds are enforced locally."""
    with adapter(successful) as client:
        for identity in ("0", "01", "123/path", "x" * 19, True):
            with pytest.raises(PromptLayerError):
                client.submit_score(identity, Score(name="correctness", value=100))
        for updates in (
            {"value": -1},
            {"value": 101},
            {"value": 0.5},
            {"value": float("nan")},
            {"name": CANARY},
        ):
            invalid = Score(name="correctness", value=100).model_copy(update=updates)
            with pytest.raises(PromptLayerError):
                client.submit_score("123", invalid)
        assert client.used_requests == 0


def test_score_failure_preserves_logging_and_other_score_results() -> None:
    """Log success survives one score failure; evaluation remains authoritative."""

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.url.path == SCORE_PATH
            and json.loads(request.content)["name"] == "correctness"
        ):
            return httpx.Response(200, json={"success": False, "message": CANARY})
        return successful(request)

    evidence = report()
    with adapter(handler) as client:
        outcome = observe_evaluation(evidence, client, window())
    assert outcome.logging.state == "succeeded"
    assert [item.outcome.state for item in outcome.scores] == [
        "succeeded",
        "succeeded",
        "failed",
    ]
    assert (
        outcome.scores[-1].outcome.failure == "response"
        and evidence.metrics.correct == 1
    )
    assert CANARY not in outcome.model_dump_json()


def test_attempt_payload_budgets_and_deterministic_correlation() -> None:
    """Calls are charged cumulatively; correlation follows evidence, not remote IDs."""
    evidence = report()
    with adapter(successful, max_requests=1) as client:
        outcome = observe_evaluation(evidence, client, window())
        assert outcome.logging.state == "succeeded" and client.used_requests == 1
        assert all(item.outcome.failure == "budget" for item in outcome.scores)
        repeated = observe_evaluation(evidence, client, window())
        assert (
            repeated.correlation_id == outcome.correlation_id
            and repeated.logging.failure == "budget"
        )
    with adapter(successful, max_payload_bytes=1) as client:
        assert (
            observe_evaluation(evidence, client, window()).logging.failure == "budget"
        )
        assert client.used_requests == 0


def test_remote_extras_do_not_change_policy_or_tool_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Discard remote extras with network and authority tripwires intact."""

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Unexpected live network.")

    monkeypatch.setattr(socket, "socket", forbidden)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == LOG_PATH:
            return httpx.Response(
                201,
                json={
                    "id": 123,
                    "status": "SUCCESS",
                    "policy": CANARY,
                    "allowed_tools": ["shell"],
                    "authorized": True,
                },
            )
        return successful(request)

    tools = ToolSession(SafetyPolicy())
    with adapter(handler) as client:
        result = observe_evaluation(report(), client, window())
    assert result.logging.state == "succeeded" and tools.policy.allowed_tools == ()
    assert tools.used_executions == 0 and CANARY not in result.model_dump_json()
    with pytest.raises(ToolAuthorizationError):
        tools.execute({"tool": "add", "arguments": {"left": 1, "right": 2}})


def test_timing_integrity_and_invalid_evidence_before_transport() -> None:
    """Forged evidence and ambiguous artifact windows cannot be transmitted."""
    with adapter(successful) as client:
        for updates in (
            {"end": window().start - timedelta(seconds=1)},
            {"start": datetime(2026, 10, 2)},
            {"end": window().start + timedelta(hours=2)},
        ):
            invalid = window().model_copy(update=updates)
            assert (
                observe_evaluation(report(), client, invalid).logging.failure
                == "configuration"
            )
        evidence = report()
        corrupt = evidence.model_copy(
            update={"metrics": evidence.metrics.model_copy(update={"correct": 0})}
        )
        with pytest.raises(PromptLayerError):
            observe_evaluation(corrupt, client, window())
        assert client.used_requests == 0


def test_failed_evaluation_logs_warning_without_changing_failures() -> None:
    """Artifact warning is distinct from logging failure; scores retain zero rates."""
    item = EvaluationCase(
        case_id="invalid", version=1, request=CANARY, expected_answer="alpha"
    )
    app = ApplicationInstructions(
        policy="Keep policy.", task="Answer.", output_contract="Return JSON."
    )
    evidence = run_evaluation(
        CaseSuite(cases=(item,)),
        StructuredFixtureExecutor(
            app, (FixtureResponse(case_id="invalid", text="not JSON"),)
        ),
    )
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        sent.append(payload)
        if request.url.path == LOG_PATH:
            assert payload["status"] == "WARNING"
            return httpx.Response(201, json={"id": 123, "status": "WARNING"})
        return successful(request)

    with adapter(handler) as client:
        outcome = observe_evaluation(evidence, client, window())
    assert evidence.metrics.failed == 1 and outcome.logging.state == "succeeded"
    assert all(item.score.value == 0 for item in outcome.scores)
    assert CANARY not in json.dumps(sent)


def test_empty_metrics_skip_scores_and_percentage_rounding_is_explicit() -> None:
    """Empty rates create no scores; fractional rates map to bounded REST integers."""
    app = ApplicationInstructions(
        policy="Keep policy.", task="Answer.", output_contract="Return JSON."
    )
    empty = run_evaluation(CaseSuite(cases=()), StructuredFixtureExecutor(app, ()))
    with adapter(successful) as client:
        outcome = observe_evaluation(empty, client, window())
        assert outcome.scores == () and client.used_requests == 1
    cases = tuple(
        EvaluationCase(
            case_id=f"case-{index}",
            version=1,
            request="Synthetic",
            expected_answer="alpha",
        )
        for index in range(3)
    )
    responses = tuple(
        FixtureResponse(
            case_id=item.case_id,
            text=json.dumps({"answer": "other" if index == 2 else "alpha"}),
        )
        for index, item in enumerate(cases)
    )
    evidence = run_evaluation(
        CaseSuite(cases=cases), StructuredFixtureExecutor(app, responses)
    )
    with adapter(successful) as client:
        outcome = observe_evaluation(evidence, client, window())
    assert (
        next(
            item.score.value
            for item in outcome.scores
            if item.score.name == "correctness"
        )
        == 67
    )


def test_score_http_failure_is_separate_and_offline_failure_is_explicit() -> None:
    """A score HTTP failure preserves logging; invalid offline windows make no call."""

    def handler(request: httpx.Request) -> httpx.Response:
        return (
            successful(request)
            if request.url.path == LOG_PATH
            else httpx.Response(403, text=CANARY)
        )

    with adapter(handler) as client:
        outcome = observe_evaluation(report(), client, window())
    assert outcome.logging.state == "succeeded"
    assert all(item.outcome.failure == "permission" for item in outcome.scores)
    with PromptLayerAdapter() as offline:
        invalid = window().model_copy(
            update={"end": window().start - timedelta(seconds=1)}
        )
        outcome = observe_evaluation(report(), offline, invalid)
        assert outcome.logging.failure == "configuration" and offline.used_requests == 0
