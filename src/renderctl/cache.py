"""SQLite result cache with bounded retention."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


class ResultCache:
    def __init__(self, path: Path, retention_hours: int = 168) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.retention = timedelta(hours=retention_hours)
        with closing(self._connect()) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS results (key TEXT PRIMARY KEY, payload TEXT NOT NULL, expires TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    @staticmethod
    def make_key(model_id: str, params: dict[str, Any]) -> str:
        raw = json.dumps([model_id, params], sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def put(self, key: str, payload: dict[str, Any]) -> None:
        expires = (datetime.now(UTC) + self.retention).isoformat()
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO results(key, payload, expires) VALUES (?, ?, ?)",
                (key, json.dumps(payload, sort_keys=True, default=str), expires),
            )

    def get(self, key: str) -> dict[str, Any] | None:
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as db, db:
            row = db.execute(
                "SELECT payload FROM results WHERE key = ? AND expires > ?", (key, now)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def cleanup(self) -> int:
        with closing(self._connect()) as db, db:
            cursor = db.execute("DELETE FROM results WHERE expires <= ?", (datetime.now(UTC).isoformat(),))
            return int(cursor.rowcount or 0)
