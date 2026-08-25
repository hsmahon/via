"""Structured response validation tests (required area 10)."""

from __future__ import annotations

import pytest
from via_harness import ErrorCategory, HarnessError
from via_harness.response import FinalAnswer, ToolRequest, parse_model_output, validate_agent_answer


class TestParseModelOutput:
    """Wire-contract parsing and validation."""

    def test_parses_final_payload(self) -> None:
        """Valid final JSON yields a typed FinalAnswer with citations."""
        raw = (
            '{"type": "final", "answer": "A dog appears.", '
            '"citations": [{"video_id": "v1", "timestamp_start": 1.5, "timestamp_end": 3.0}]}'
        )
        parsed = parse_model_output(raw)
        assert isinstance(parsed, FinalAnswer)
        assert parsed.answer == "A dog appears."
        assert parsed.citations[0].timestamp_start == 1.5

    def test_parses_tool_request_payload(self) -> None:
        """Tool requests validate their arguments object shape."""
        parsed = parse_model_output(
            '{"type": "tool_request", "tool": "get_transcript", "arguments": {}}'
        )
        assert isinstance(parsed, ToolRequest)
        assert parsed.tool == "get_transcript"

    def test_non_json_output_rejected(self) -> None:
        """Non-JSON output raises INVALID_MODEL_RESPONSE."""
        with pytest.raises(HarnessError) as err:
            parse_model_output("I think the video shows a dog")
        assert err.value.category is ErrorCategory.INVALID_MODEL_RESPONSE

    def test_unknown_type_rejected(self) -> None:
        """Payloads with unknown ``type`` values are rejected."""
        with pytest.raises(HarnessError) as err:
            parse_model_output('{"type": "poem", "text": "roses"}')
        assert err.value.category is ErrorCategory.INVALID_MODEL_RESPONSE

    def test_schema_violation_rejected(self) -> None:
        """Final payloads missing required fields are rejected."""
        with pytest.raises(HarnessError) as err:
            parse_model_output('{"type": "final"}')
        assert err.value.category is ErrorCategory.INVALID_MODEL_RESPONSE


class TestValidateAgentAnswer:
    """Run-scoped rules applied after schema validation."""

    def test_foreign_citation_rejected(self) -> None:
        """Citations pointing at another video are rejected outright."""
        answer = parse_model_output(
            '{"type": "final", "answer": "x", "citations": [{"video_id": "other-video"}]}'
        )
        with pytest.raises(HarnessError) as err:
            validate_agent_answer(answer, video_id="authorized-video")  # type: ignore[arg-type]
        assert err.value.category is ErrorCategory.INVALID_MODEL_RESPONSE

    def test_scoped_citations_pass_through(self) -> None:
        """Citations for the authorized video are preserved."""
        answer = parse_model_output(
            '{"type": "final", "answer": "x", "citations": [{"video_id": "authorized-video", "timestamp_start": 0.0, "timestamp_end": 2.0}]}'
        )
        response = validate_agent_answer(answer, video_id="authorized-video")  # type: ignore[arg-type]
        assert len(response.citations) == 1
