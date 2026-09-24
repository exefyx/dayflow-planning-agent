from datetime import datetime, timedelta

import pytest

from planner import Task, build_plan, priority_score


NOW = datetime(2026, 9, 25, 9, 0)


def task(task_id, title, hours, minutes, importance, deferrals=0):
    return Task(task_id, title, (NOW + timedelta(hours=hours)).isoformat(), minutes, importance, "medium", deferrals)


def test_urgent_important_task_is_first():
    plan = build_plan([task(1, "Future reading", 240, 30, 2), task(2, "Submit assignment", 8, 60, 5)], 90, now=NOW)
    assert plan["blocks"][0]["task_id"] == 2


def test_plan_never_exceeds_available_time():
    plan = build_plan([task(1, "Long project", 24, 180, 5), task(2, "Email", 12, 30, 4)], 75, now=NOW)
    assert plan["work_minutes"] + plan["break_minutes"] + plan["free_minutes"] == 75
    assert plan["unscheduled"]


def test_deferral_increases_priority():
    normal = task(1, "Normal", 100, 30, 3)
    delayed = task(2, "Delayed", 100, 30, 3, deferrals=2)
    assert priority_score(delayed, NOW)[0] > priority_score(normal, NOW)[0]


def test_invalid_available_time_is_rejected():
    with pytest.raises(ValueError):
        build_plan([], 5, NOW)


def test_plan_has_clock_times_breaks_and_fair_task_rotation():
    tasks = [task(1, "Large task", 8, 150, 5), task(2, "Small task", 10, 20, 4)]
    plan = build_plan(tasks, 100, "09:00", 10, NOW)
    focus = [item for item in plan["timeline"] if item["type"] == "focus"]
    assert focus[0]["start"] == "09:00"
    assert focus[0]["minutes"] == 50
    assert focus[1]["task_id"] == 2
    assert plan["break_minutes"] > 0
