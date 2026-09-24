from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel, Field

from agent import result_dict, run_research


DB_PATH = Path(os.getenv("RESEARCH_DB", "research.db"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")

app = FastAPI(title="Everyday Research Agent", version="1.0.0")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


def connect():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS research_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL, answer TEXT NOT NULL, sources TEXT NOT NULL,
            searches TEXT NOT NULL, model TEXT NOT NULL, created_at TEXT NOT NULL
        )""")


init_db()


class ResearchRequest(BaseModel):
    question: str = Field(min_length=5, max_length=1200)


@app.get("/")
def home():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "configured": bool(os.getenv("OPENAI_API_KEY")), "model": MODEL}


@app.post("/api/research", status_code=201)
def research(request: ResearchRequest):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(503, detail="Set OPENAI_API_KEY before running research.")
    try:
        result = run_research(OpenAI(), request.question, MODEL)
    except Exception as exc:
        raise HTTPException(502, detail=f"Research request failed: {exc}") from exc
    data = result_dict(result)
    created_at = datetime.now(timezone.utc).isoformat()
    with connect() as db:
        cursor = db.execute(
            "INSERT INTO research_runs(question, answer, sources, searches, model, created_at) VALUES(?,?,?,?,?,?)",
            (request.question, data["answer"], json.dumps(data["sources"]), json.dumps(data["searches"]), MODEL, created_at),
        )
        run_id = cursor.lastrowid
    return {"id": run_id, "question": request.question, "created_at": created_at, **data}


@app.get("/api/history")
def history():
    with connect() as db:
        rows = db.execute("SELECT id, question, model, created_at FROM research_runs ORDER BY id DESC LIMIT 20").fetchall()
    return [dict(row) for row in rows]


@app.get("/api/history/{run_id}")
def history_item(run_id: int):
    with connect() as db:
        row = db.execute("SELECT * FROM research_runs WHERE id=?", (run_id,)).fetchone()
    if not row:
        raise HTTPException(404, detail="Research run not found")
    data = dict(row)
    data["sources"] = json.loads(data["sources"])
    data["searches"] = json.loads(data["searches"])
    return data
