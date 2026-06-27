"""Local configuration without credential persistence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RenderConfig:
    storage_path: Path = Path(".renderctl")
    concurrency: int = 4
    requests_per_second: float = 5.0
    burst: int = 8
    max_retries: int = 3
    retry_base_seconds: float = 0.05
    cache_retention_hours: int = 168
    budget_daily: float | None = None
    budget_monthly: float | None = None

    def __post_init__(self) -> None:
        if self.concurrency < 1:
            raise ValueError("concurrency must be positive")
        if self.requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        if self.burst < 1 or self.max_retries < 0:
            raise ValueError("burst must be positive and max_retries non-negative")
        if self.cache_retention_hours < 1:
            raise ValueError("cache_retention_hours must be positive")

    def ensure_dirs(self) -> None:
        for name in ("assets", "cache", "logs"):
            (self.storage_path.expanduser() / name).mkdir(parents=True, exist_ok=True)
