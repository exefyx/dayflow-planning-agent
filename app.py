from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from planner import Task, build_plan


DB_PATH = Path(os.getenv("DAYFLOW_DB", "dayflow.db"))
app = FastAPI(title="DayFlow Planning Agent", version="1.0.0")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, due_at TEXT NOT NULL,
            estimate_minutes INTEGER NOT NULL, importance INTEGER NOT NULL, energy TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open', deferrals INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL)""")


init_db()


class TaskIn(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    due_at: str
    estimate_minutes: int = Field(ge=10, le=600)
    importance: int = Field(ge=1, le=5)
    energy: str = "medium"


class PlanIn(BaseModel):
    available_minutes: int = Field(ge=15, le=720)


@app.get("/")
def home():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "requires_api_key": False}


@app.get("/api/tasks")
def list_tasks():
    with connect() as db:
        rows = db.execute("SELECT * FROM tasks ORDER BY status, due_at").fetchall()
    return [dict(row) for row in rows]


@app.post("/api/tasks", status_code=201)
def create_task(task: TaskIn):
    if task.energy not in {"low", "medium", "high"}:
        raise HTTPException(422, detail="精力要求必须是低、中或高")
    try:
        datetime.fromisoformat(task.due_at)
    except ValueError as exc:
        raise HTTPException(422, detail="截止时间格式无效") from exc
    with connect() as db:
        cursor = db.execute("INSERT INTO tasks(title,due_at,estimate_minutes,importance,energy,created_at) VALUES(?,?,?,?,?,?)",
            (task.title, task.due_at, task.estimate_minutes, task.importance, task.energy, datetime.now().isoformat()))
        row = db.execute("SELECT * FROM tasks WHERE id=?", (cursor.lastrowid,)).fetchone()
    return dict(row)


@app.patch("/api/tasks/{task_id}/{action}")
def update_task(task_id: int, action: str):
    if action not in {"complete", "replan", "reopen"}:
        raise HTTPException(422, detail="无法识别的操作")
    with connect() as db:
        if not db.execute("SELECT id FROM tasks WHERE id=?", (task_id,)).fetchone():
            raise HTTPException(404, detail="没有找到这个任务")
        if action == "complete":
            db.execute("UPDATE tasks SET status='done' WHERE id=?", (task_id,))
        elif action == "reopen":
            db.execute("UPDATE tasks SET status='open' WHERE id=?", (task_id,))
        else:
            db.execute("UPDATE tasks SET status='open', deferrals=deferrals+1 WHERE id=?", (task_id,))
        row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    return dict(row)


@app.post("/api/plan")
def create_plan(request: PlanIn):
    with connect() as db:
        rows = db.execute("SELECT * FROM tasks WHERE status='open'").fetchall()
    tasks = [Task(row["id"], row["title"], row["due_at"], row["estimate_minutes"],
                  row["importance"], row["energy"], row["deferrals"]) for row in rows]
    return build_plan(tasks, request.available_minutes)


@app.post("/api/demo", status_code=201)
def seed_demo():
    now = datetime.now().replace(second=0, microsecond=0)
    examples = [
        ("完成数据分析作业", (now + timedelta(hours=10)).isoformat(), 90, 5, "high"),
        ("回复实习邮件", (now + timedelta(hours=4)).isoformat(), 15, 4, "low"),
        ("整理研究论文笔记", (now + timedelta(days=2)).isoformat(), 45, 3, "medium"),
    ]
    with connect() as db:
        db.execute("DELETE FROM tasks")
        for item in examples:
            db.execute("INSERT INTO tasks(title,due_at,estimate_minutes,importance,energy,created_at) VALUES(?,?,?,?,?,?)", (*item, now.isoformat()))
    return {"created": len(examples)}
