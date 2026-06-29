"""Reusable step constructors."""

from __future__ import annotations

from typing import Any

from ..client import GenerateRequest, RenderEngine
from .engine import PipelineStep


def generation_step(name: str, engine: RenderEngine, model_id: str, **params: Any) -> PipelineStep:
    async def run(_: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
        request = GenerateRequest(model_id=model_id, params={**params, **overrides})
        job = await engine.generate(request)
        if job.error:
            raise RuntimeError(job.error)
        return job.result or {}

    return PipelineStep(name=name, run=run)
