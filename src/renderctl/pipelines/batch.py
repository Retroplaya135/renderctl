"""Batch execution helpers."""

from __future__ import annotations

from dataclasses import dataclass

from ..client import GenerateRequest, Job, RenderEngine


@dataclass(frozen=True, slots=True)
class BatchResult:
    jobs: tuple[Job, ...]

    @property
    def succeeded(self) -> int:
        return sum(job.error is None for job in self.jobs)


async def run_batch(engine: RenderEngine, requests: list[GenerateRequest]) -> BatchResult:
    return BatchResult(tuple(await engine.generate_batch(requests)))
