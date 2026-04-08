from __future__ import annotations

import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from tests.helpers import (
    FakeWindow,
    battery,
    build_box_floor,
    build_engine,
    crawler,
    signal,
    stalker,
)
from voidcat.app import _read_key
from voidcat.models import (
    AlertState,
    CellColor,
    EffectKind,
    OverlayState,
    Point,
    RenderEffect,
    ScoreEntry,
)
from voidcat.ui import (
    COLOR_IDS,
    draw_high_scores,
    draw_title,
    ensure_terminal_size,
    init_colors,
    render_game,
)


class UITests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _score_file(self) -> Path:
        return Path(self.tempdir.name) / "scores.json"

    def _patch_ui_curses(self) -> ExitStack:
        stack = ExitStack()
        stack.enter_context(
            patch("voidcat.ui.curses.color_pair", side_effect=lambda value: value << 8)
        )
        return stack

    def test_ensure_terminal_size_reports_small_terminal(self) -> None:
        window = FakeWindow(height=20, width=60)

        ok = ensure_terminal_size(window)

        self.assertFalse(ok)
        self.assertTrue(window.refreshed)
        self.assertTrue(any("VOIDCAT needs a larger terminal." in line for line in window.lines))

    def test_init_colors_configures_expected_palette(self) -> None:
        with self._patch_ui_curses():
            with (
                patch("voidcat.ui.curses.start_color"),
                patch("voidcat.ui.curses.use_default_colors"),
                patch("voidcat.ui.curses.init_pair") as init_pair,
            ):
                colors = init_colors()

        self.assertEqual(colors, COLOR_IDS)
        self.assertGreaterEqual(init_pair.call_count, len(COLOR_IDS) - 1)

    def test_render_game_draws_map_sidebar_log_and_overlay(self) -> None:
        floor = build_box_floor(
            width=9,
            height=7,
            relays=[Point(2, 1)],
            items=[battery(Point(3, 1), amount=7), signal(Point(4, 1))],
            enemies=[
                crawler(Point(5, 1)),
                stalker(Point(5, 2), alert=AlertState.CHASING),
            ],
            heat=[Point(6, 1)],
        )
        engine = build_engine(floor, score_file=self._score_file(), power=18)
        engine.player.position = Point(1, 2)
        engine.player.hidden_turns = 1
        engine.current_noise = 6
        engine.ship_alert = 5
        engine.heard_position = Point(4, 2)
        engine.restored_relays = {Point(2, 1)}
        engine.floor.objective.restored_relays = 1
        engine.last_turn_effects = [
            RenderEffect(EffectKind.KNOCK, [Point(4, 2)], CellColor.NOISE, 2, "◌"),
            RenderEffect(EffectKind.ALERT_BAR, [], CellColor.RELAY_PULSE, 1, "!"),
        ]
        state = engine.get_render_state(
            OverlayState(title="VOIDCAT // HELP", lines=["Stay low."], backdrop=True)
        )
        window = FakeWindow()

        with self._patch_ui_curses():
            render_game(window, state, COLOR_IDS, title_suffix=" | HELP")

        self.assertTrue(window.refreshed)
        self.assertTrue(any("VOIDCAT | HELP" in line for line in window.lines))
        self.assertTrue(any("TACTICAL" in line for line in window.lines))
        self.assertTrue(any("LOG" in line for line in window.lines))
        self.assertTrue(any("Stay low." in line for line in window.lines))

    def test_title_and_high_score_panels_render_expected_copy(self) -> None:
        scores = [
            ScoreEntry(
                timestamp="2026-04-07T00:00:00+00:00",
                score=420,
                floor_reached=4,
                scrap=7,
                relays_restored=3,
                rare_modules=1,
                extracted=True,
                title="Silent Gremlin",
            )
        ]
        with self._patch_ui_curses():
            title_window = FakeWindow()
            draw_title(title_window, scores)

            score_window = FakeWindow()
            draw_high_scores(score_window, scores)

        self.assertTrue(title_window.refreshed)
        self.assertTrue(score_window.refreshed)
        self.assertTrue(any("VOIDCAT" in line for line in title_window.lines))
        self.assertTrue(any("HIGH SCORES" in line for line in score_window.lines))
        self.assertTrue(any("Silent Gremlin" in line for line in score_window.lines))

    def test_read_key_normalizes_common_inputs(self) -> None:
        self.assertEqual(_read_key(FakeWindow(keycodes=[ord("Q")])), "q")
        self.assertEqual(_read_key(FakeWindow(keycodes=[27])), "esc")
        self.assertEqual(_read_key(FakeWindow(keycodes=[9])), "tab")

    def test_read_key_uses_curses_keyname_for_special_keys(self) -> None:
        window = FakeWindow(keycodes=[260])

        with patch("voidcat.app.curses.keyname", return_value=b"KEY_LEFT"):
            key = _read_key(window)

        self.assertEqual(key, "KEY_LEFT")


if __name__ == "__main__":
    unittest.main()
