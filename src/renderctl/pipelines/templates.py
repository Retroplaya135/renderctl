"""Small original templates using synthetic model identifiers."""

from __future__ import annotations

from .storyboard import Scene, Storyboard


def three_scene_demo() -> Storyboard:
    return Storyboard(
        title="Synthetic product motion",
        scenes=(
            Scene("establish", "neutral object on a plain background", 2.0),
            Scene("detail", "close view of material and form", 2.0),
            Scene("resolve", "object returns to the centered composition", 2.0),
        ),
    )
