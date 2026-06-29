"""Comparison jobs over the same synthetic input."""

from __future__ import annotations

from ..client import GenerateRequest, Job, RenderEngine


async def compare_models(
    engine: RenderEngine,
    model_ids: list[str],
    params: dict[str, object],
) -> list[Job]:
    return await engine.generate_batch(
        [GenerateRequest(model_id=model_id, params=dict(params)) for model_id in model_ids]
    )
