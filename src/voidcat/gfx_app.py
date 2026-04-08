from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from .controller import GameController, OverlayKind, Scene
from .engine import GameEngine
from .gfx_assets import SpriteCatalog, load_sprite_catalog
from .help import HELP_PAGES
from .models import (
    MAX_LOG_LINES,
    ActionType,
    AlertState,
    BarColor,
    CellColor,
    EffectKind,
    GameMode,
    MapMarker,
    Point,
    RenderCell,
    RenderEffect,
    RenderState,
    ScoreEntry,
)

_pygame: Any
try:
    import pygame as _pygame
except ImportError:  # pragma: no cover - exercised when graphics extra is missing
    _pygame = None

if TYPE_CHECKING:
    import pygame
else:
    pygame = cast(Any, _pygame)


INTERNAL_WIDTH = 1104
INTERNAL_HEIGHT = 720
INTERNAL_SIZE = (INTERNAL_WIDTH, INTERNAL_HEIGHT)
WINDOWED_SIZE = (1440, 900)
MAP_ORIGIN = (46, 116)
MAP_TILES = (35, 15)
TILE_SIZE = 16
MAP_SIZE = (MAP_TILES[0] * TILE_SIZE, MAP_TILES[1] * TILE_SIZE)
MAP_PANEL_BOUNDS = (32, 92, MAP_SIZE[0] + 28, MAP_SIZE[1] + 40)
SIDEBAR_BOUNDS = (648, 92, 424, 408)
LOG_BOUNDS = (32, 516, 1040, 172)

SCENE_TITLE = "title"
SCENE_GAME = "game"
SCENE_HELP = "help"
SCENE_SCORES = "scores"

RGBColor = tuple[int, int, int]
RGBAColor = tuple[int, int, int, int]
ColorValue = RGBColor | RGBAColor

PALETTE: dict[str, ColorValue] = {
    "bg": (5, 9, 14),
    "panel": (10, 18, 24, 228),
    "panel_dim": (9, 14, 20, 236),
    "steel": (31, 54, 70),
    "line": (73, 135, 160),
    "text": (227, 236, 240),
    "muted": (147, 164, 174),
    "danger": (227, 81, 78),
    "danger_hot": (255, 135, 124),
    "alert": (241, 82, 70),
    "gold": (242, 212, 124),
    "power": (146, 227, 120),
    "noise": (235, 177, 86),
    "cyan": (118, 220, 230),
    "shadow": (0, 0, 0, 150),
    "fog": (10, 18, 26, 150),
}

BAR_COLORS: dict[BarColor, RGBColor] = {
    BarColor.POWER: (146, 227, 120),
    BarColor.NOISE: (235, 177, 86),
    BarColor.ALERT: (241, 82, 70),
}


def main() -> None:
    if _pygame is None:
        raise SystemExit("Install the package first: python3 -m pip install -e .")
    app = GfxApp()
    try:
        app.run()
    finally:
        app.shutdown()


