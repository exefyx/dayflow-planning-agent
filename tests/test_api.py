from pathlib import Path

from fastapi.testclient import TestClient

import app as module


def client(tmp_path: Path):
    module.DB_PATH = tmp_path / "dayflow-test.db"
    module.init_db()
    return TestClient(module.app)


def sample_task():
    return {"title": "准备课程展示", "due_at": "2026-09-26T18:00", "estimate_minutes": 60, "importance": 4, "energy": "high"}


def test_task_crud_and_completion(tmp_path):
    api = client(tmp_path)
    created = api.post("/api/tasks", json=sample_task())
    assert created.status_code == 201
    task_id = created.json()["id"]
    edited = api.patch(f"/api/tasks/{task_id}", json={"estimate_minutes": 75})
    assert edited.json()["estimate_minutes"] == 75
    completed = api.patch(f"/api/tasks/{task_id}/complete")
    assert completed.json()["status"] == "done"
    plan = api.post("/api/plan", json={"available_minutes": 120, "start_time": "09:00", "break_minutes": 10})
    assert plan.json()["timeline"] == []
    assert api.delete(f"/api/tasks/{task_id}").status_code == 204


def test_demo_requires_explicit_replace(tmp_path):
    api = client(tmp_path)
    api.post("/api/tasks", json=sample_task())
    assert api.post("/api/demo").status_code == 409
    assert api.post("/api/demo?replace=true").status_code == 201
    assert len(api.get("/api/tasks").json()) == 3
