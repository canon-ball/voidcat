from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tests.helpers import FakeWindow, build_box_floor, build_engine
from voidcat import app
from voidcat.controller import ControllerResult, GameController, OverlayKind, Scene
from voidcat.models import ActionType, CellColor, EffectKind, GameMode, Point, RenderEffect


class _StubController:
    def __init__(self, engine: object, results: list[ControllerResult]) -> None:
        self.engine = engine
        self.scene = Scene.TITLE
        self.return_scene = Scene.TITLE
        self.help_page_index = 0
        self.pending_action = None
        self.quit_confirm = False
        self._results = list(results)

    def handle_key(self, key: str) -> ControllerResult:
        return self._results.pop(0)

    def current_overlay(self) -> OverlayKind:
        return OverlayKind.NONE


class TerminalAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _score_file(self) -> Path:
        return Path(self.tempdir.name) / "scores.json"

    def test_main_wraps_run_function(self) -> None:
        with patch("voidcat.app.curses.wrapper") as wrapper:
            app.main()

        wrapper.assert_called_once_with(app._run)

    def test_run_handles_resize_retry_then_animation_then_quit(self) -> None:
        window = FakeWindow(keycodes=[0])
        engine = Mock()
        controller = _StubController(
            engine,
            [
                ControllerResult(engine_changed=True),
                ControllerResult(should_quit=True),
            ],
        )

        with (
            patch("voidcat.app.curses.curs_set"),
            patch("voidcat.app.curses.noecho"),
            patch("voidcat.app.curses.cbreak"),
            patch("voidcat.app.init_colors", return_value={CellColor.TITLE: 18}),
            patch("voidcat.app.GameEngine", return_value=engine),
            patch("voidcat.app.GameController", return_value=controller),
            patch("voidcat.app.ensure_terminal_size", side_effect=[False, True, True]),
            patch("voidcat.app._render_scene") as render_scene,
            patch("voidcat.app._read_key", return_value="q"),
            patch("voidcat.app._animate_effects") as animate_effects,
        ):
            app._run(window)

        self.assertTrue(window.keypad_enabled)
        self.assertEqual(render_scene.call_count, 2)
        animate_effects.assert_called_once()

    def test_render_scene_routes_every_scene_variant(self) -> None:
        engine = build_engine(build_box_floor(), score_file=self._score_file())
        controller = GameController(engine)
        colors = {color: index for index, color in enumerate(CellColor)}
        window = FakeWindow()

        with (
            patch("voidcat.app.draw_title") as draw_title,
            patch("voidcat.app.draw_high_scores") as draw_high_scores,
            patch("voidcat.app.draw_modal") as draw_modal,
            patch("voidcat.app.render_game") as render_game,
        ):
            controller.scene = Scene.TITLE
            app._render_scene(window, controller, colors)

            controller.scene = Scene.SCORES
            app._render_scene(window, controller, colors)

            controller.scene = Scene.HELP
            controller.return_scene = Scene.GAME
            controller.help_page_index = 2
            app._render_scene(window, controller, colors)

            controller.return_scene = Scene.SCORES
            app._render_scene(window, controller, colors)

            controller.return_scene = Scene.TITLE
            app._render_scene(window, controller, colors)

            controller.scene = Scene.GAME
            controller.pending_action = ActionType.KNOCK
            app._render_scene(window, controller, colors)

        self.assertGreaterEqual(draw_title.call_count, 2)
        self.assertGreaterEqual(draw_high_scores.call_count, 2)
        self.assertGreaterEqual(draw_modal.call_count, 2)
        self.assertGreaterEqual(render_game.call_count, 2)
        self.assertTrue(window.refreshed)

    def test_game_overlay_and_suffix_cover_all_overlay_kinds(self) -> None:
        engine = build_engine(build_box_floor(), score_file=self._score_file())
        controller = GameController(engine)
        controller.scene = Scene.GAME

        controller.quit_confirm = True
        self.assertEqual(app._game_overlay(controller).title, "Quit the current session?")
        self.assertEqual(app._title_suffix_for_overlay(OverlayKind.QUIT), " | QUIT")

        controller.quit_confirm = False
        controller.pending_action = ActionType.KNOCK
        self.assertIn("knock", app._game_overlay(controller).title.lower())
        self.assertEqual(app._title_suffix_for_overlay(OverlayKind.KNOCK), " | KNOCK")

        controller.pending_action = ActionType.POUNCE
        self.assertIn("pounce", app._game_overlay(controller).title.lower())
        self.assertEqual(app._title_suffix_for_overlay(OverlayKind.POUNCE), " | POUNCE")

        controller.pending_action = None
        with patch.object(engine, "summary_lines", return_value=["Dock Exchange", "Descend soon."]):
            engine.mode = GameMode.DOCK_SHOP
            self.assertEqual(app._game_overlay(controller).title, "Dock Exchange")
            self.assertEqual(app._title_suffix_for_overlay(OverlayKind.DOCK), " | DOCK")

        with patch.object(engine, "summary_lines", return_value=["Run Over", "Line two."]):
            engine.mode = GameMode.GAME_OVER
            self.assertEqual(app._game_overlay(controller).title, "Run Over")
            self.assertEqual(app._title_suffix_for_overlay(OverlayKind.GAME_OVER), " | GAME OVER")

        with patch.object(engine, "summary_lines", return_value=[]):
            self.assertIsNone(app._game_overlay(controller))

        self.assertEqual(app._title_suffix_for_overlay(OverlayKind.NONE), "")

    def test_animate_effects_renders_frames_and_clears_engine_effects(self) -> None:
        engine = build_engine(build_box_floor(), score_file=self._score_file())
        engine.last_turn_effects = [
            RenderEffect(EffectKind.KNOCK, [Point(2, 1)], CellColor.NOISE, 3, "◌"),
            RenderEffect(EffectKind.HIDE, [Point(1, 1)], CellColor.RELAY_PULSE, 1, "◌"),
        ]
        window = FakeWindow()
        colors = {color: index for index, color in enumerate(CellColor)}

        with patch("voidcat.app.render_game") as render_game, patch("voidcat.app.curses.napms"):
            app._animate_effects(window, engine, colors, title_suffix=" | TEST")

        self.assertEqual(render_game.call_count, 3)
        self.assertFalse(engine.last_turn_effects)

        with patch("voidcat.app.render_game") as render_game, patch("voidcat.app.curses.napms"):
            app._animate_effects(window, engine, colors)

        render_game.assert_not_called()


if __name__ == "__main__":
    unittest.main()
