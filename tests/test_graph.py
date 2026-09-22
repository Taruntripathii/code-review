from unittest.mock import MagicMock, patch

from backend.app.graph import compiled_graph
from backend.app.models import Review
from backend.app.schemas import ReviewState

FAKE_LLM_RESPONSE = '[{"file_path": "app.py", "line": 1, "category": "style", "explanation": "stub finding for graph wiring test", "confidence": 0.5}]'  # noqa: E501


def _fake_session_factory():
    """A stand-in for SessionLocal that never touches a real DB.

    persist_review calls db.flush() and then reads review.id, so flush() must
    assign an id to any pending Review the way a real autoincrement PK would.
    """

    session = MagicMock()

    def flush():
        for call in session.add.call_args_list:
            obj = call.args[0]
            if isinstance(obj, Review) and obj.id is None:
                setattr(obj, "id", 1)

    session.flush.side_effect = flush
    return session


@patch("backend.app.graph.SessionLocal", side_effect=_fake_session_factory)
@patch("backend.app.graph._llm")
def test_graph_runs_end_to_end(mock_llm, mock_session):
    mock_llm.analyze.return_value = FAKE_LLM_RESPONSE
    initial = ReviewState(pull_request_id=1, head_sha="abc123")
    result = compiled_graph.invoke(initial)
    assert len(result["validated_findings"]) == 1
    assert result["validated_findings"][0].category == "style"


@patch("backend.app.graph.SessionLocal", side_effect=_fake_session_factory)
@patch("backend.app.graph._llm")
def test_graph_is_deterministic(mock_llm, mock_session):
    mock_llm.analyze.return_value = FAKE_LLM_RESPONSE
    initial = ReviewState(pull_request_id=1, head_sha="abc123")
    result_a = compiled_graph.invoke(initial.model_copy(deep=True))
    result_b = compiled_graph.invoke(initial.model_copy(deep=True))
    assert result_a["validated_findings"] == result_b["validated_findings"]
