from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
except ImportError:  # pragma: no cover - optional dependency
    pygame = None

from voidcat.controller import Scene
from voidcat.gfx_app import (
    INTERNAL_HEIGHT,
    INTERNAL_WIDTH,
    SCENE_GAME,
    SCENE_HELP,
    SCENE_TITLE,
    GfxApp,
)
from voidcat.help import HELP_PAGES
from voidcat.models import CellColor, MapMarker, Point


@unittest.skipIf(pygame is None, "pygame-ce not installed")
class GfxAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.app = GfxApp(seed=9, score_file=Path(self.tempdir.name) / "scores.json")

    def tearDown(self) -> None:
        self.app.shutdown()
        self.tempdir.cleanup()

    def test_headless_app_starts_and_renders_title(self) -> None:
        scene = self.app.render_frame()

        self.assertEqual(scene, SCENE_TITLE)
        self.assertIn("player_idle", self.app.assets.surfaces)
        self.assertIn("crawler", self.app.assets.surfaces)
        self.assertEqual(self.app.assets.sprite("stalker").get_size(), (16, 16))
        self.assertGreaterEqual(self.app.window.get_size()[0], 1024)
        self.assertGreaterEqual(self.app.window.get_size()[1], 640)
        self.assertEqual(self.app.canvas.get_size(), (INTERNAL_WIDTH, INTERNAL_HEIGHT))
        self.assertFalse(self.app.fullscreen_active)

    def test_help_scene_replaces_live_game_state(self) -> None:
        self.app.handle_key("n")
        self.assertEqual(self.app.scene_name, SCENE_GAME)
        turn_count = self.app.engine.turn_count

        self.app.handle_key("?")
        self.assertEqual(self.app.scene_name, SCENE_HELP)
        self.app.render_frame()
        self.assertEqual(self.app.engine.turn_count, turn_count)

        self.app.handle_key("KEY_RIGHT")
        self.assertEqual(self.app.help_page_index, 1)

        self.app.handle_key("esc")
        self.assertEqual(self.app.scene_name, SCENE_GAME)
        self.assertEqual(self.app.controller.scene, Scene.GAME)

    def test_help_scene_wraps_when_page_index_is_out_of_range(self) -> None:
        self.app.scene = SCENE_HELP
        self.app.help_page_index = len(HELP_PAGES) + 2

        scene = self.app.render_frame()

        self.assertEqual(scene, SCENE_HELP)
        self.assertEqual(self.app._help_page_index(), 2)

    def test_game_scene_renders_after_action_and_loads_distinct_enemy_sprites(self) -> None:
        self.app.handle_key("n")
        self.app.handle_key("x")
        scene = self.app.render_frame()

        crawler_raw = pygame.image.tobytes(self.app.assets.sprite("crawler"), "RGBA")
        stalker_raw = pygame.image.tobytes(self.app.assets.sprite("stalker"), "RGBA")

        self.assertEqual(scene, SCENE_GAME)
        self.assertIsNotNone(self.app.effect_snapshot)
        self.assertNotEqual(crawler_raw, stalker_raw)

    def test_wrap_text_respects_panel_width(self) -> None:
        lines = self.app._wrap_text_lines(
            [
                "Dock exchange text should stay inside the panel "
                "even when the instructions run long.",
                "",
                "Power refreshes at the start of each floor.",
            ],
            self.app.font_body,
            220,
        )

        self.assertGreater(len(lines), 3)
        self.assertIn("", lines)
        self.assertTrue(all(self.app.font_body.size(line)[0] <= 220 for line in lines if line))

    def test_space_wait_spends_a_turn(self) -> None:
        self.app.handle_key("n")
        turn_count = self.app.engine.turn_count

        self.app.handle_key(" ")

        self.assertEqual(self.app.engine.turn_count, turn_count + 1)

    def test_f11_toggles_fullscreen_request(self) -> None:
        initial = self.app.fullscreen_requested

        self.app.handle_key("f11")

        self.assertNotEqual(self.app.fullscreen_requested, initial)

    def test_v_toggles_threat_view_in_game(self) -> None:
        self.app.handle_key("n")
        self.assertFalse(self.app.threat_view_active)

        self.app.handle_key("v")
        self.assertTrue(self.app.threat_view_active)
        self.assertEqual(self.app.render_frame(), SCENE_GAME)

        self.app.handle_key("v")
        self.assertFalse(self.app.threat_view_active)

    def test_pending_action_previews_exist_for_knock_and_pounce(self) -> None:
        self.app.handle_key("n")
        self.app.handle_key("k")
        knock_paths = self.app._preview_knock_paths()
        self.assertTrue(knock_paths)

        self.app.pending_action = None
        self.app.handle_key("p")
        pounce_targets = self.app._preview_pounce_targets()
        self.assertTrue(pounce_targets)

    def test_scene_transitions_use_shared_controller(self) -> None:
        self.assertEqual(self.app.controller.scene, Scene.TITLE)

        self.app.handle_key("?")
        self.assertEqual(self.app.scene_name, SCENE_HELP)

        self.app.handle_key("esc")
        self.assertEqual(self.app.controller.scene, Scene.TITLE)

    def test_daily_run_and_seed_reroll_are_available_from_title(self) -> None:
        original_seed = self.app.engine.seed

        self.app.handle_key("r")
        self.assertNotEqual(self.app.engine.seed, original_seed)
        self.assertEqual(self.app.scene_name, SCENE_TITLE)

        self.app.handle_key("d")
        self.assertEqual(self.app.scene_name, SCENE_GAME)
        self.assertTrue(self.app.engine.daily_run_active)
        self.assertEqual(self.app.engine.seed, self.app.engine.daily_seed())

        self.app.scene = SCENE_TITLE
        self.app.handle_key("h")
        self.assertEqual(self.app.controller.scene, Scene.SCORES)

        self.app.handle_key("esc")
        self.assertEqual(self.app.controller.scene, Scene.TITLE)

    def test_marker_labels_avoid_overlapping_each_other_and_the_player_tile(self) -> None:
        markers = [
            MapMarker(Point(5, 4), "Signal", CellColor.SIGNAL),
            MapMarker(Point(6, 4), "Scrap", CellColor.SCRAP),
            MapMarker(Point(5, 5), "Relay", CellColor.RELAY, pulse=True),
        ]

        layouts = self.app._layout_marker_labels(markers, avoid_points=[Point(6, 5)])

        self.assertEqual(len(layouts), 3)
        frames = [frame for _, frame, _ in layouts]
        player_guard = self.app._tile_rect(Point(6, 5)).inflate(4, 4)
        for index, frame in enumerate(frames):
            self.assertFalse(frame.colliderect(player_guard))
            for other in frames[index + 1 :]:
                self.assertFalse(frame.colliderect(other))


if __name__ == "__main__":
    unittest.main()
