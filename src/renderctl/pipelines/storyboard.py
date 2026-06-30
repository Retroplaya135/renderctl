"""Provider-neutral storyboard plan data."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Scene:
    name: str
    prompt: str
    duration_seconds: float


@dataclass(frozen=True, slots=True)
class Storyboard:
    title: str
    scenes: tuple[Scene, ...]

    @property
    def duration_seconds(self) -> float:
        return sum(scene.duration_seconds for scene in self.scenes)
