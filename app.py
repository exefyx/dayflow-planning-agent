from __future__ import annotations

import os
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from planner import Task, build_plan


DB_PATH = Path(os.getenv("DAYFLOW_DB", "dayflow.db"))
OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
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


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=120)
    due_at: str | None = None
    estimate_minutes: int | None = Field(default=None, ge=10, le=600)
    importance: int | None = Field(default=None, ge=1, le=5)
    energy: str | None = None


class PlanIn(BaseModel):
    available_minutes: int = Field(ge=15, le=720)
    start_time: str = "09:00"
    break_minutes: int = Field(default=10, ge=0, le=30)


class NaturalTaskIn(BaseModel):
    text: str = Field(min_length=5, max_length=500)


def validate_task_fields(due_at: str | None, energy: str | None):
    if energy is not None and energy not in {"low", "medium", "high"}:
        raise HTTPException(422, detail="精力要求必须是低、中或高")
    if due_at is not None:
        try:
            datetime.fromisoformat(due_at)
        except ValueError as exc:
            raise HTTPException(422, detail="截止时间格式无效") from exc


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
    validate_task_fields(task.due_at, task.energy)
    with connect() as db:
        cursor = db.execute("INSERT INTO tasks(title,due_at,estimate_minutes,importance,energy,created_at) VALUES(?,?,?,?,?,?)",
            (task.title, task.due_at, task.estimate_minutes, task.importance, task.energy, datetime.now().isoformat()))
        row = db.execute("SELECT * FROM tasks WHERE id=?", (cursor.lastrowid,)).fetchone()
    return dict(row)


@app.patch("/api/tasks/{task_id}")
def edit_task(task_id: int, task: TaskUpdate):
    changes = task.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise HTTPException(422, detail="没有需要更新的内容")
    validate_task_fields(changes.get("due_at"), changes.get("energy"))
    with connect() as db:
        if not db.execute("SELECT id FROM tasks WHERE id=?", (task_id,)).fetchone():
            raise HTTPException(404, detail="没有找到这个任务")
        assignments = ", ".join(f"{field}=?" for field in changes)
        db.execute(f"UPDATE tasks SET {assignments} WHERE id=?", (*changes.values(), task_id))
        row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    return dict(row)


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    with connect() as db:
        cursor = db.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        if not cursor.rowcount:
            raise HTTPException(404, detail="没有找到这个任务")


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
    try:
        return build_plan(tasks, request.available_minutes, request.start_time, request.break_minutes)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


@app.post("/api/demo", status_code=201)
def seed_demo(replace: bool = False):
    now = datetime.now().replace(second=0, microsecond=0)
    examples = [
        ("完成数据分析作业", (now + timedelta(hours=10)).isoformat(), 90, 5, "high"),
        ("回复实习邮件", (now + timedelta(hours=4)).isoformat(), 15, 4, "low"),
        ("整理研究论文笔记", (now + timedelta(days=2)).isoformat(), 45, 3, "medium"),
    ]
    with connect() as db:
        count = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if count and not replace:
            raise HTTPException(409, detail="已有任务，加载示例会覆盖它们。")
        db.execute("DELETE FROM tasks")
        for item in examples:
            db.execute("INSERT INTO tasks(title,due_at,estimate_minutes,importance,energy,created_at) VALUES(?,?,?,?,?,?)", (*item, now.isoformat()))
    return {"created": len(examples)}


@app.get("/api/ollama/status")
def ollama_status():
    try:
        response = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        response.raise_for_status()
        models = [item.get("name", "") for item in response.json().get("models", [])]
        return {"available": True, "model": OLLAMA_MODEL, "installed": any(name.startswith(OLLAMA_MODEL) for name in models)}
    except (httpx.HTTPError, ValueError):
        return {"available": False, "model": OLLAMA_MODEL, "installed": False}


@app.post("/api/ollama/parse")
def parse_natural_task(request: NaturalTaskIn):
    prompt = f"""现在是 {datetime.now().isoformat(timespec='minutes')}。
把用户的中文任务描述转换为 JSON，只返回 JSON，不要解释：
{{"title":"简洁标题","due_at":"YYYY-MM-DDTHH:MM","estimate_minutes":45,"importance":3,"energy":"low|medium|high"}}
重要程度范围1到5，耗时范围10到600分钟。信息缺失时做保守推断。
用户输入：{request.text}"""
    try:
        response = httpx.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": OLLAMA_MODEL, "stream": False, "format": "json", "messages": [{"role": "user", "content": prompt}]},
            timeout=45,
        )
        response.raise_for_status()
        raw = response.json()["message"]["content"]
        parsed = json.loads(raw)
        task = TaskIn.model_validate(parsed)
        validate_task_fields(task.due_at, task.energy)
        return task.model_dump()
    except httpx.ConnectError as exc:
        raise HTTPException(503, detail="没有检测到 Ollama；可以继续手动添加任务。") from exc
    except (httpx.HTTPError, KeyError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(502, detail="本地模型未能识别任务，请修改描述或手动填写。") from exc
