from unittest.mock import patch

from backend.app.llm import OllamaLLM, parse_llm_output


def test_parse_valid_json():
    raw = '[{"file_path": "a.py", "line": 5, "category": "bug", "explanation": "off-by-one here", "confidence": 0.8}]'
    findings = parse_llm_output(raw, "a.py")
    assert len(findings) == 1
    assert findings[0].confidence == 0.8


def test_parse_handles_markdown_fence():
    raw = '```json\n[{"file_path": "a.py", "line": 5, "category": "bug", "explanation": "issue here", "confidence": 0.6}]\n```'  # noqa: E501
    findings = parse_llm_output(raw, "a.py")
    assert len(findings) == 1


def test_parse_garbage_returns_empty_not_crash():
    assert parse_llm_output("not json at all", "a.py") == []


def test_parse_empty_list_is_valid_abstention():
    assert parse_llm_output("[]", "a.py") == []


@patch("backend.app.llm.httpx.Client.post")
def test_ollama_llm_analyze_calls_correct_endpoint(mock_post):
    mock_post.return_value.json.return_value = {"response": "[]"}
    mock_post.return_value.raise_for_status = lambda: None

    llm = OllamaLLM(base_url="http://fake", model="test-model")
    result = llm.analyze("some prompt")

    assert result == "[]"
    called_url = mock_post.call_args[0][0]
    assert called_url == "http://fake/api/generate"
