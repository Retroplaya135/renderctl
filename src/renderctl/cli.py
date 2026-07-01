"""Small offline command surface for fixtures and a synthetic run."""

from __future__ import annotations

import argparse
import asyncio
import json
from importlib.resources import files
from typing import Any

from .client import GenerateRequest, RenderEngine
from .config import RenderConfig


def _fixture(name: str) -> dict[str, Any]:
    path = files("renderctl").joinpath("fixtures", name)
    return json.loads(path.read_text(encoding="utf-8"))


class _DemoTransport:
    async def submit(self, request: GenerateRequest) -> dict[str, Any]:
        return {
            "fixture": True,
            "model_id": request.model_id,
            "summary": "synthetic request completed locally",
        }


async def _demo() -> dict[str, Any]:
    engine = RenderEngine(
        _DemoTransport(),
        RenderConfig(requests_per_second=100, burst=4, max_retries=0),
    )
    job = await engine.generate(
        GenerateRequest(
            "fixture/image-basic",
            {"prompt": "neutral geometric object", "width": 512, "height": 512},
        )
    )
    return {"status": job.status, "model_id": job.model_id, "result": job.result}


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="renderctl")
    subcommands = command.add_subparsers(dest="command", required=True)
    subcommands.add_parser("models", help="print the synthetic offline model fixture")
    subcommands.add_parser("prompts", help="print the synthetic offline prompt fixture")
    subcommands.add_parser("demo", help="run one synthetic request without network access")
    return command


def main() -> None:
    args = parser().parse_args()
    if args.command == "models":
        payload = _fixture("models.json")
    elif args.command == "prompts":
        payload = _fixture("prompts.json")
    else:
        payload = asyncio.run(_demo())
    print(json.dumps(payload, indent=2, default=str, sort_keys=True))


if __name__ == "__main__":
    main()
