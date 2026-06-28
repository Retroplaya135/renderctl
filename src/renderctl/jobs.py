"""Minimal durable queue for local workers."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class JobQueue:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, model_id TEXT NOT NULL, params TEXT NOT NULL, status TEXT NOT NULL, created TEXT NOT NULL, result TEXT, error TEXT)"
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def enqueue(self, model_id: str, params: dict[str, Any]) -> str:
        job_id = str(uuid.uuid4())
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO jobs(id, model_id, params, status, created) VALUES (?, ?, ?, 'pending', ?)",
                (job_id, model_id, json.dumps(params, sort_keys=True), datetime.now(UTC).isoformat()),
            )
        return job_id

    def claim(self) -> dict[str, Any] | None:
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM jobs WHERE status = 'pending' ORDER BY created, id LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            db.execute("UPDATE jobs SET status = 'running' WHERE id = ?", (row["id"],))
        return {"id": row["id"], "model_id": row["model_id"], "params": json.loads(row["params"])}

    def finish(self, job_id: str, result: dict[str, Any] | None = None, error: str | None = None) -> None:
        status = "failed" if error else "completed"
        with closing(self._connect()) as db, db:
            db.execute(
                "UPDATE jobs SET status = ?, result = ?, error = ? WHERE id = ?",
                (status, json.dumps(result, sort_keys=True) if result is not None else None, error, job_id),
            )
