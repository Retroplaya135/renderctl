"""Contained local asset storage."""

from __future__ import annotations

from pathlib import Path


class AssetStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, relative: str | Path) -> Path:
        candidate = (self.root / relative).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("asset path escapes configured root")
        return candidate

    def write(self, relative: str | Path, content: bytes) -> Path:
        destination = self.resolve(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return destination
