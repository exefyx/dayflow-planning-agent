from types import SimpleNamespace

import pytest

from agent import extract_trace, run_research


def fake_response():
    return SimpleNamespace(
        output_text="A sourced answer [1].",
        output=[
            {"type": "web_search_call", "action": {"type": "search", "query": "offline bilingual note apps"}},
            {"type": "message", "content": [{"annotations": [
                {"type": "url_citation", "url": "https://example.com/review", "title": "Independent review"}
            ]}]},
        ],
    )


class FakeResponses:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return fake_response()


def test_agent_requires_search_and_returns_trace():
    responses = FakeResponses()
    result = run_research(SimpleNamespace(responses=responses), "Which app should I use?")
    assert responses.kwargs["tool_choice"] == "required"
    assert responses.kwargs["tools"][0]["type"] == "web_search"
    assert result.sources[0]["url"] == "https://example.com/review"
    assert result.searches == ["offline bilingual note apps"]


def test_short_question_is_rejected():
    with pytest.raises(ValueError):
        run_research(SimpleNamespace(), "why")


def test_duplicate_sources_are_removed():
    response = fake_response()
    response.output[1]["content"][0]["annotations"].append(
        {"type": "url_citation", "url": "https://example.com/review", "title": "Same source"}
    )
    sources, _ = extract_trace(response)
    assert len(sources) == 1