class GfxApp:
    def __init__(
        self,
        *,
        seed: int | None = None,
        score_file: Path | None = None,
        window_size: tuple[int, int] = WINDOWED_SIZE,
        fullscreen: bool | None = None,
    ) -> None:
        if _pygame is None:
            raise RuntimeError("pygame-ce is required for the graphical frontend")

        if "SDL_VIDEODRIVER" not in os.environ:
            os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
        pygame.init()
        pygame.font.init()
        pygame.display.set_caption("VOIDCAT // Alarm Ship")
        self.windowed_size = window_size
        self.fullscreen_capable = os.environ.get("SDL_VIDEODRIVER") != "dummy"
        self.fullscreen_requested = (
            self.fullscreen_capable if fullscreen is None else bool(fullscreen)
        )
        self.window = self._create_window()
        self.canvas = pygame.Surface(INTERNAL_SIZE).convert_alpha()
        self.clock = pygame.time.Clock()
        self.assets: SpriteCatalog = load_sprite_catalog()
        self.font_small = pygame.font.Font(None, 20)
        self.font_body = pygame.font.Font(None, 24)
        self.font_label = pygame.font.Font(None, 30)
        self.font_header = pygame.font.Font(None, 44)
        self.font_title = pygame.font.Font(None, 68)
        self.map_panel_rect = pygame.Rect(*MAP_PANEL_BOUNDS)
        self.sidebar_rect = pygame.Rect(*SIDEBAR_BOUNDS)
        self.log_rect = pygame.Rect(*LOG_BOUNDS)
        self.engine = GameEngine(seed=seed, score_file=score_file)
        self.controller = GameController(self.engine)
        self.effect_snapshot: RenderState | None = None
        self.effect_started_ms: int | None = None
        self.threat_view_active = False
        self.should_quit = False

    @property
    def scene(self) -> str:
        return self.controller.scene.value

    @scene.setter
    def scene(self, value: str | Scene) -> None:
        self.controller.scene = value if isinstance(value, Scene) else Scene(value)

    @property
    def return_scene(self) -> str:
        return self.controller.return_scene.value

    @return_scene.setter
    def return_scene(self, value: str | Scene) -> None:
        self.controller.return_scene = value if isinstance(value, Scene) else Scene(value)

    @property
    def help_page_index(self) -> int:
        return self.controller.help_page_index

    @help_page_index.setter
    def help_page_index(self, value: int) -> None:
        self.controller.help_page_index = value

    @property
    def pending_action(self) -> ActionType | None:
        return self.controller.pending_action

    @pending_action.setter
    def pending_action(self, value: ActionType | None) -> None:
        self.controller.pending_action = value

    @property
    def quit_confirm(self) -> bool:
        return self.controller.quit_confirm

    @quit_confirm.setter
    def quit_confirm(self, value: bool) -> None:
        self.controller.quit_confirm = value

    @property
    def fullscreen_active(self) -> bool:
        return self.fullscreen_requested and self.fullscreen_capable

    @property
    def scene_name(self) -> str:
        return self.scene

    def shutdown(self) -> None:
        if pygame is not None:
            pygame.display.quit()
            pygame.quit()

    def _desktop_size(self) -> tuple[int, int]:
        sizes = pygame.display.get_desktop_sizes()
        if sizes:
            return sizes[0]
        info = pygame.display.Info()
        if info.current_w > 0 and info.current_h > 0:
            return info.current_w, info.current_h
        return self.windowed_size

    def _create_window(self) -> pygame.Surface:
        if self.fullscreen_active:
            return pygame.display.set_mode(self._desktop_size(), pygame.FULLSCREEN)
        desktop_width, desktop_height = self._desktop_size()
        width = min(self.windowed_size[0], desktop_width)
        height = min(self.windowed_size[1], desktop_height)
        return pygame.display.set_mode((width, height), pygame.RESIZABLE)

    def _toggle_fullscreen(self) -> None:
        self.fullscreen_requested = not self.fullscreen_requested
        self.window = self._create_window()

    def run(self) -> None:
        while not self.should_quit:
            for event in pygame.event.get():
                self.handle_event(event)
            self.render_frame()
            self.clock.tick(60)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.should_quit = True
            return
        if event.type != pygame.KEYDOWN:
            return
        key = _key_from_event(event)
        if key is not None:
            self.handle_key(key)

    def handle_key(self, key: str) -> None:
        if key == "f11":
            self._toggle_fullscreen()
            return
        if self.scene == SCENE_GAME and self.engine.mode == GameMode.PLAYING and key == "v":
            self.threat_view_active = not self.threat_view_active
            return
        result = self.controller.handle_key(key)
        if result.should_quit:
            self.should_quit = True
            return
        if result.engine_changed:
            self._refresh_effect_snapshot()

    def render_frame(self) -> str:
        self._draw_background(self.canvas)
        if self.scene == SCENE_TITLE:
            self._render_title_scene()
        elif self.scene == SCENE_HELP:
            self._render_help_scene()
        elif self.scene == SCENE_SCORES:
            self._render_scores_scene()
        else:
            self._render_game_scene()
        self._present()
        return self.scene

    def _refresh_effect_snapshot(self) -> None:
        state = self.engine.get_render_state()
        if state.effects:
            self.effect_snapshot = state
            self.effect_started_ms = pygame.time.get_ticks()
        else:
            self.effect_snapshot = None
            self.effect_started_ms = None

    def _current_game_state(self) -> RenderState:
        if self.effect_snapshot is None or self.effect_started_ms is None:
            return self.engine.get_render_state()

        elapsed = pygame.time.get_ticks() - self.effect_started_ms
        frame = elapsed // 45
        active = [effect for effect in self.effect_snapshot.effects if effect.frames > frame]
        if active:
            return replace(self.effect_snapshot, effects=active)

        self.engine.clear_effects()
        self.effect_snapshot = None
        self.effect_started_ms = None
        return self.engine.get_render_state()

    def _render_title_scene(self) -> None:
        self._draw_banner("VOIDCAT", "Shipboard Stealth Roguelite")
        menu_rect = pygame.Rect(64, 120, 350, 352)
        scores_rect = pygame.Rect(446, 120, 594, 352)
        self._draw_panel(menu_rect, "AIRLOCK MENU")
        self._draw_panel(scores_rect, "TOP RUNS")

        icon = pygame.transform.scale(self.assets.sprite("player_idle"), (80, 80))
        icon_pos = ((menu_rect.width - icon.get_width()) // 2 + menu_rect.x, menu_rect.y + 38)
        self.canvas.blit(icon, icon_pos)

        lines = [
            "You are not the hero.",
            "You are the ship's last cat.",
            "[N] New Run",
            "[D] Daily Run",
            "[R] Reroll Seed",
            "[H] High Scores",
            "[?] Rules Codex",
            "[F11] Fullscreen",
            "[Q] Quit",
        ]
        self._draw_lines(
            lines,
            pygame.Rect(
                menu_rect.x + 28, menu_rect.y + 132, menu_rect.width - 56, menu_rect.height - 154
            ),
            self.font_small,
            PALETTE["text"],
            line_height=20,
        )
        self._draw_chip_right(
            self.engine.seed_label,
            menu_rect.right - 26,
            menu_rect.y + 12,
            text_color=PALETTE["gold"],
            border_color=PALETTE["gold"],
        )
        self._draw_lines(
            [
                "Daily Run uses today's shared seed.",
                "Reroll Seed builds a fresh personal route.",
            ],
            pygame.Rect(menu_rect.x + 28, menu_rect.bottom - 76, menu_rect.width - 56, 42),
            self.font_small,
            PALETTE["muted"],
            line_height=18,
        )
        self._draw_scores(scores_rect, self.engine.get_scores(), limit=8)

    def _render_scores_scene(self) -> None:
        self._draw_banner("RUN LOG", "Recorded high scores")
        panel = pygame.Rect(88, 110, 928, 510)
        self._draw_panel(panel, "HIGH SCORES")
        scores = self.engine.get_scores()
        lines = []
        if scores:
            for index, entry in enumerate(scores[:10], start=1):
                badge = "DLY" if entry.daily_run else "RUN"
                path = (entry.build_path or "Adaptive").replace(" Route", "")
                lines.append(
                    f"{index:>2}. {entry.score:>5}  F{entry.floor_reached:<2}  "
                    f"{badge:<3}  {path:<9}  {entry.title}"
                )
        else:
            lines.append("No recorded runs yet.")
        lines.extend(["", "Esc closes  ? opens the codex"])
        self._draw_lines(
            lines,
            pygame.Rect(panel.x + 26, panel.y + 56, panel.width - 52, panel.height - 88),
            self.font_body,
            PALETTE["text"],
            line_height=30,
        )

    def _render_help_scene(self) -> None:
        page_index = self._help_page_index()
        page = HELP_PAGES[page_index]
        icon_map = ["player_idle", "dock", "player_idle", "signal", "noise", "stalker"]
        card = pygame.Rect(96, 86, 912, 560)
        shadow = card.move(8, 8)
        pygame.draw.rect(self.canvas, PALETTE["shadow"], shadow, border_radius=18)
        self._draw_panel(card, page[0], dense=True)
        icon = pygame.transform.scale(self.assets.sprite(icon_map[page_index]), (64, 64))
        icon_x = card.x + (card.width - icon.get_width()) // 2
        self.canvas.blit(icon, (icon_x, card.y + 54))
        self._draw_lines(
            page[1:],
            pygame.Rect(card.x + 36, card.y + 136, card.width - 72, card.height - 182),
            self.font_body,
            PALETTE["text"],
            line_height=30,
        )
        footer = (
            f"Page {page_index + 1}/{len(HELP_PAGES)}   Left/Right or Tab to switch   Esc closes"
        )
        self._draw_lines(
            [footer],
            pygame.Rect(card.x + 28, card.bottom - 46, card.width - 56, 24),
            self.font_small,
            PALETTE["muted"],
            line_height=20,
        )

    def _render_game_scene(self) -> None:
        state = self._current_game_state()
        accent = PALETTE["muted"]
        if state.hud.alert_stage.label == "HUNT":
            accent = PALETTE["gold"]
        elif state.hud.alert_stage.label == "SWEEP":
            accent = PALETTE["danger_hot"]
        self._draw_banner(
            "VOIDCAT",
            (
                f"Floor {state.hud.floor}  {state.hud.condition}  "
                f"Alert {state.hud.alert_stage.label} {state.hud.alert}"
            ),
            accent=accent,
        )
        self._draw_chip_right(
            state.hud.seed_label,
            INTERNAL_WIDTH - 46,
            22,
            text_color=PALETTE["gold"],
            border_color=PALETTE["gold"],
        )
        self._draw_map(state)
        self._draw_sidebar(state)
        self._draw_log_strip(state)
        overlay = self._game_overlay(state)
        if overlay:
            self._draw_center_card(*overlay)

    def _draw_banner(
        self,
        title: str,
        subtitle: str,
        *,
        accent: ColorValue = PALETTE["muted"],
    ) -> None:
        title_position = (48, 18)
        self._draw_text(title, self.font_title, PALETTE["danger_hot"], title_position)
        subtitle_x = title_position[0] + self.font_title.size(title)[0] + 24
        self._draw_text(subtitle, self.font_label, accent, (subtitle_x, 36))
        pygame.draw.line(self.canvas, PALETTE["line"], (32, 78), (INTERNAL_WIDTH - 32, 78), 2)

    def _draw_background(self, surface: pygame.Surface) -> None:
        surface.fill(PALETTE["bg"])
        tile = self.assets.sprite("panel_texture")
        for y in range(0, INTERNAL_HEIGHT, tile.get_height()):
            for x in range(0, INTERNAL_WIDTH, tile.get_width()):
                surface.blit(tile, (x, y))

    def _draw_map(self, state: RenderState) -> None:
        self._draw_panel(self.map_panel_rect, "DECK 35x15")
        if self.threat_view_active:
            self._draw_chip_right(
                "Threat View",
                self.map_panel_rect.right - 16,
                self.map_panel_rect.y + 8,
                text_color=PALETTE["danger_hot"],
                border_color=PALETTE["danger_hot"],
            )
        move_active = any(effect.kind == EffectKind.MOVE_TRAIL for effect in state.effects)
        for y, row in enumerate(state.map_rows):
            for x, cell in enumerate(row):
                screen_x = MAP_ORIGIN[0] + x * TILE_SIZE
                screen_y = MAP_ORIGIN[1] + y * TILE_SIZE
                self._draw_cell(cell, screen_x, screen_y, move_active=move_active)
        if self.threat_view_active:
            self._draw_threat_view(state)
        self._draw_enemy_intents(state)
        self._draw_map_markers(state)
        self._redraw_player_cell(state, move_active=move_active)
        self._draw_live_markers()
        self._draw_effects(state.effects)

    def _draw_cell(self, cell: RenderCell, x: int, y: int, *, move_active: bool) -> None:
        name = _sprite_name_for_cell(cell, move_active=move_active)
        if name is None:
            return
        sprite = self.assets.sprite(name)
        self.canvas.blit(sprite, (x, y))
        if cell.color == CellColor.PLAYER_HIDDEN:
            veil = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
            veil.fill((118, 220, 230, 88))
            self.canvas.blit(veil, (x, y))
            pygame.draw.rect(
                self.canvas,
                PALETTE["cyan"],
                pygame.Rect(x + 1, y + 1, TILE_SIZE - 2, TILE_SIZE - 2),
                1,
                3,
            )
        if cell.color == CellColor.FOG:
            fog = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
            fog.fill(PALETTE["fog"])
            self.canvas.blit(fog, (x, y))
        if cell.dim and cell.color != CellColor.FOG:
            shade = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 110))
            self.canvas.blit(shade, (x, y))
        if cell.flash and (pygame.time.get_ticks() // 90) % 2 == 0:
            flash = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
            flash.fill((255, 120, 110, 90))
            self.canvas.blit(flash, (x, y))

    def _draw_effects(self, effects: list[RenderEffect]) -> None:
        for effect in effects:
            sprite_name = _sprite_name_for_effect(effect)
            sprite = self.assets.sprite(sprite_name)
            for point in effect.points:
                x = MAP_ORIGIN[0] + point.x * TILE_SIZE
                y = MAP_ORIGIN[1] + point.y * TILE_SIZE
                self.canvas.blit(sprite, (x, y))
        if any(effect.kind == EffectKind.ALERT_BAR for effect in effects):
            flash = pygame.Surface((self.sidebar_rect.width - 24, 12), pygame.SRCALPHA)
            flash.fill((100, 230, 240, 120))
            self.canvas.blit(flash, (self.sidebar_rect.x + 12, self.sidebar_rect.y + 72))

    def _draw_live_markers(self) -> None:
        for path in self._preview_knock_paths():
            for point in path[:-1]:
                self._draw_tile_glow(point, (235, 177, 86, 42), PALETTE["noise"])
            self._draw_tile_glow(path[-1], (235, 177, 86, 86), PALETTE["noise"])
        for point in self._preview_pounce_targets():
            self._draw_tile_glow(point, (241, 82, 70, 78), PALETTE["danger_hot"])
        if self.engine.decoy_target is not None and self.engine.decoy_turns > 0:
            pulse = 90 + ((pygame.time.get_ticks() // 90) % 2) * 60
            self._draw_tile_glow(self.engine.decoy_target, (235, 177, 86, pulse), PALETTE["gold"])

    def _draw_map_markers(self, state: RenderState) -> None:
        pulse_on = (pygame.time.get_ticks() // 180) % 2 == 0
        for marker, frame, accent in self._layout_marker_labels(
            state.markers, avoid_points=[self.engine.player.position]
        ):
            alpha = 92 if marker.pulse and pulse_on else 48
            self._draw_tile_glow(marker.point, (*accent, alpha), accent)
            pygame.draw.rect(self.canvas, PALETTE["panel_dim"], frame, border_radius=6)
            pygame.draw.rect(self.canvas, accent, frame, 1, border_radius=6)
            self._draw_text(marker.label, self.font_small, accent, (frame.x + 4, frame.y + 2))

    def _draw_enemy_intents(self, state: RenderState) -> None:
        for intent in state.enemy_intents:
            color = _intent_color(intent.alert, intent.attack)
            start = self._tile_center(intent.origin)
            end = self._tile_center(intent.destination)
            if start != end:
                pygame.draw.line(self.canvas, color, start, end, 2)
            fill_alpha = 112 if intent.attack else 56
            self._draw_tile_glow(intent.destination, (*color, fill_alpha), color)

    def _draw_threat_view(self, state: RenderState) -> None:
        for point in state.threat_cells:
            fill = (241, 82, 70, 58)
            border = PALETTE["danger"]
            if point == self.engine.player.position:
                fill = (255, 135, 124, 90)
                border = PALETTE["danger_hot"]
            self._draw_tile_glow(point, fill, border)

    def _tile_center(self, point: Point) -> tuple[int, int]:
        return (
            MAP_ORIGIN[0] + point.x * TILE_SIZE + TILE_SIZE // 2,
            MAP_ORIGIN[1] + point.y * TILE_SIZE + TILE_SIZE // 2,
        )

    def _tile_rect(self, point: Point) -> pygame.Rect:
        return pygame.Rect(
            MAP_ORIGIN[0] + point.x * TILE_SIZE,
            MAP_ORIGIN[1] + point.y * TILE_SIZE,
            TILE_SIZE,
            TILE_SIZE,
        )

    def _help_page_index(self) -> int:
        return self.help_page_index % len(HELP_PAGES)

    def _redraw_player_cell(self, state: RenderState, *, move_active: bool) -> None:
        if self.engine.floor is None:
            return
        point = self.engine.player.position
        if not self.engine.floor.in_bounds(point):
            return
        cell = state.map_rows[point.y][point.x]
        self._draw_cell(
            cell, self._tile_rect(point).x, self._tile_rect(point).y, move_active=move_active
        )

    def _layout_marker_labels(
        self,
        markers: list[MapMarker],
        *,
        avoid_points: list[Point] | None = None,
    ) -> list[tuple[MapMarker, pygame.Rect, RGBColor]]:
        layouts: list[tuple[MapMarker, pygame.Rect, RGBColor]] = []
        blocked = [self._tile_rect(point).inflate(4, 4) for point in (avoid_points or [])]
        sorted_markers = sorted(
            markers, key=lambda marker: (not marker.pulse, marker.point.y, marker.point.x)
        )
        for marker in sorted_markers:
            accent = _accent_for_cell(marker.color)
            width, height = self.font_small.size(marker.label)
            frame_size = (width + 8, height + 4)
            for frame in self._marker_label_candidates(marker.point, frame_size):
                if any(frame.colliderect(other) for other in blocked):
                    continue
                layouts.append((marker, frame, accent))
                blocked.append(frame.inflate(4, 4))
                break
        return layouts

    def _marker_label_candidates(
        self,
        point: Point,
        frame_size: tuple[int, int],
    ) -> list[pygame.Rect]:
        frame_width, frame_height = frame_size
        tile = self._tile_rect(point)
        bounds = self.map_panel_rect.inflate(-12, -12)
        right_x = tile.right + 4
        left_x = tile.left - frame_width - 4
        above_y = tile.top - frame_height - 2
        below_y = tile.bottom + 2
        middle_y = tile.centery - frame_height // 2
        bases = [
            (right_x, above_y),
            (right_x, below_y),
            (left_x, above_y),
            (left_x, below_y),
            (right_x, middle_y),
            (left_x, middle_y),
        ]
        offsets = [0, 18, -18, 36, -36]
        candidates: list[pygame.Rect] = []
        for base_x, base_y in bases:
            for offset in offsets:
                frame = pygame.Rect(base_x, base_y + offset, frame_width, frame_height)
                frame = self._clamp_rect(frame, bounds)
                if frame not in candidates:
                    candidates.append(frame)
        return candidates

    def _clamp_rect(self, rect: pygame.Rect, bounds: pygame.Rect) -> pygame.Rect:
        clamped = rect.copy()
        if clamped.left < bounds.left:
            clamped.left = bounds.left
        if clamped.right > bounds.right:
            clamped.right = bounds.right
        if clamped.top < bounds.top:
            clamped.top = bounds.top
        if clamped.bottom > bounds.bottom:
            clamped.bottom = bounds.bottom
        return clamped

    def _draw_tile_glow(
        self,
        point: Point,
        fill_color: RGBAColor,
        border_color: ColorValue,
    ) -> None:
        x = MAP_ORIGIN[0] + point.x * TILE_SIZE
        y = MAP_ORIGIN[1] + point.y * TILE_SIZE
        glow = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        glow.fill(fill_color)
        self.canvas.blit(glow, (x, y))
        pygame.draw.rect(
            self.canvas, border_color, pygame.Rect(x + 1, y + 1, TILE_SIZE - 2, TILE_SIZE - 2), 1, 3
        )

    def _preview_knock_paths(self) -> list[list[Point]]:
        if (
            self.pending_action != ActionType.KNOCK
            or self.engine.floor is None
            or self.engine.mode != GameMode.PLAYING
        ):
            return []
        return list(self.engine.preview_knock_paths().values())

    def _preview_pounce_targets(self) -> list[Point]:
        if (
            self.pending_action != ActionType.POUNCE
            or self.engine.floor is None
            or self.engine.mode != GameMode.PLAYING
        ):
            return []
        return list(dict.fromkeys(self.engine.preview_pounce_targets().values()))

    def _pounce_target(self, direction: str) -> Point | None:
        return self.engine.preview_pounce_target(direction)

    def _draw_sidebar(self, state: RenderState) -> None:
        self._draw_panel(self.sidebar_rect, "TACTICAL HUD", dense=True)
        top = self.sidebar_rect.y + 28
        self._draw_text(
            f"Relays {state.hud.relays}",
            self.font_label,
            PALETTE["text"],
            (self.sidebar_rect.x + 20, top),
        )
        self._draw_text(
            f"Score {state.hud.score}",
            self.font_small,
            PALETTE["muted"],
            (self.sidebar_rect.x + 20, top + 28),
        )
        self._draw_chip(
            state.hud.condition,
            self.sidebar_rect.x + 20,
            top + 50,
            text_color=PALETTE["gold"],
            border_color=PALETTE["gold"],
        )
        self._draw_chip(
            state.hud.seed_label,
            self.sidebar_rect.x + 20,
            top + 78,
            text_color=PALETTE["cyan"],
            border_color=PALETTE["cyan"],
        )
        self._draw_chip(
            state.hud.build_path,
            self.sidebar_rect.x + 20,
            top + 106,
            text_color=PALETTE["power"],
            border_color=PALETTE["power"],
        )
        bar_top = top + 140
        for index, bar in enumerate(state.status_bars):
            self._draw_status_bar(
                bar.label,
                bar.value,
                bar.maximum,
                bar.color,
                self.sidebar_rect.x + 20,
                bar_top + index * 34,
                self.sidebar_rect.width - 40,
            )
        chart_top = bar_top + len(state.status_bars) * 34 + 14
        self._draw_text(
            "Noise Trace",
            self.font_small,
            PALETTE["muted"],
            (self.sidebar_rect.x + 20, chart_top),
        )
        self._draw_noise_chart(
            state.noise_history,
            self.sidebar_rect.x + 20,
            chart_top + 20,
            self.sidebar_rect.width - 40,
            40,
        )
        info_top = chart_top + 72
        line_y = info_top
        for section in (
            state.sidebar.objective,
            state.sidebar.tools,
            state.sidebar.guidance,
            state.sidebar.modules,
        ):
            self._draw_text(
                section.title.upper(),
                self.font_small,
                PALETTE["cyan"],
                (self.sidebar_rect.x + 20, line_y),
            )
            line_y += 16
            line_y += (
                self._draw_lines(
                    section.lines[:3],
                    pygame.Rect(
                        self.sidebar_rect.x + 20,
                        line_y,
                        self.sidebar_rect.width - 40,
                        self.sidebar_rect.bottom - line_y - 42,
                    ),
                    self.font_small,
                    PALETTE["text"],
                    line_height=16,
                )
                * 16
            )
            line_y += 6
            if line_y > self.sidebar_rect.bottom - 54:
                break

        if self.engine.floor_number == 1 and self.engine.mode == GameMode.PLAYING:
            hint = "Restore relays, then run for the dock."
            if self.engine.floor and self.engine.floor.objective.complete:
                hint = "Objective clear. Dock out to cash the floor."
            self._draw_lines(
                [hint],
                pygame.Rect(
                    self.sidebar_rect.x + 20,
                    self.sidebar_rect.bottom - 42,
                    self.sidebar_rect.width - 40,
                    28,
                ),
                self.font_small,
                PALETTE["gold"],
                line_height=16,
            )

    def _draw_status_bar(
        self,
        label: str,
        value: int,
        maximum: int,
        color_name: BarColor,
        x: int,
        y: int,
        width: int,
    ) -> None:
        label_text = f"{label} {value}/{maximum}"
        self._draw_text(label_text, self.font_small, PALETTE["text"], (x, y))
        bar_rect = pygame.Rect(x, y + 16, width, 12)
        pygame.draw.rect(self.canvas, (12, 22, 30), bar_rect, border_radius=5)
        fill = (
            0
            if maximum <= 0
            else max(0, min(bar_rect.width, int(bar_rect.width * value / maximum)))
        )
        if fill:
            fill_rect = pygame.Rect(bar_rect.x, bar_rect.y, fill, bar_rect.height)
            pygame.draw.rect(self.canvas, _bar_color(color_name), fill_rect, border_radius=5)
        pygame.draw.rect(self.canvas, PALETTE["steel"], bar_rect, 1, border_radius=5)

    def _draw_noise_chart(
        self, history: list[int], x: int, y: int, width: int, height: int
    ) -> None:
        chart_rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(self.canvas, (9, 14, 20), chart_rect, border_radius=8)
        pygame.draw.rect(self.canvas, PALETTE["steel"], chart_rect, 1, border_radius=8)
        if not history:
            return
        column_gap = 2
        column_width = max(4, (width - column_gap * (len(history) - 1)) // len(history))
        for index, value in enumerate(history):
            bar_height = 0 if value <= 0 else int((height - 8) * min(1.0, value / 9))
            left = x + index * (column_width + column_gap)
            rect = pygame.Rect(left, y + height - 4 - bar_height, column_width, bar_height)
            pygame.draw.rect(self.canvas, PALETTE["noise"], rect, border_radius=3)

    def _draw_log_strip(self, state: RenderState) -> None:
        self._draw_panel(self.log_rect, "EVENT FEED", dense=True)
        lines = (
            state.log_lines[-MAX_LOG_LINES:]
            if state.log_lines
            else ["No new movement in the vents."]
        )
        self._draw_lines(
            lines,
            pygame.Rect(
                self.log_rect.x + 22,
                self.log_rect.y + 52,
                self.log_rect.width - 44,
                self.log_rect.height - 96,
            ),
            self.font_body,
            PALETTE["text"],
            line_height=24,
        )
        self._draw_lines(
            [state.footer],
            pygame.Rect(
                self.log_rect.x + 22,
                self.log_rect.bottom - 38,
                self.log_rect.width - 44,
                20,
            ),
            self.font_small,
            PALETTE["muted"],
            line_height=18,
        )

    def _game_overlay(self, state: RenderState) -> tuple[str, list[str]] | None:
        overlay_kind = self.controller.current_overlay()
        if overlay_kind == OverlayKind.QUIT:
            return ("Quit Current Session?", ["Press Y to quit or N to stay in the ducts."])
        if overlay_kind == OverlayKind.KNOCK:
            return (
                "Aim Knock",
                [
                    "Noise +5 at the farthest open tile in that direction.",
                    "The decoy stays live for two enemy phases and drags patrols off your route.",
                    "Use W A S D or arrows. Esc cancels.",
                ],
            )
        if overlay_kind == OverlayKind.POUNCE:
            return (
                "Aim Pounce",
                [
                    "Leap 1-2 tiles. Costs extra power, makes noise, and cannot land on enemies.",
                    "Use it to steal distance or loot, not to dive blind into heat and vision.",
                    "Use W A S D or arrows. Esc cancels.",
                ],
            )
        if overlay_kind == OverlayKind.DOCK:
            lines = self.engine.summary_lines()
            return (lines[0], lines[1:])
        if overlay_kind == OverlayKind.GAME_OVER:
            return ("Run Over", self.engine.summary_lines())
        return None

    def _draw_center_card(self, title: str, lines: list[str]) -> None:
        width = 620
        wrapped_lines = self._wrap_text_lines(lines, self.font_body, width - 56)
        height = max(180, min(INTERNAL_HEIGHT - 120, 92 + len(wrapped_lines) * 26))
        rect = pygame.Rect(
            (INTERNAL_WIDTH - width) // 2, (INTERNAL_HEIGHT - height) // 2, width, height
        )
        shadow = rect.move(10, 10)
        pygame.draw.rect(self.canvas, PALETTE["shadow"], shadow, border_radius=18)
        self._draw_panel(rect, title, dense=True)
        self._draw_lines(
            wrapped_lines,
            pygame.Rect(rect.x + 28, rect.y + 54, rect.width - 56, rect.height - 82),
            self.font_body,
            PALETTE["text"],
            line_height=26,
        )

    def _draw_panel(self, rect: pygame.Rect, title: str, *, dense: bool = False) -> None:
        panel_fill = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        panel_fill.fill(PALETTE["panel_dim"] if dense else PALETTE["panel"])
        self.canvas.blit(panel_fill, rect.topleft)
        tile = self.assets.sprite("panel_texture")
        for y in range(rect.y + 2, rect.bottom - 2, tile.get_height()):
            for x in range(rect.x + 2, rect.right - 2, tile.get_width()):
                self.canvas.blit(tile, (x, y))
        self._draw_frame(rect)
        self._draw_text(title, self.font_label, PALETTE["cyan"], (rect.x + 18, rect.y + 8))

    def _draw_frame(self, rect: pygame.Rect) -> None:
        tl = self.assets.sprite("frame_tl")
        tr = self.assets.sprite("frame_tr")
        bl = self.assets.sprite("frame_bl")
        br = self.assets.sprite("frame_br")
        h = self.assets.sprite("frame_h")
        v = self.assets.sprite("frame_v")
        step = self.assets.tile_size
        self.canvas.blit(tl, rect.topleft)
        self.canvas.blit(tr, (rect.right - step, rect.y))
        self.canvas.blit(bl, (rect.x, rect.bottom - step))
        self.canvas.blit(br, (rect.right - step, rect.bottom - step))
        for x in range(rect.x + step, rect.right - step, step):
            self.canvas.blit(h, (x, rect.y))
            self.canvas.blit(h, (x, rect.bottom - step))
        for y in range(rect.y + step, rect.bottom - step, step):
            self.canvas.blit(v, (rect.x, y))
            self.canvas.blit(v, (rect.right - step, y))

    def _draw_scores(self, rect: pygame.Rect, scores: list[ScoreEntry], *, limit: int) -> None:
        lines = []
        if scores:
            for index, entry in enumerate(scores[:limit], start=1):
                badge = "DAILY" if entry.daily_run else "RUN"
                path = (entry.build_path or "Adaptive").replace(" Route", "")
                lines.append(
                    f"{index}. {entry.score:>5}  F{entry.floor_reached}  "
                    f"{badge}  {path}  {entry.title}"
                )
        else:
            lines.append("No high scores yet.")
        self._draw_lines(
            lines,
            pygame.Rect(rect.x + 24, rect.y + 54, rect.width - 48, rect.height - 78),
            self.font_body,
            PALETTE["text"],
            line_height=28,
        )

    def _draw_lines(
        self,
        lines: list[str],
        rect: pygame.Rect,
        font: pygame.font.Font,
        color: ColorValue,
        *,
        line_height: int,
    ) -> int:
        wrapped_lines = self._wrap_text_lines(lines, font, rect.width)
        y = rect.y
        drawn = 0
        for line in wrapped_lines:
            if y + line_height > rect.bottom + 1:
                break
            self._draw_text(line, font, color, (rect.x, y))
            y += line_height
            drawn += 1
        return drawn

    def _wrap_text_lines(
        self, lines: list[str], font: pygame.font.Font, max_width: int
    ) -> list[str]:
        wrapped: list[str] = []
        for line in lines:
            if not line:
                wrapped.append("")
                continue
            current = ""
            line_wrapped = False
            for word in line.split(" "):
                candidate = word if not current else f"{current} {word}"
                if current and font.size(candidate)[0] > max_width:
                    wrapped.append(current)
                    line_wrapped = True
                    current = ""
                if font.size(word)[0] <= max_width:
                    current = word if not current else f"{current} {word}"
                    continue
                if current:
                    wrapped.append(current)
                    line_wrapped = True
                    current = ""
                remainder = word
                while remainder:
                    split = 1
                    while (
                        split < len(remainder) and font.size(remainder[: split + 1])[0] <= max_width
                    ):
                        split += 1
                    wrapped.append(remainder[:split])
                    line_wrapped = True
                    remainder = remainder[split:]
            if current or not line_wrapped:
                wrapped.append(current)
        return wrapped

    def _draw_text(
        self,
        text: str,
        font: pygame.font.Font,
        color: ColorValue,
        position: tuple[int, int],
    ) -> None:
        surface = font.render(text, True, color)
        self.canvas.blit(surface, position)

    def _draw_chip(
        self,
        text: str,
        x: int,
        y: int,
        *,
        text_color: ColorValue,
        border_color: ColorValue,
    ) -> pygame.Rect:
        surface = self.font_small.render(text, True, text_color)
        rect = surface.get_rect(topleft=(x + 10, y + 4))
        frame = rect.inflate(20, 8)
        pygame.draw.rect(self.canvas, PALETTE["panel_dim"], frame, border_radius=8)
        pygame.draw.rect(self.canvas, border_color, frame, 1, border_radius=8)
        self.canvas.blit(surface, rect)
        return frame

    def _draw_chip_right(
        self,
        text: str,
        right: int,
        y: int,
        *,
        text_color: ColorValue,
        border_color: ColorValue,
    ) -> pygame.Rect:
        surface = self.font_small.render(text, True, text_color)
        frame = surface.get_rect()
        frame.width += 20
        frame.height += 8
        frame.top = y
        frame.right = right
        pygame.draw.rect(self.canvas, PALETTE["panel_dim"], frame, border_radius=8)
        pygame.draw.rect(self.canvas, border_color, frame, 1, border_radius=8)
        self.canvas.blit(surface, (frame.x + 10, frame.y + 4))
        return frame

    def _present(self) -> None:
        window_width, window_height = self.window.get_size()
        scale = min(window_width / INTERNAL_WIDTH, window_height / INTERNAL_HEIGHT)
        scaled_size = (
            max(1, int(INTERNAL_WIDTH * scale)),
            max(1, int(INTERNAL_HEIGHT * scale)),
        )
        if scaled_size == INTERNAL_SIZE:
            scaled = self.canvas
        elif scale >= 1:
            scaled = pygame.transform.scale(self.canvas, scaled_size)
        else:
            scaled = pygame.transform.smoothscale(self.canvas, scaled_size)
        self.window.fill((0, 0, 0))
        offset = ((window_width - scaled_size[0]) // 2, (window_height - scaled_size[1]) // 2)
        self.window.blit(scaled, offset)
        pygame.display.flip()


def _key_from_event(event: pygame.event.Event) -> str | None:
    keymap = {
        pygame.K_UP: "KEY_UP",
        pygame.K_DOWN: "KEY_DOWN",
        pygame.K_LEFT: "KEY_LEFT",
        pygame.K_RIGHT: "KEY_RIGHT",
        pygame.K_RETURN: "enter",
        pygame.K_ESCAPE: "esc",
        pygame.K_TAB: "tab",
        pygame.K_SPACE: " ",
        pygame.K_F11: "f11",
        pygame.K_SLASH: "?" if bool(getattr(event, "mod", 0) & pygame.KMOD_SHIFT) else "/",
    }
    if event.key in keymap:
        return keymap[event.key]
    if event.unicode:
        return str(event.unicode).lower()
    return None


def _is_direction_key(key: str) -> bool:
    return key in {"w", "a", "s", "d", "KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT"}


def _sprite_name_for_cell(cell: RenderCell, *, move_active: bool) -> str | None:
    if cell.color == CellColor.VOID:
        return None
    if cell.color in {CellColor.PLAYER, CellColor.PLAYER_HIDDEN}:
        return "player_walk" if move_active else "player_idle"
    if cell.char == "▓":
        return "wall"
    if cell.char == "·":
        return "floor"
    if cell.char == "⌂":
        return "dock"
    if cell.char == "◇":
        return "relay"
    if cell.char == "◆" and cell.color == CellColor.RELAY_RESTORED:
        return "relay_restored"
    if cell.char == "≈":
        return "heat"
    if cell.char == "▣":
        return "battery"
    if cell.char == "✦":
        return "scrap"
    if cell.char == "◎":
        return "signal"
    if cell.char == "◌":
        return "noise"
    if cell.char == "◍":
        return "crawler"
    if cell.char == "▲" and cell.color in {
        CellColor.ENEMY_RED,
        CellColor.ENEMY_RED_COOL,
        CellColor.ENEMY_HOT,
    }:
        return "stalker"
    if cell.char == "◆" and cell.color in {
        CellColor.ENEMY_RED,
        CellColor.ENEMY_RED_COOL,
        CellColor.ENEMY_HOT,
    }:
        return "mimic_reveal"
    return "floor"


def _sprite_name_for_effect(effect: RenderEffect) -> str:
    mapping = {
        EffectKind.MOVE_TRAIL: "noise",
        EffectKind.KNOCK: "noise",
        EffectKind.KNOCK_FLASH: "signal",
        EffectKind.HISS: "alert_flash",
        EffectKind.HIDE: "noise",
        EffectKind.RELAY: "relay_restored",
        EffectKind.MIMIC: "mimic_reveal",
        EffectKind.ENEMY_SPOT: "alert_flash",
    }
    return mapping.get(effect.kind, "noise")


def _bar_color(name: BarColor) -> tuple[int, int, int]:
    return BAR_COLORS.get(name, (31, 54, 70))


def _accent_for_cell(color: CellColor) -> RGBColor:
    mapping = {
        CellColor.DOCK: PALETTE["cyan"],
        CellColor.RELAY: PALETTE["power"],
        CellColor.BATTERY: PALETTE["power"],
        CellColor.SCRAP: PALETTE["gold"],
        CellColor.SIGNAL: PALETTE["noise"],
        CellColor.ENEMY_RED: PALETTE["danger_hot"],
        CellColor.ENEMY_RED_COOL: PALETTE["cyan"],
    }
    return cast(RGBColor, mapping.get(color, PALETTE["muted"]))


def _intent_color(alert: AlertState, attack: bool) -> RGBColor:
    if attack:
        return cast(RGBColor, PALETTE["danger_hot"])
    mapping = {
        "DORMANT": PALETTE["muted"],
        "INVESTIGATING": PALETTE["noise"],
        "CHASING": PALETTE["danger"],
        "SCARED": PALETTE["cyan"],
    }
    label = getattr(alert, "name", "DORMANT")
    return cast(RGBColor, mapping.get(label, PALETTE["muted"]))
