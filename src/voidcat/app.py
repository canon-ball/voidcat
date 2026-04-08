from __future__ import annotations

import curses
from dataclasses import replace

from .controller import GameController, OverlayKind, Scene
from .engine import GameEngine
from .help import help_overlay
from .models import CellColor, OverlayState
from .ui import (
    CursesWindow,
    draw_high_scores,
    draw_modal,
    draw_title,
    ensure_terminal_size,
    init_colors,
    render_game,
)


def main() -> None:
    curses.wrapper(_run)


def _run(stdscr: CursesWindow) -> None:
    curses.curs_set(0)
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    colors = init_colors()
    engine = GameEngine()
    controller = GameController(engine)

    while True:
        if not ensure_terminal_size(stdscr):
            stdscr.getch()
            continue

        _render_scene(stdscr, controller, colors)
        key = _read_key(stdscr)
        result = controller.handle_key(key)
        if result.should_quit:
            return
        if result.engine_changed:
            _animate_effects(
                stdscr,
                engine,
                colors,
                title_suffix=_title_suffix_for_overlay(controller.current_overlay()),
            )


def _render_scene(
    stdscr: CursesWindow,
    controller: GameController,
    colors: dict[CellColor, int],
) -> None:
    if controller.scene == Scene.TITLE:
        draw_title(stdscr, controller.engine.get_scores())
        return
    if controller.scene == Scene.SCORES:
        draw_high_scores(stdscr, controller.engine.get_scores())
        return
    if controller.scene == Scene.HELP:
        overlay = help_overlay(controller.help_page_index)
        if controller.return_scene == Scene.GAME:
            render_game(
                stdscr,
                controller.engine.get_render_state(overlay),
                colors,
                title_suffix=" | HELP",
            )
        elif controller.return_scene == Scene.SCORES:
            draw_high_scores(stdscr, controller.engine.get_scores())
            draw_modal(stdscr, overlay)
            stdscr.refresh()
        else:
            draw_title(stdscr, controller.engine.get_scores())
            draw_modal(stdscr, overlay)
            stdscr.refresh()
        return

    game_overlay = _game_overlay(controller)
    render_game(
        stdscr,
        controller.engine.get_render_state(game_overlay),
        colors,
        title_suffix=_title_suffix_for_overlay(controller.current_overlay()),
    )


def _game_overlay(controller: GameController) -> OverlayState | None:
    overlay_kind = controller.current_overlay()
    if overlay_kind == OverlayKind.QUIT:
        return OverlayState(
            title="Quit the current session?", lines=["", "Press Y to quit or N to stay."]
        )
    if overlay_kind == OverlayKind.KNOCK:
        return OverlayState(
            title="Choose a direction for the knock.",
            lines=[
                "",
                "Knock costs 1 power and makes 5 noise at the farthest open tile.",
                "The decoy stays live for two enemy phases.",
                "Use it before crossing an open lane. Esc cancels.",
            ],
        )
    if overlay_kind == OverlayKind.POUNCE:
        return OverlayState(
            title="Choose a direction for the pounce.",
            lines=[
                "",
                "Pounce leaps 1-2 tiles, costs extra power, and makes noise.",
                "Use it to burst through a choke or steal distance quickly.",
                "It cannot land on enemies. Esc cancels.",
            ],
        )
    if overlay_kind in {OverlayKind.DOCK, OverlayKind.GAME_OVER}:
        lines = controller.engine.summary_lines()
        if not lines:
            return None
        return OverlayState(title=lines[0], lines=lines[1:])
    return None


def _read_key(stdscr: CursesWindow) -> str:
    code = stdscr.getch()
    if code in {10, 13}:
        return "enter"
    if code == 9:
        return "tab"
    if code == 27:
        return "esc"
    if code == ord("?"):
        return "?"
    if 0 <= code < 256:
        return chr(code).lower()
    return curses.keyname(code).decode("ascii", "ignore")


def _title_suffix_for_overlay(overlay_kind: OverlayKind) -> str:
    if overlay_kind == OverlayKind.DOCK:
        return " | DOCK"
    if overlay_kind == OverlayKind.GAME_OVER:
        return " | GAME OVER"
    if overlay_kind == OverlayKind.QUIT:
        return " | QUIT"
    if overlay_kind == OverlayKind.KNOCK:
        return " | KNOCK"
    if overlay_kind == OverlayKind.POUNCE:
        return " | POUNCE"
    return ""


def _animate_effects(
    stdscr: CursesWindow,
    engine: GameEngine,
    colors: dict[CellColor, int],
    *,
    title_suffix: str = "",
) -> None:
    state = engine.get_render_state()
    if not state.effects:
        return
    max_frames = min(3, max(effect.frames for effect in state.effects))
    for frame in range(max_frames):
        active = [effect for effect in state.effects if effect.frames > frame]
        render_game(stdscr, replace(state, effects=active), colors, title_suffix=title_suffix)
        curses.napms(45)
    engine.clear_effects()
