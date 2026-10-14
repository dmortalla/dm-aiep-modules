"""Private bounded JSON transport for an application-injected gateway factory."""

import asyncio
import contextlib
import importlib.util
import json
import os
import sys

from .live_errors import LiveExecutionError, LiveFailureCategory
from .live_validation import validate_live_data
from .model_gateway import ModelRequest, checked_reply

MAX_REQUEST_PACKET = 60_000
MAX_REPLY_PACKET = 110_000


def main() -> None:
    """Load trusted application code; never select a provider from model data.

    Factory location arguments come only from the parent's injected callable.
    This worker contains no provider, credential lookup, retry or fallback.
    Exceptions and unsolicited stdout are discarded, never sent to the parent.
    """
    transport = sys.stdout

    def emit(packet: dict) -> None:
        encoded = json.dumps(packet, ensure_ascii=True, separators=(",", ":"))
        if len(encoded) > MAX_REPLY_PACKET:
            encoded = json.dumps({"error": "output_too_large"})
        transport.write(encoded + "\n")
        transport.flush()

    async def serve() -> None:
        module_name, factory_name, source = sys.argv[1:]
        # Load the exact source selected by the trusted injected callable once.
        # No import fallback can substitute a different application factory.
        spec = importlib.util.spec_from_file_location(module_name, source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        factory = module
        for name in factory_name.split("."):
            factory = getattr(factory, name)
        gateway = factory()
        emit({"ready": True})
        while True:
            line = sys.stdin.buffer.readline(MAX_REQUEST_PACKET + 1)
            if not line:
                return
            if len(line) > MAX_REQUEST_PACKET or not line.endswith(b"\n"):
                emit({"error": "unexpected_provider_failure"})
                return
            try:
                request = validate_live_data(ModelRequest, json.loads(line))
                raw = await gateway.complete(request)
                reply = checked_reply(request, raw)
                emit({"reply": reply.model_dump(mode="json")})
            except LiveExecutionError as error:
                # Reconstruct a closed enum; even a constructed exception is data.
                category = LiveFailureCategory(error.category)
                emit({"error": category.value})
            except Exception:
                emit({"error": "unexpected_provider_failure"})

    with open(os.devnull, "w", encoding="utf-8") as sink:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            try:
                asyncio.run(serve())
            except Exception:
                emit({"error": "unexpected_provider_failure"})


if __name__ == "__main__":
    main()
