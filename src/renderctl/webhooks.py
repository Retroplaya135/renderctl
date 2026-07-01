"""Webhook payload normalization and callback isolation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass(frozen=True, slots=True)
class WebhookEvent:
    event: str
    job_id: str
    payload: dict[str, Any]

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "WebhookEvent":
        event = str(raw.get("event", "")).strip()
        job_id = str(raw.get("job_id", raw.get("id", ""))).strip()
        if not event or not job_id:
            raise ValueError("webhook event and job_id are required")
        return cls(event=event, job_id=job_id, payload=dict(raw))


Callback = Callable[[WebhookEvent], Awaitable[None]]


class WebhookDispatcher:
    def __init__(self) -> None:
        self._callbacks: list[Callback] = []

    def register(self, callback: Callback) -> None:
        self._callbacks.append(callback)

    async def dispatch(self, event: WebhookEvent) -> list[Exception]:
        outcomes = await asyncio.gather(
            *(callback(event) for callback in self._callbacks), return_exceptions=True
        )
        return [item for item in outcomes if isinstance(item, Exception)]
