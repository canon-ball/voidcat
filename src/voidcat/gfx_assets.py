from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import TYPE_CHECKING, Any, cast

_pygame: Any
try:
    import pygame as _pygame
except ImportError:  # pragma: no cover - exercised when graphics extra is missing
    _pygame = None

if TYPE_CHECKING:
    import pygame
else:
    pygame = cast(Any, _pygame)


@dataclass
class SpriteCatalog:
    tile_size: int
    surfaces: dict[str, pygame.Surface]
    palette: dict[str, tuple[int, int, int, int]]

    def sprite(self, name: str) -> pygame.Surface:
        return self.surfaces[name]


def load_sprite_catalog() -> SpriteCatalog:
    if _pygame is None:
        raise RuntimeError("pygame-ce is required for the graphical frontend")

    data = json.loads(resources.files("voidcat").joinpath("assets/gfx/sprites.json").read_text())
    tile_size = int(data["tile_size"])
    pixel_size = int(data.get("pixel_size", 1))
    palette = {key: _hex_to_rgba(value) for key, value in data["palette"].items()}
    surfaces: dict[str, pygame.Surface] = {}

    for name, rows in data["sprites"].items():
        height = len(rows)
        width = len(rows[0])
        surface = pygame.Surface(
            (width * pixel_size, height * pixel_size), pygame.SRCALPHA, 32
        ).convert_alpha()
        surface.fill((0, 0, 0, 0))
        for y, row in enumerate(rows):
            for x, token in enumerate(row):
                color = palette[token]
                if color[3] == 0:
                    continue
                surface.fill(
                    color,
                    pygame.Rect(x * pixel_size, y * pixel_size, pixel_size, pixel_size),
                )
        if surface.get_size() != (tile_size, tile_size):
            surface = pygame.transform.scale(surface, (tile_size, tile_size))
        surfaces[name] = surface

    return SpriteCatalog(tile_size=tile_size, surfaces=surfaces, palette=palette)


def _hex_to_rgba(value: str) -> tuple[int, int, int, int]:
    raw = value.strip().lstrip("#")
    if len(raw) == 6:
        raw += "ff"
    if len(raw) != 8:
        raise ValueError(f"Expected RGBA hex value, got {value!r}")
    return (
        int(raw[0:2], 16),
        int(raw[2:4], 16),
        int(raw[4:6], 16),
        int(raw[6:8], 16),
    )
