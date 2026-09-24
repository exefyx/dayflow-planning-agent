from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta


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
        urgency, reasons = 70, ["已经逾期"]
    elif hours_left <= 24:
        urgency, reasons = 50, ["24小时内截止"]
    elif hours_left <= 72:
        urgency, reasons = 30, ["3天内截止"]
    elif hours_left <= 168:
        urgency, reasons = 15, ["本周截止"]
    else:
        urgency, reasons = max(0, 10 - hours_left / 168), ["截止时间较远"]
    importance_points = task.importance * 10
    if task.importance >= 4:
        reasons.append("重要程度较高")
    deferral_points = min(task.deferrals * 8, 24)
    if task.deferrals:
        reasons.append(f"已经重新规划{task.deferrals}次")
    short_task_bonus = 6 if task.estimate_minutes <= 30 else 0
    if short_task_bonus:
        reasons.append("可以快速完成")
    return round(urgency + importance_points + deferral_points + short_task_bonus, 1), reasons


def build_plan(
    tasks: list[Task],
    available_minutes: int,
    start_time: str = "09:00",
    break_minutes: int = 10,
    now: datetime | None = None,
) -> dict:
    if available_minutes < 15 or available_minutes > 720:
        raise ValueError("可用时间必须在15到720分钟之间。")
    if break_minutes < 0 or break_minutes > 30:
        raise ValueError("休息时间必须在0到30分钟之间。")
    now = now or datetime.now()
    try:
        cursor = datetime.combine(now.date(), time.fromisoformat(start_time))
    except ValueError as exc:
        raise ValueError("开始时间格式无效。") from exc
    scored = []
    for task in tasks:
        score, reasons = priority_score(task, now)
        scored.append((score, ENERGY_RANK.get(task.energy, 2), task, reasons))
    scored.sort(key=lambda item: (-item[0], -item[1], item[2].due_at))

    remaining_window = available_minutes
    work_remaining = {item[2].id: item[2].estimate_minutes for item in scored}
    timeline: list[dict] = []
    scheduled_by_task = {item[2].id: 0 for item in scored}
    work_minutes = 0
    pause_minutes = 0

    # Round-robin focus blocks prevent one long task from consuming the whole day.
    while remaining_window >= 10 and any(value > 0 for value in work_remaining.values()):
        made_progress = False
        for score, _, task, reasons in scored:
            task_left = work_remaining[task.id]
            if task_left <= 0 or remaining_window < 10:
                continue
            duration = min(50, task_left, remaining_window)
            end = cursor + timedelta(minutes=duration)
            timeline.append({
                "type": "focus", "task_id": task.id, "title": task.title,
                "start": cursor.strftime("%H:%M"), "end": end.strftime("%H:%M"),
                "minutes": duration, "score": score, "reason": ", ".join(reasons),
                "energy": task.energy,
            })
            cursor = end
            remaining_window -= duration
            work_remaining[task.id] -= duration
            scheduled_by_task[task.id] += duration
            work_minutes += duration
            made_progress = True

            has_more_work = any(value > 0 for value in work_remaining.values())
            if has_more_work and break_minutes and remaining_window >= break_minutes + 10:
                break_end = cursor + timedelta(minutes=break_minutes)
                timeline.append({
                    "type": "break", "title": "休息与切换", "start": cursor.strftime("%H:%M"),
                    "end": break_end.strftime("%H:%M"), "minutes": break_minutes,
                })
                cursor = break_end
                remaining_window -= break_minutes
                pause_minutes += break_minutes
        if not made_progress:
            break

    blocks, unscheduled = [], []
    for score, _, task, reasons in scored:
        scheduled = scheduled_by_task[task.id]
        left = work_remaining[task.id]
        blocks.append({
            "task_id": task.id, "title": task.title, "scheduled_minutes": scheduled,
            "remaining_task_minutes": left, "score": score,
            "reason": ", ".join(reasons), "energy": task.energy,
        })
        if left:
            unscheduled.append({"task_id": task.id, "title": task.title, "minutes": left})
    return {
        "available_minutes": available_minutes, "work_minutes": work_minutes,
        "break_minutes": pause_minutes, "free_minutes": remaining_window,
        "timeline": timeline, "blocks": blocks, "unscheduled": unscheduled,
    }
