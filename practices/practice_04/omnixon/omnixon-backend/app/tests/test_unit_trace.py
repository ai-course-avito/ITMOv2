"""unit trace tests"""

from shared import NOW


def test_the_tracer_keeps_a_failed_tool_and_clips_long_results():
    from datetime import timedelta
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        RetryPromptPart,
        ToolCallPart,
        ToolReturnPart,
    )
    from ai.trace import MAX_CHARS, Tracer, clip

    t0 = NOW
    messages = [
        ModelResponse(
            parts=[
                ToolCallPart("a", {"x": 1}, tool_call_id="1"),
                ToolCallPart("b", "{}", tool_call_id="2"),
                ToolCallPart("c", {}, tool_call_id="3"),
            ],
            model_name="m",
            timestamp=t0,
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    "a",
                    "y" * (MAX_CHARS * 2),
                    tool_call_id="1",
                    timestamp=t0 + timedelta(seconds=2),
                ),
                RetryPromptPart(
                    "bad arguments",
                    tool_name="b",
                    tool_call_id="2",
                    timestamp=t0 + timedelta(seconds=1),
                ),
            ]
        ),
    ]
    tracer = Tracer()
    steps = tracer.feed(messages) + tracer.finish()

    by_name = {s.name: s for s in steps if s.kind == "tool"}
    assert (
        by_name["a"].duration_ms == 2000 and len(by_name["a"].result) < MAX_CHARS + 50
    )
    assert by_name["a"].result.endswith("more characters)")
    assert by_name["b"].error == "bad arguments" and by_name["b"].result is None
    assert by_name["c"].error == "no result"  # never answered
    assert clip({"k": [1, 2]}) == {"k": [1, 2]} and clip(object).startswith("<class")
