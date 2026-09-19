from unittest.mock import patch

from backend.app.graph import compiled_graph
from backend.app.schemas import ReviewState

FAKE_LLM_RESPONSE = '[{"file_path": "app.py", "line": 1, "category": "style", "explanation": "stub finding for graph wiring test", "confidence": 0.5}]'  # noqa: E501


@patch("backend.app.graph._llm")
def test_graph_runs_end_to_end(mock_llm):
    mock_llm.analyze.return_value = FAKE_LLM_RESPONSE
    initial = ReviewState(pull_request_id=1, head_sha="abc123")
    result = compiled_graph.invoke(initial)
    assert len(result["validated_findings"]) == 1
    assert result["validated_findings"][0].category == "style"


@patch("backend.app.graph._llm")
def test_graph_is_deterministic(mock_llm):
    mock_llm.analyze.return_value = FAKE_LLM_RESPONSE
    initial = ReviewState(pull_request_id=1, head_sha="abc123")
    result_a = compiled_graph.invoke(initial.model_copy(deep=True))
    result_b = compiled_graph.invoke(initial.model_copy(deep=True))
    assert result_a["validated_findings"] == result_b["validated_findings"]
