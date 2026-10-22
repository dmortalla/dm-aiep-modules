"""Demonstration-only synthetic canonical gateway factory.

The operations console runs the accepted canonical live workflow with
deterministic synthetic content instead of a real local provider. The public
supervisor requires the gateway factory to be a module-level importable
callable in a real file; this module provides exactly that factory shape.

The returned gateway keeps the accepted ``LocalModelGateway`` behaviour but
binds an ``httpx.MockTransport``: no socket is opened, no credential is read,
no environment is asserted, and every reply is a fixed synthetic Ollama
envelope with fixed usage counts. The replies are synthetic demonstration
data; the canonical workflow itself classifies their receipts as synthetic
offline, and no presentation may describe them as model output or inference.
"""

import json

import httpx

from .local_model_gateway import LocalModelGateway

# Fixed role-shaped reply bodies validated against the closed role schemas
# (research findings, assessment with support witnesses, advisory verdict).
_REPLY = {
    "RESEARCHER": {"findings": ["Synthetic finding."]},
    "ANALYST": {"assessment": "Synthetic assessment.", "supports": [1]},
    "CRITIC": {
        "advisory_verdict": "needs_revision",
        "rationale": "Advisory content only.",
    },
}


def synthetic_gateway_factory() -> LocalModelGateway:
    """Return the accepted local gateway shape with a synthetic transport.

    Returns:
        Deterministic synthetic local gateway for the canonical workflow.

    Raises:
        LiveExecutionError: Closed gateway failure for any refused request or
            unsupported role; never raw library exceptions.
    """

    def respond(request):
        payload = json.loads(request.content)
        role = payload["messages"][0]["content"].split(". ", 1)[0].removeprefix(
            "ROLE="
        )
        if role not in _REPLY:
            raise ValueError("Unexpected canonical role.")
        text = json.dumps(_REPLY[role])
        envelope = {
            "created_at": "2000-01-01T00:00:00Z",
            "done": True,
            "done_reason": "stop",
            "eval_count": 3,
            "eval_duration": 0,
            "load_duration": 0,
            "message": {"role": "assistant", "content": text},
            "model": payload["model"],
            "prompt_eval_cached_count": 0,
            "prompt_eval_count": 2,
            "prompt_eval_duration": 0,
            "total_duration": 0,
        }
        body = json.dumps(envelope).encode()
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            stream=httpx.ByteStream(body),
        )

    return LocalModelGateway(transport=httpx.MockTransport(respond))
