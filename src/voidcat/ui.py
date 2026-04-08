from __future__ import annotations

import curses
from typing import Protocol

from .models import (
    MAX_NOISE,
    MIN_TERM_HEIGHT,
    MIN_TERM_WIDTH,
    SIDEBAR_WIDTH,
    CellColor,
    EffectKind,
    OverlayState,
    RenderCell,
    RenderState,
    ScoreEntry,
    StatusBar,
)


class CursesWindow(Protocol):
    def getmaxyx(self) -> tuple[int, int]: ...

    def erase(self) -> None: ...

    def refresh(self) -> None: ...

    def addnstr(self, y: int, x: int, text: str, limit: int, attrs: int = 0) -> None: ...

    def addstr(self, y: int, x: int, text: str, attrs: int = 0) -> None: ...

    def getch(self) -> int: ...

    def keypad(self, flag: bool) -> None: ...


COLOR_IDS = {
    CellColor.VOID: 0,
    CellColor.WALL: 1,
    CellColor.FLOOR: 2,
    CellColor.FOG: 3,
    CellColor.PLAYER: 4,
    CellColor.PLAYER_HIDDEN: 5,
    CellColor.DOCK: 6,
    CellColor.RELAY: 7,
    CellColor.RELAY_RESTORED: 8,
    CellColor.BATTERY: 9,
    CellColor.SCRAP: 10,
    CellColor.SIGNAL: 11,
    CellColor.HEAT: 12,
    CellColor.ENEMY_RED: 13,
    CellColor.ENEMY_RED_COOL: 14,
    CellColor.ENEMY_HOT: 15,
    CellColor.HEARD: 16,
    CellColor.BORDER: 17,
    CellColor.TITLE: 18,
    CellColor.BAR_POWER: 19,
    CellColor.BAR_NOISE: 20,
    CellColor.BAR_ALERT: 21,
    CellColor.RELAY_PULSE: 22,
    CellColor.NOISE: 23,
    CellColor.NOISE_FLASH: 24,
    CellColor.TRAIL: 25,
    CellColor.BACKDROP: 26,
    CellColor.PANEL_FILL: 27,
}


def init_colors() -> dict[CellColor, int]:
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_IDS[CellColor.WALL], curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_IDS[CellColor.FLOOR], curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_IDS[CellColor.FOG], curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_IDS[CellColor.PLAYER], curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_IDS[CellColor.PLAYER_HIDDEN], curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_IDS[CellColor.DOCK], curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_IDS[CellColor.RELAY], curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_IDS[CellColor.RELAY_RESTORED], curses.COLOR_WHITE, curses.COLOR_CYAN)
    curses.init_pair(COLOR_IDS[CellColor.BATTERY], curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_IDS[CellColor.SCRAP], curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_IDS[CellColor.SIGNAL], curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_IDS[CellColor.HEAT], curses.COLOR_RED, -1)
    curses.init_pair(COLOR_IDS[CellColor.ENEMY_RED], curses.COLOR_RED, -1)
    curses.init_pair(COLOR_IDS[CellColor.ENEMY_RED_COOL], curses.COLOR_RED, -1)
    curses.init_pair(COLOR_IDS[CellColor.ENEMY_HOT], curses.COLOR_RED, -1)
    curses.init_pair(COLOR_IDS[CellColor.HEARD], curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_IDS[CellColor.BORDER], curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_IDS[CellColor.TITLE], curses.COLOR_RED, -1)
    curses.init_pair(COLOR_IDS[CellColor.BAR_POWER], curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_IDS[CellColor.BAR_NOISE], curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_IDS[CellColor.BAR_ALERT], curses.COLOR_RED, -1)
    curses.init_pair(COLOR_IDS[CellColor.RELAY_PULSE], curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_IDS[CellColor.NOISE], curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_IDS[CellColor.NOISE_FLASH], curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_IDS[CellColor.TRAIL], curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_IDS[CellColor.BACKDROP], curses.COLOR_BLACK, curses.COLOR_BLACK)
    curses.init_pair(COLOR_IDS[CellColor.PANEL_FILL], curses.COLOR_WHITE, curses.COLOR_BLACK)
    return COLOR_IDS


def ensure_terminal_size(stdscr: CursesWindow) -> bool:
    height, width = stdscr.getmaxyx()
    if width >= MIN_TERM_WIDTH and height >= MIN_TERM_HEIGHT:
        return True
    stdscr.erase()
    lines = [
        "VOIDCAT needs a larger terminal.",
        f"Current size: {width}x{height}",
        f"Minimum size: {MIN_TERM_WIDTH}x{MIN_TERM_HEIGHT}",
        "Resize the window, then press any key.",
    ]
    draw_centered_block(stdscr, lines)
    stdscr.refresh()
    return False


