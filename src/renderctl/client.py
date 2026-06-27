"""Async orchestration around an application-supplied transport."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

from .config import RenderConfig


class JobStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class GenerateRequest:
    model_id: str
    params: dict[str, Any]
    priority: int = 0
    tags: tuple[str, ...] = ()


@dataclass(slots=True)
class Job:
    id: str
    model_id: str
    params: dict[str, Any]
    status: JobStatus
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    cost_estimate: float = 0.0


class Transport(Protocol):
    async def submit(self, request: GenerateRequest) -> dict[str, Any]: ...


class TokenBucket:
    def __init__(self, rate: float, burst: int) -> None:
        self._rate = rate
        self._burst = float(burst)
        self._tokens = float(burst)
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                self._tokens = min(
                    self._burst,
                    self._tokens + (now - self._last) * self._rate,
                )
                self._last = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                delay = (1 - self._tokens) / self._rate
            await asyncio.sleep(delay)


class RenderEngine:
    def __init__(self, transport: Transport, config: RenderConfig | None = None) -> None:
        self.config = config or RenderConfig()
        self._transport = transport
        self._limit = TokenBucket(self.config.requests_per_second, self.config.burst)
        self._semaphore = asyncio.Semaphore(self.config.concurrency)
        self._inflight: dict[str, asyncio.Task[Job]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def dedup_key(request: GenerateRequest) -> str:
        encoded = json.dumps(
            {"model_id": request.model_id, "params": request.params},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

    async def generate(self, request: GenerateRequest) -> Job:
        key = self.dedup_key(request)
        async with self._lock:
            task = self._inflight.get(key)
            if task is None:
                task = asyncio.create_task(self._run(request))
                self._inflight[key] = task
        try:
            return await asyncio.shield(task)
        finally:
            if task.done():
                async with self._lock:
                    if self._inflight.get(key) is task:
                        self._inflight.pop(key, None)

    async def generate_batch(self, requests: list[GenerateRequest]) -> list[Job]:
        return list(await asyncio.gather(*(self.generate(item) for item in requests)))

    async def _run(self, request: GenerateRequest) -> Job:
        job = Job(
            id=str(uuid.uuid4()),
            model_id=request.model_id,
            params=dict(request.params),
            status=JobStatus.IN_PROGRESS,
        )
        async with self._semaphore:
            for attempt in range(self.config.max_retries + 1):
                await self._limit.acquire()
                try:
                    job.result = await self._transport.submit(request)
                    job.status = JobStatus.COMPLETED
                    job.completed_at = datetime.now(UTC)
                    return job
                except Exception as exc:
                    if attempt >= self.config.max_retries:
                        job.status = JobStatus.FAILED
                        job.error = f"{type(exc).__name__}: {exc}"
                        job.completed_at = datetime.now(UTC)
                        return job
                    await asyncio.sleep(self.config.retry_base_seconds * (2**attempt))
        return job
