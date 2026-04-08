from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voidcat.controller import GameController, Scene
from voidcat.engine import GameEngine
from voidcat.help import HELP_PAGES
from voidcat.models import ActionType, GameMode


class ControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.engine = GameEngine(seed=11, score_file=Path(self.tempdir.name) / "scores.json")
        self.controller = GameController(self.engine)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_title_keys_transition_between_title_help_and_scores(self) -> None:
        result = self.controller.handle_key("?")
        self.assertFalse(result.engine_changed)
        self.assertEqual(self.controller.scene, Scene.HELP)

        result = self.controller.handle_key("esc")
        self.assertFalse(result.engine_changed)
        self.assertEqual(self.controller.scene, Scene.TITLE)

        result = self.controller.handle_key("h")
        self.assertFalse(result.engine_changed)
        self.assertEqual(self.controller.scene, Scene.SCORES)

        result = self.controller.handle_key("esc")
        self.assertFalse(result.engine_changed)
        self.assertEqual(self.controller.scene, Scene.TITLE)

    def test_new_game_enters_game_scene_and_marks_engine_changed(self) -> None:
        result = self.controller.handle_key("n")

        self.assertTrue(result.engine_changed)
        self.assertFalse(result.should_quit)
        self.assertEqual(self.controller.scene, Scene.GAME)
        self.assertFalse(self.engine.daily_run_active)

    def test_title_daily_run_and_seed_reroll_controls(self) -> None:
        original_seed = self.engine.seed

        reroll = self.controller.handle_key("r")

        self.assertFalse(reroll.engine_changed)
        self.assertEqual(self.controller.scene, Scene.TITLE)
        self.assertNotEqual(self.engine.seed, original_seed)
        self.assertFalse(self.engine.daily_run_active)

        daily = self.controller.handle_key("d")

        self.assertTrue(daily.engine_changed)
        self.assertEqual(self.controller.scene, Scene.GAME)
        self.assertTrue(self.engine.daily_run_active)
        self.assertEqual(self.engine.seed, self.engine.daily_seed())

    def test_pending_direction_action_dispatches_to_engine(self) -> None:
        self.controller.handle_key("n")

        pending = self.controller.handle_key("k")
        self.assertFalse(pending.engine_changed)
        self.assertIsNotNone(self.controller.pending_action)

        result = self.controller.handle_key("d")
        self.assertTrue(result.engine_changed)
        self.assertIsNone(self.controller.pending_action)

    def test_quit_confirm_round_trip_stays_in_game_until_confirmed(self) -> None:
        self.controller.handle_key("n")

        prompt = self.controller.handle_key("q")
        self.assertFalse(prompt.engine_changed)
        self.assertTrue(self.controller.quit_confirm)
        self.assertEqual(self.controller.scene, Scene.GAME)

        dismissed = self.controller.handle_key("n")
        self.assertFalse(dismissed.engine_changed)
        self.assertFalse(self.controller.quit_confirm)

        self.controller.handle_key("q")
        confirmed = self.controller.handle_key("y")
        self.assertTrue(confirmed.should_quit)

    def test_help_and_scores_keys_cover_navigation_edges(self) -> None:
        self.controller.scene = Scene.HELP
        self.controller.return_scene = Scene.TITLE
        self.controller.help_page_index = 1

        self.controller.handle_key("KEY_RIGHT")
        self.assertEqual(self.controller.help_page_index, 2)

        self.controller.handle_key("KEY_LEFT")
        self.assertEqual(self.controller.help_page_index, 1)

        self.controller.handle_key("enter")
        self.assertEqual(self.controller.scene, Scene.TITLE)

        self.controller.scene = Scene.SCORES
        self.controller.return_scene = Scene.TITLE
        self.controller.handle_key("?")
        self.assertEqual(self.controller.scene, Scene.HELP)

        self.controller.scene = Scene.SCORES
        self.controller.return_scene = Scene.TITLE
        self.assertTrue(self.controller.handle_key("q").should_quit)

    def test_help_navigation_wraps_across_page_bounds(self) -> None:
        self.controller.scene = Scene.HELP
        self.controller.return_scene = Scene.GAME
        self.controller.help_page_index = len(HELP_PAGES) - 1

        self.controller.handle_key("KEY_RIGHT")
        self.assertEqual(self.controller.help_page_index, 0)

        self.controller.handle_key("KEY_LEFT")
        self.assertEqual(self.controller.help_page_index, len(HELP_PAGES) - 1)

    def test_game_keys_dispatch_actions_and_wait(self) -> None:
        self.controller.handle_key("n")

        with patch.object(self.engine, "perform_action", return_value=True) as perform_action:
            self.assertTrue(self.controller.handle_key("w").engine_changed)
            self.assertTrue(self.controller.handle_key("e").engine_changed)
            self.assertTrue(self.controller.handle_key("h").engine_changed)
            self.assertTrue(self.controller.handle_key("x").engine_changed)
            self.assertTrue(self.controller.handle_key(" ").engine_changed)

        self.assertEqual(perform_action.call_args_list[0].args, (ActionType.MOVE, "w"))
        self.assertEqual(perform_action.call_args_list[1].args, (ActionType.INTERACT,))
        self.assertEqual(perform_action.call_args_list[2].args, (ActionType.HISS,))
        self.assertEqual(perform_action.call_args_list[3].args, (ActionType.HIDE,))
        self.assertEqual(perform_action.call_args_list[4].args, (ActionType.WAIT,))

    def test_dock_and_game_over_routes_use_engine_entrypoints(self) -> None:
        self.controller.scene = Scene.GAME
        self.engine.mode = GameMode.DOCK_SHOP

        with (
            patch.object(self.engine, "buy_dock_offer", return_value=True) as buy_offer,
            patch.object(self.engine, "descend") as descend,
            patch.object(self.engine, "finish_run") as finish_run,
        ):
            self.assertTrue(self.controller.handle_key("1").engine_changed)
            self.assertTrue(self.controller.handle_key("d").engine_changed)
            self.assertTrue(self.controller.handle_key("e").engine_changed)
            self.controller.handle_key("q")

        buy_offer.assert_called_once_with(1)
        descend.assert_called_once()
        finish_run.assert_called_once()
        self.assertTrue(self.controller.quit_confirm)

        self.engine.mode = GameMode.GAME_OVER
        self.controller.quit_confirm = False
        with patch.object(self.engine, "new_game") as new_game:
            self.assertTrue(self.controller.handle_key("n").engine_changed)
            self.assertEqual(self.controller.scene, Scene.GAME)
            new_game.assert_called_once()

        self.assertFalse(self.controller.handle_key("h").engine_changed)
        self.assertEqual(self.controller.scene, Scene.SCORES)

        self.controller.scene = Scene.GAME
        self.engine.mode = GameMode.GAME_OVER
        self.assertFalse(self.controller.handle_key("?").engine_changed)
        self.assertEqual(self.controller.scene, Scene.HELP)
        self.controller.scene = Scene.GAME
        self.engine.mode = GameMode.GAME_OVER
        self.assertTrue(self.controller.handle_key("q").should_quit)

    def test_pending_action_escape_cancels_without_calling_engine(self) -> None:
        self.controller.handle_key("n")
        self.controller.pending_action = ActionType.POUNCE

        with patch.object(self.engine, "perform_action") as perform_action:
            result = self.controller.handle_key("esc")

        self.assertFalse(result.engine_changed)
        self.assertIsNone(self.controller.pending_action)
        perform_action.assert_not_called()