def render_game(
    stdscr: CursesWindow,
    state: RenderState,
    colors: dict[CellColor, int],
    *,
    title_suffix: str = "",
) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    map_width = len(state.map_rows[0]) if state.map_rows else 0
    map_height = len(state.map_rows)
    map_panel_width = map_width + 2
    map_panel_height = map_height + 2
    gap = 2
    content_width = map_panel_width + gap + SIDEBAR_WIDTH
    left = max(2, (width - content_width) // 2)
    map_panel_left = left
    sidebar_left = map_panel_left + map_panel_width + gap
    top = 2

    header = (
        f"▓▒░ VOIDCAT{title_suffix} ░▒▓  SCORE {state.hud.score}  "
        f"ALERT {state.hud.alert_stage.label} {state.hud.alert}"
    )
    stdscr.addnstr(
        0, 2, header, width - 4, curses.A_BOLD | curses.color_pair(colors[CellColor.TITLE])
    )
    stdscr.addnstr(
        1, 2, "═" * max(0, width - 4), width - 4, curses.color_pair(colors[CellColor.BORDER])
    )

    map_top, map_left, _, _ = draw_panel(
        stdscr,
        top,
        map_panel_left,
        map_panel_width,
        map_panel_height,
        title="DECK",
    )

    for y, row in enumerate(state.map_rows):
        for x, cell in enumerate(row):
            stdscr.addstr(map_top + y, map_left + x, cell.char, _cell_attrs(cell, colors))

    draw_effects(stdscr, map_top, map_left, state, colors)
    draw_sidebar(stdscr, top, sidebar_left, SIDEBAR_WIDTH, height - top - 2, state, colors)

    log_top = top + map_panel_height + 1
    log_height = max(4, height - log_top - 1)
    draw_log_panel(stdscr, log_top, map_panel_left, map_panel_width, log_height, state.log_lines)

    stdscr.addnstr(height - 1, 2, state.footer, width - 4, curses.A_DIM)

    if state.overlay.visible:
        draw_modal(stdscr, state.overlay)

    stdscr.refresh()


def draw_title(stdscr: CursesWindow, scores: list[ScoreEntry]) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    banner = "▓▒░ VOIDCAT ░▒▓"
    stdscr.addnstr(
        max(1, height // 7),
        max(0, (width - len(banner)) // 2),
        banner,
        len(banner),
        curses.A_BOLD | curses.color_pair(COLOR_IDS[CellColor.TITLE]),
    )

    title_lines = [
        "You are not the hero. You are the ship's last cat.",
        "",
        "Slip through dying vents, restore the ship, and vanish before the hunt closes in.",
        "",
        "[N]ew Run   [H]igh Scores   [?]Codex   [Q]uit",
    ]
    panel_width = 62
    panel_height = len(title_lines) + 2
    top = max(3, height // 5)
    left = max(2, (width - panel_width) // 2)
    inner_top, inner_left, inner_width, _ = draw_panel(
        stdscr, top, left, panel_width, panel_height, title="ALARM SHIP"
    )
    for index, line in enumerate(title_lines):
        stdscr.addnstr(
            inner_top + index, inner_left, line, inner_width, curses.A_BOLD if index == 0 else 0
        )

    score_lines = ["Top Runs"]
    if scores:
        for index, entry in enumerate(scores[:5], start=1):
            score_lines.append(f"{index}. {entry.score:>5}  F{entry.floor_reached}  {entry.title}")
    else:
        score_lines.append("No high scores yet.")
    inner_top, inner_left, inner_width, _ = draw_panel(
        stdscr,
        top + panel_height + 1,
        max(2, (width - 40) // 2),
        40,
        len(score_lines) + 2,
        title="TOP RUNS",
    )
    for index, line in enumerate(score_lines[1:], start=1):
        stdscr.addnstr(inner_top + index, inner_left, line, inner_width)
    stdscr.refresh()


def draw_high_scores(stdscr: CursesWindow, scores: list[ScoreEntry]) -> None:
    stdscr.erase()
    lines = ["", "Recorded Runs", ""]
    if scores:
        for index, entry in enumerate(scores[:10], start=1):
            lines.append(
                f"{index:>2}. {entry.score:>5}  Floor {entry.floor_reached:<2}  "
                f"{entry.title}  Scrap {entry.scrap}"
            )
    else:
        lines.append("No recorded runs yet.")
    lines.extend(["", "Esc closes  ? opens the codex"])
    panel_width = min(72, max(len(line) for line in lines) + 4)
    panel_height = len(lines) + 2
    height, width = stdscr.getmaxyx()
    top = max(2, (height - panel_height) // 2)
    left = max(2, (width - panel_width) // 2)
    inner_top, inner_left, inner_width, _ = draw_panel(
        stdscr, top, left, panel_width, panel_height, title="HIGH SCORES"
    )
    for index, line in enumerate(lines):
        if line:
            stdscr.addnstr(inner_top + index, inner_left, line, inner_width)
    stdscr.refresh()


def draw_modal(stdscr: CursesWindow, overlay: OverlayState) -> None:
    if not overlay.visible:
        return
    height, width = stdscr.getmaxyx()
    if overlay.backdrop:
        fill = " " * max(0, width - 1)
        attrs = curses.color_pair(COLOR_IDS[CellColor.BACKDROP])
        for y in range(height):
            stdscr.addnstr(y, 0, fill, width - 1, attrs)
    content = [overlay.title, *overlay.lines]
    body = content[1:] if len(content) > 1 else [""]
    modal_width = min(width - 8, max(len(line) for line in content) + 4)
    modal_height = len(body) + 2
    top = max(2, (height - modal_height) // 2)
    left = max(2, (width - modal_width) // 2)
    inner_top, inner_left, inner_width, _ = draw_panel(
        stdscr, top, left, modal_width, modal_height, title=overlay.title
    )
    for index, line in enumerate(body):
        stdscr.addnstr(inner_top + index, inner_left, line, inner_width)


def draw_centered_block(
    stdscr: CursesWindow,
    lines: list[str],
    *,
    start_y: int | None = None,
) -> None:
    height, width = stdscr.getmaxyx()
    if start_y is None:
        start_y = max(1, (height - len(lines)) // 2)
    for offset, line in enumerate(lines):
        x = max(0, (width - len(line)) // 2)
        stdscr.addnstr(
            start_y + offset, x, line, max(0, width - x - 1), curses.A_BOLD if offset == 0 else 0
        )


def draw_block(
    stdscr: CursesWindow,
    lines: list[str],
    top: int,
    left: int,
) -> None:
    height, width = stdscr.getmaxyx()
    for offset, line in enumerate(lines):
        if top + offset >= height - 1:
            break
        stdscr.addnstr(top + offset, left, line, max(0, width - left - 1))


def draw_panel(
    stdscr: CursesWindow,
    top: int,
    left: int,
    width: int,
    height: int,
    *,
    title: str | None = None,
) -> tuple[int, int, int, int]:
    border_attrs = curses.color_pair(COLOR_IDS[CellColor.BORDER])
    title_attrs = curses.color_pair(COLOR_IDS[CellColor.TITLE]) | curses.A_BOLD
    fill_attrs = curses.color_pair(COLOR_IDS[CellColor.PANEL_FILL])
    horiz = "═" * max(0, width - 2)
    stdscr.addnstr(top, left, f"╔{horiz}╗", width, border_attrs)
    for row in range(1, max(1, height - 1)):
        stdscr.addnstr(top + row, left, "║", 1, border_attrs)
        if width > 2:
            stdscr.addnstr(top + row, left + 1, " " * (width - 2), width - 2, fill_attrs)
        stdscr.addnstr(top + row, left + width - 1, "║", 1, border_attrs)
    stdscr.addnstr(top + height - 1, left, f"╚{horiz}╝", width, border_attrs)
    if title:
        stdscr.addnstr(top, left + 2, f" {title} ", width - 4, title_attrs)
    return top + 1, left + 1, width - 2, height - 2


def _cell_attrs(cell: RenderCell, colors: dict[CellColor, int]) -> int:
    attrs = curses.color_pair(colors.get(cell.color, 0))
    if cell.bold:
        attrs |= curses.A_BOLD
    if cell.reverse:
        attrs |= curses.A_REVERSE
    if cell.flash:
        attrs |= curses.A_REVERSE | curses.A_BOLD
    if cell.dim:
        attrs |= curses.A_DIM
    return attrs


def draw_effects(
    stdscr: CursesWindow,
    map_top: int,
    map_left: int,
    state: RenderState,
    colors: dict[CellColor, int],
) -> None:
    for effect in state.effects:
        if not effect.points:
            continue
        attrs = curses.color_pair(colors.get(effect.color, 0)) | curses.A_BOLD
        for point in effect.points:
            stdscr.addstr(map_top + point.y, map_left + point.x, effect.glyph, attrs)


def draw_sidebar(
    stdscr: CursesWindow,
    top: int,
    left: int,
    width: int,
    height: int,
    state: RenderState,
    colors: dict[CellColor, int],
) -> None:
    inner_top, inner_left, inner_width, inner_height = draw_panel(
        stdscr, top, left, width, height, title="TACTICAL"
    )
    line = inner_top
    alert_flash = any(effect.kind == EffectKind.ALERT_BAR for effect in state.effects)

    for text in state.sidebar.objective.lines:
        stdscr.addnstr(
            line, inner_left, text, inner_width, curses.A_BOLD if text.startswith("Floor") else 0
        )
        line += 1

    for bar in state.status_bars:
        draw_status_bar(
            stdscr,
            line,
            inner_left,
            inner_width,
            bar,
            colors,
            flash=alert_flash and bar.label == "Alert",
        )
        line += 1

    stdscr.addnstr(line, inner_left, "Noise Trend", inner_width, curses.A_BOLD)
    line += 1
    draw_noise_chart(stdscr, line, inner_left, inner_width, state.noise_history, colors)
    line += 5

    for section in (state.sidebar.tools, state.sidebar.guidance, state.sidebar.modules):
        if line < inner_top + inner_height:
            stdscr.addnstr(line, inner_left, section.title, inner_width, curses.A_BOLD)
            line += 1
        for text in section.lines:
            if line >= inner_top + inner_height:
                break
            stdscr.addnstr(line, inner_left, text, inner_width)
            line += 1


def draw_status_bar(
    stdscr: CursesWindow,
    y: int,
    left: int,
    width: int,
    bar: StatusBar,
    colors: dict[CellColor, int],
    *,
    flash: bool = False,
) -> None:
    label = f"{bar.label[:5]:<5}"
    bar_width = max(6, width - len(label) - 4)
    maximum = max(1, bar.maximum)
    filled = min(bar_width, round((max(0, bar.value) / maximum) * bar_width))
    attrs = curses.A_BOLD | (curses.A_REVERSE if flash else 0)
    stdscr.addnstr(y, left, label, len(label), attrs)
    stdscr.addnstr(y, left + len(label) + 1, "[", 1, attrs)
    fill_attrs = (
        curses.color_pair(colors.get(CellColor(bar.color.value), 0))
        | curses.A_BOLD
        | (curses.A_REVERSE if flash else 0)
    )
    stdscr.addnstr(y, left + len(label) + 2, "█" * filled, bar_width, fill_attrs)
    empty_attrs = curses.A_REVERSE if flash else 0
    stdscr.addnstr(
        y,
        left + len(label) + 2 + filled,
        "·" * (bar_width - filled),
        bar_width - filled,
        empty_attrs,
    )
    stdscr.addnstr(y, left + len(label) + 2 + bar_width, "]", 1, attrs)


def draw_noise_chart(
    stdscr: CursesWindow,
    top: int,
    left: int,
    width: int,
    history: list[int],
    colors: dict[CellColor, int],
) -> None:
    chart_height = 4
    chart_width = min(len(history) * 2 - 1, width)
    start_x = left + max(0, (width - chart_width) // 2)
    levels = [round((value / MAX_NOISE) * chart_height) if MAX_NOISE else 0 for value in history]
    bar_attrs = curses.color_pair(colors[CellColor.BAR_NOISE]) | curses.A_BOLD
    empty_attrs = curses.color_pair(colors[CellColor.FOG]) | curses.A_DIM
    for row in range(chart_height):
        threshold = chart_height - row
        for index, level in enumerate(levels):
            x = start_x + index * 2
            char = "▮" if level >= threshold else "·"
            stdscr.addnstr(top + row, x, char, 1, bar_attrs if char == "▮" else empty_attrs)
    labels = " ".join(str((index + 1) % 10) for index in range(len(history)))
    stdscr.addnstr(top + chart_height, start_x, labels, width, curses.A_DIM)


def draw_log_panel(
    stdscr: CursesWindow,
    top: int,
    left: int,
    width: int,
    height: int,
    log_lines: list[str],
) -> None:
    inner_top, inner_left, inner_width, inner_height = draw_panel(
        stdscr, top, left, width, height, title="LOG"
    )
    for index, line in enumerate(log_lines[:inner_height]):
        stdscr.addnstr(inner_top + index, inner_left, f"› {line}", inner_width)
