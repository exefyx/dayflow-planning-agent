# Everyday Research Agent

A small AI demo for questions that are annoying to research repeatedly: comparing products, checking current rules, choosing tools, or turning scattered sources into a short decision brief.

The model is not used as a text box. It receives a real web-search tool, decides what to search, checks current sources, returns citations, and saves each research run for later review.

## Features

- Agentic web research through the OpenAI Responses API
- Required live search for current, source-backed answers
- Visible source links and search-query trace
- Clear uncertainty and next-step sections
- SQLite research history
- Small web interface, REST API and automated tests
- Configurable model through `OPENAI_MODEL`

## Run

```bash
python -m venv .venv
# Activate the environment, then:
pip install -r requirements.txt
copy .env.example .env
```

Set `OPENAI_API_KEY` in your environment. Do not commit the key.

```bash
uvicorn app:app --reload
```

Open `http://127.0.0.1:8000`.

## Test

```bash
pytest -q
```

The tests use a fake Responses client, so they do not spend API credits.

## What this demonstrates

The project is intentionally small. Its purpose is to show practical interest in agent workflows: connecting a model to a tool, making tool use observable, preserving citations, handling configuration safely and turning the result into a reusable everyday utility.

## Privacy and cost

Questions are sent to the configured OpenAI API project and saved locally in SQLite. Web search and model usage may incur API charges. Avoid submitting confidential information.
