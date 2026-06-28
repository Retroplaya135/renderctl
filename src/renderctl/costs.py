"""Local cost ledger with optional budget checks."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path


class CostTracker:
    def __init__(self, path: Path, daily: float | None = None, monthly: float | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.daily_budget = daily
        self.monthly_budget = monthly
        with closing(self._connect()) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS costs (job_id TEXT PRIMARY KEY, model_id TEXT NOT NULL, amount REAL NOT NULL, status TEXT NOT NULL, recorded TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def record(self, job_id: str, model_id: str, amount: float, status: str = "completed") -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO costs VALUES (?, ?, ?, ?, ?)",
                (job_id, model_id, float(amount), status, datetime.now(UTC).isoformat()),
            )

    def _total_since(self, start: datetime) -> float:
        with closing(self._connect()) as db, db:
            row = db.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM costs WHERE status = 'completed' AND recorded >= ?",
                (start.isoformat(),),
            ).fetchone()
        return float(row[0])

    def check_budget(self, additional: float = 0) -> tuple[bool, str]:
        now = datetime.now(UTC)
        daily = self._total_since(now.replace(hour=0, minute=0, second=0, microsecond=0))
        monthly = self._total_since(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))
        if self.daily_budget is not None and daily + additional > self.daily_budget:
            return False, "daily budget exceeded"
        if self.monthly_budget is not None and monthly + additional > self.monthly_budget:
            return False, "monthly budget exceeded"
        return True, "within budget"
