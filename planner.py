from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import ceil


ENERGY_RANK = {"low": 1, "medium": 2, "high": 3}


@dataclass
class Task:
    id: int
    title: str
    due_at: str
    estimate_minutes: int
    importance: int
    energy: str
    deferrals: int = 0


def priority_score(task: Task, now: datetime) -> tuple[float, list[str]]:
    due = datetime.fromisoformat(task.due_at)
    hours_left = (due - now).total_seconds() / 3600
    if hours_left <= 0:
        urgency, reasons = 70, ["overdue"]
    elif hours_left <= 24:
        urgency, reasons = 50, ["due within 24 hours"]
    elif hours_left <= 72:
        urgency, reasons = 30, ["due within 3 days"]
    elif hours_left <= 168:
        urgency, reasons = 15, ["due this week"]
    else:
        urgency, reasons = max(0, 10 - hours_left / 168), ["future deadline"]
    importance_points = task.importance * 10
    if task.importance >= 4:
        reasons.append("high importance")
    deferral_points = min(task.deferrals * 8, 24)
    if task.deferrals:
        reasons.append(f"replanned {task.deferrals} time(s)")
    short_task_bonus = 6 if task.estimate_minutes <= 30 else 0
    if short_task_bonus:
        reasons.append("quick win")
    return round(urgency + importance_points + deferral_points + short_task_bonus, 1), reasons


def build_plan(tasks: list[Task], available_minutes: int, now: datetime | None = None) -> dict:
    if available_minutes < 15 or available_minutes > 720:
        raise ValueError("Available time must be between 15 and 720 minutes.")
    now = now or datetime.now()
    scored = []
    for task in tasks:
        score, reasons = priority_score(task, now)
        scored.append((score, ENERGY_RANK.get(task.energy, 2), task, reasons))
    scored.sort(key=lambda item: (-item[0], -item[1], item[2].due_at))

    remaining, blocks, unscheduled = available_minutes, [], []
    for score, _, task, reasons in scored:
        if remaining < 15:
            unscheduled.append({"task_id": task.id, "title": task.title, "minutes": task.estimate_minutes})
            continue
        scheduled = min(task.estimate_minutes, remaining)
        chunks, left = [], scheduled
        for _ in range(ceil(scheduled / 50)):
            length = min(50, left)
            if length:
                chunks.append(length)
                left -= length
        blocks.append({
            "task_id": task.id, "title": task.title, "scheduled_minutes": scheduled,
            "remaining_task_minutes": task.estimate_minutes - scheduled, "chunks": chunks,
            "score": score, "reason": ", ".join(reasons), "energy": task.energy,
        })
        remaining -= scheduled
        if scheduled < task.estimate_minutes:
            unscheduled.append({"task_id": task.id, "title": task.title, "minutes": task.estimate_minutes - scheduled})
    return {"available_minutes": available_minutes, "scheduled_minutes": available_minutes - remaining,
            "free_minutes": remaining, "blocks": blocks, "unscheduled": unscheduled}
