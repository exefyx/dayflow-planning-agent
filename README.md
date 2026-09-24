# DayFlow Planning Agent

A small, local-first planning agent for a common daily problem: deciding what to do when tasks have different deadlines, importance, durations and energy requirements.

DayFlow does not call a paid AI API. It keeps task memory in SQLite, scores urgency and importance, builds a time-constrained plan, explains each decision and learns from missed tasks by increasing their priority during replanning.

## What works

- Add tasks with deadline, duration, importance and required energy
- Generate a realistic plan for the time available today
- Generate a clock-based timeline with focus blocks and breaks
- Rotate between tasks so one long task cannot consume the whole plan
- Explain why each task was prioritised
- Edit, delete, complete, miss or reopen tasks
- Replan missed work with a deferral penalty
- Store all task memory locally in SQLite
- Load a demonstration day with overwrite protection
- Optionally parse a natural-language task with a local Ollama model
- Use a responsive browser interface

## Why this is agent-like

The application has four explicit parts of an agent loop:

1. **Memory** — persistent tasks and past deferrals
2. **Planning** — priority scoring and time constraints
3. **Action** — a concrete ordered work plan
4. **Feedback** — completion or missed-task signals change the next plan

The implementation is deliberately transparent: the user can see every score and explanation instead of trusting an unexplained model output.

## Run

```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

Open `http://127.0.0.1:8000`. No API key, account or internet connection is required.

### Optional local language model

The manual planner is fully functional without a model. If Ollama is already installed, pull the default small model and restart DayFlow:

```bash
ollama pull qwen2.5:1.5b
```

You can select another installed model with `OLLAMA_MODEL`. Natural-language parsing only fills the task form; the user reviews the fields before saving.

## Test

```bash
pytest -q
```

## Technology

Python, FastAPI, SQLite, constraint-based scheduling, HTML, CSS and JavaScript.
