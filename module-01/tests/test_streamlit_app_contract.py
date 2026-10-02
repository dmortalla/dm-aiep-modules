"""Static regression contracts for the Module 1 Streamlit application."""

import ast
from pathlib import Path

APP_PATH = Path(__file__).parents[1] / "app.py"


def _parse_app() -> ast.Module:
    """Parse the Streamlit application without executing it."""
    return ast.parse(APP_PATH.read_text(encoding="utf-8"))


def test_stream_function_is_not_shadowed_by_assignment() -> None:
    """Protect the streaming callable from the demonstrated bool collision."""
    tree = _parse_app()

    function_names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assigned_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned_names.add(target.id)

        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assigned_names.add(node.target.id)

    assert "stream_response" in function_names
    assert "stream_response" not in assigned_names


def test_stream_toggle_has_distinct_name() -> None:
    """Keep UI stream state separate from the streaming callable."""
    source = APP_PATH.read_text(encoding="utf-8")

    assert "stream_enabled = st.toggle(" in source
    assert "if stream_enabled:" in source
    assert "stream_response = st.toggle(" not in source


def test_streamlit_consumes_native_async_stream_without_buffering() -> None:
    """Keep the verified incremental streaming architecture intact."""
    source = APP_PATH.read_text(encoding="utf-8")

    assert "async def stream_response(" in source
    assert "async for chunk in service.stream(service_name, request):" in source
    assert "yield chunk" in source
    assert "st.write_stream(" in source

    assert "chunks.append(" not in source
    assert "asyncio.new_event_loop()" not in source
    assert "run_until_complete(" not in source