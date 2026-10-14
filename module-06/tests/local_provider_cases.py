"""Child-importable test-owned provider; never opens a socket."""

import json
import os
from pathlib import Path

import httpx
from multi_agent_orchestration.local_model_gateway import LocalModelGateway

SCENARIO = "happy"
LOG = ""


def factory():
    calls = 0

    def respond(request):
        nonlocal calls
        calls += 1
        scenario = SCENARIO.removeprefix("cached_")
        payload = json.loads(request.content)
        # Fail rather than consult ambient model configuration/credentials.
        assert set(os.environ) <= {
            "SYSTEMROOT",
            "WINDIR",
            "PYTHON_DOTENV_DISABLED",
            "OTEL_SDK_DISABLED",
            "LANGSMITH_TRACING",
            "LANGCHAIN_TRACING_V2",
            "DO_NOT_TRACK",
            "LC_CTYPE",
        }
        with Path(LOG).open("a", encoding="utf-8") as log:
            log.write(json.dumps({"call": calls, "pid": os.getpid()}) + "\n")
        content = [
            {"findings": ["Synthetic provider finding."]},
            {"assessment": "Synthetic assessment.", "supports": [1]},
            {"advisory_verdict": "sound", "rationale": "Synthetic critique."},
        ]
        index = calls - 1
        if scenario == "repair":
            index -= 1
        text = json.dumps(content[max(0, min(index, 2))])
        if scenario == "bad_always" or (scenario == "repair" and calls == 1):
            text = "{SYNTHETIC_ADAPTER_SECRET_7431"
        if scenario == "connection":
            raise httpx.ConnectError("SYNTHETIC_ADAPTER_SECRET_7431")
        body = json.dumps(
            {
                "model": payload["model"],
                "done": True,
                "message": {"role": "assistant", "content": text},
                "prompt_eval_count": 2,
                "eval_count": 3,
                **(
                    {
                        "prompt_eval_cached_count": (
                            False if scenario == "invalid" else 100
                        )
                    }
                    if SCENARIO.startswith("cached_")
                    else {}
                ),
            }
        ).encode()
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            stream=httpx.ByteStream(body),
        )

    return LocalModelGateway(transport=httpx.MockTransport(respond))
