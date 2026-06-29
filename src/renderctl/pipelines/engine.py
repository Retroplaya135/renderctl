"""Small dependency-aware pipeline executor."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


StepFunction = Callable[[dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class PipelineStep:
    name: str
    run: StepFunction
    depends_on: tuple[str, ...] = ()
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Pipeline:
    name: str
    steps: tuple[PipelineStep, ...]


class PipelineEngine:
    async def run(self, pipeline: Pipeline, context: dict[str, Any] | None = None) -> dict[str, Any]:
        remaining = {step.name: step for step in pipeline.steps}
        if len(remaining) != len(pipeline.steps):
            raise ValueError("pipeline step names must be unique")
        results: dict[str, Any] = dict(context or {})
        completed: set[str] = set()
        while remaining:
            ready = [step for step in remaining.values() if set(step.depends_on) <= completed]
            if not ready:
                raise ValueError("pipeline contains a cycle or missing dependency")
            values = await asyncio.gather(*(step.run(results, dict(step.params)) for step in ready))
            for step, value in zip(ready, values, strict=True):
                results[step.name] = value
                completed.add(step.name)
                remaining.pop(step.name)
        return results
