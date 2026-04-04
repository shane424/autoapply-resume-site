import json
import pytest
from app.services.llm_client import _parse_json_response


def test_parse_clean_json():
    text = '["Python", "FastAPI", "Docker"]'
    result = _parse_json_response(text)
    assert result == ["Python", "FastAPI", "Docker"]


def test_parse_json_with_markdown_fences():
    text = "```json\n[\"Python\", \"Go\"]\n```"
    result = _parse_json_response(text)
    assert result == ["Python", "Go"]


def test_parse_json_object():
    data = {"summary": "A great engineer", "skills": ["Python"], "experience": [], "education": [], "keywords_added": []}
    text = json.dumps(data)
    result = _parse_json_response(text)
    assert result["summary"] == "A great engineer"


def test_parse_invalid_json_raises():
    with pytest.raises(Exception):
        _parse_json_response("this is not json")
