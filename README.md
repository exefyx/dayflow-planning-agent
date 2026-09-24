# DayFlow Planning Agent

A small, local-first planning agent for a common daily problem: deciding what to do when tasks have different deadlines, importance, durations and energy requirements.

DayFlow does not call a paid AI API. It keeps task memory in SQLite, scores urgency and importance, builds a time-constrained plan, explains each decision and learns from missed tasks by increasing their priority during replanning.

## What works

- Add tasks with deadline, duration, importance and required energy
- Generate a realistic plan for the time available today
- Split long tasks into focus blocks of up to 50 minutes
- Explain why each task was prioritised
- Mark tasks complete, missed or reopened
- Replan missed work with a deferral penalty
- Store all task memory locally in SQLite
- Load a one-click demonstration day
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

## Test

```bash
pytest -q
```

## Technology

Python, FastAPI, SQLite, constraint-based scheduling, HTML, CSS and JavaScript.
