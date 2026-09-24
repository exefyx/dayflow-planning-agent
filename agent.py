from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


SYSTEM_PROMPT = """You are a compact research agent for everyday decisions.
Use web search to verify current facts instead of relying on memory.
Return a concise Markdown brief with these sections:
1. Answer
2. What the evidence says
3. Uncertainty or disagreement
4. Practical next step
Cite sources inline. Never invent a source, price, date, quotation, or feature.
"""


@dataclass
class ResearchResult:
    answer: str
    sources: list[dict[str, str]]
    searches: list[str]
    model: str


def _value(item: Any, key: str, default=None):
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def extract_trace(response: Any) -> tuple[list[dict[str, str]], list[str]]:
    sources: list[dict[str, str]] = []
    searches: list[str] = []
    seen_urls: set[str] = set()
    for item in _value(response, "output", []) or []:
        item_type = _value(item, "type", "")
        if item_type == "web_search_call":
            action = _value(item, "action", {}) or {}
            query = _value(action, "query")
            if query:
                searches.append(str(query))
        if item_type != "message":
            continue
        for content in _value(item, "content", []) or []:
            for annotation in _value(content, "annotations", []) or []:
                if _value(annotation, "type") != "url_citation":
                    continue
                citation = _value(annotation, "url_citation", annotation)
                url = _value(citation, "url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    sources.append({"title": _value(citation, "title", url), "url": url})
    return sources, searches


def run_research(client: Any, question: str, model: str = "gpt-5.5") -> ResearchResult:
    question = question.strip()
    if len(question) < 5:
        raise ValueError("Please enter a more specific question.")
    if len(question) > 1200:
        raise ValueError("Question is too long; keep it under 1,200 characters.")
    response = client.responses.create(
        model=model,
        instructions=SYSTEM_PROMPT,
        tools=[{"type": "web_search", "search_context_size": "medium"}],
        tool_choice="required",
        input=question,
    )
    sources, searches = extract_trace(response)
    return ResearchResult(
        answer=response.output_text,
        sources=sources,
        searches=searches,
        model=model,
    )


def result_dict(result: ResearchResult) -> dict:
    return asdict(result)
