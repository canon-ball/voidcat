from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
except ImportError:  # pragma: no cover - optional dependency
    pygame = None

import voidcat.gfx_app as gfx_app_module
from voidcat.controller import Scene
from voidcat.gfx_app import (
    BAR_COLORS,
    INTERNAL_HEIGHT,
    INTERNAL_WIDTH,
    PALETTE,
    SCENE_GAME,
    SCENE_HELP,
    SCENE_SCORES,
    SCENE_TITLE,
    GfxApp,
    _accent_for_cell,
    _bar_color,
    _intent_color,
    _is_direction_key,
    _key_from_event,
    _sprite_name_for_cell,
    _sprite_name_for_effect,
)
from voidcat.help import HELP_PAGES
from voidcat.models import (
    ActionType,
    AlertState,
    BarColor,
    CellColor,
    EffectKind,
    EnemyIntent,
    EnemyType,
    GameMode,
    MapMarker,
    Point,
    RenderCell,
    RenderEffect,
    ScoreEntry,
    ShipAlertStage,
)


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

    def test_main_uses_app_lifecycle_and_exits_cleanly_without_pygame(self) -> None:
        fake_app = MagicMock()
        with patch.object(gfx_app_module, "GfxApp", return_value=fake_app):
            gfx_app_module.main()

        fake_app.run.assert_called_once()
        fake_app.shutdown.assert_called_once()

        with patch.object(gfx_app_module, "_pygame", None):
            with self.assertRaises(SystemExit):
                gfx_app_module.main()

    def test_scene_and_controller_properties_round_trip(self) -> None:
        self.app.scene = Scene.SCORES
        self.app.return_scene = SCENE_TITLE
        self.app.help_page_index = 3
        self.app.pending_action = ActionType.KNOCK
        self.app.quit_confirm = True

        self.assertEqual(self.app.scene_name, SCENE_SCORES)
        self.assertEqual(self.app.return_scene, SCENE_TITLE)
        self.assertEqual(self.app.help_page_index, 3)
        self.assertEqual(self.app.pending_action, ActionType.KNOCK)
        self.assertTrue(self.app.quit_confirm)

    def test_desktop_size_and_window_creation_cover_windowed_and_fullscreen_paths(self) -> None:
        self.assertEqual(self.app._desktop_size()[0] >= 1, True)

        with (
            patch("voidcat.gfx_app.pygame.display.get_desktop_sizes", return_value=[]),
            patch(
                "voidcat.gfx_app.pygame.display.Info",
                return_value=SimpleNamespace(current_w=0, current_h=0),
            ),
        ):
            self.assertEqual(self.app._desktop_size(), self.app.windowed_size)

        with patch(
            "voidcat.gfx_app.pygame.display.set_mode", return_value=self.app.window
        ) as set_mode:
            self.app.fullscreen_requested = False
            self.app.fullscreen_capable = False
            with patch.object(self.app, "_desktop_size", return_value=self.app.windowed_size):
                self.app._create_window()
            set_mode.assert_called_with(self.app.windowed_size, pygame.RESIZABLE)

        with patch(
            "voidcat.gfx_app.pygame.display.set_mode", return_value=self.app.window
        ) as set_mode:
            self.app.fullscreen_requested = True
            self.app.fullscreen_capable = True
            self.app._create_window()
            set_mode.assert_called_with(self.app._desktop_size(), pygame.FULLSCREEN)

    def test_run_loop_handles_events_then_ticks_once(self) -> None:
        self.app.clock = MagicMock()
        quit_event = pygame.event.Event(pygame.QUIT)
        with (
            patch("voidcat.gfx_app.pygame.event.get", return_value=[quit_event]),
            patch.object(self.app, "render_frame") as render_frame,
        ):
            self.app.run()

        render_frame.assert_called_once()
        self.app.clock.tick.assert_called_once_with(60)
        self.assertTrue(self.app.should_quit)

    def test_handle_event_covers_quit_non_key_and_key_paths(self) -> None:
        with patch.object(self.app, "handle_key") as handle_key:
            self.app.handle_event(pygame.event.Event(pygame.MOUSEMOTION))
            handle_key.assert_not_called()

            self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=0, unicode=""))
            handle_key.assert_not_called()

            self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, unicode="a"))
            handle_key.assert_called_once_with("a")

        self.app.should_quit = False
        self.app.handle_event(pygame.event.Event(pygame.QUIT))
        self.assertTrue(self.app.should_quit)

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

    def test_refresh_effect_snapshot_and_current_game_state_cover_active_and_expired_effects(
        self,
    ) -> None:
        effect = RenderEffect(EffectKind.KNOCK, [Point(1, 1)], CellColor.NOISE, 2, "◌")
        state_with_effect = self.app.engine.get_render_state()
        state_with_effect.effects = [effect]

        with patch.object(self.app.engine, "get_render_state", return_value=state_with_effect):
            self.app._refresh_effect_snapshot()

        self.assertIsNotNone(self.app.effect_snapshot)
        self.assertIsNotNone(self.app.effect_started_ms)

        self.app.effect_snapshot = state_with_effect
        self.app.effect_started_ms = 100
        with patch("voidcat.gfx_app.pygame.time.get_ticks", return_value=120):
            active = self.app._current_game_state()
        self.assertEqual(len(active.effects), 1)

        self.app.engine.last_turn_effects = [effect]
        self.app.effect_snapshot = state_with_effect
        self.app.effect_started_ms = 100
        live_state = replace(state_with_effect, effects=[])
        with (
            patch("voidcat.gfx_app.pygame.time.get_ticks", return_value=1000),
            patch.object(self.app.engine, "get_render_state", return_value=live_state),
        ):
            current = self.app._current_game_state()
        self.assertEqual(current.effects, [])
        self.assertEqual(self.app.engine.last_turn_effects, [])
        self.assertIsNone(self.app.effect_snapshot)
        self.assertIsNone(self.app.effect_started_ms)

        with patch.object(self.app.engine, "get_render_state", return_value=live_state):
            self.app._refresh_effect_snapshot()
        self.assertIsNone(self.app.effect_snapshot)
        self.assertIsNone(self.app.effect_started_ms)

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

    def test_render_frame_covers_scores_scene_and_scores_panel_variants(self) -> None:
        self.app.engine.scores = [
            ScoreEntry(
                timestamp="2026-04-08T00:00:00+00:00",
                score=500,
                floor_reached=4,
                scrap=3,
                relays_restored=4,
                rare_modules=2,
                extracted=True,
                title="Vent Ghost",
                seed=123,
                daily_run=True,
                build_path="Stealth Route",
                highlight="Stayed cold all run.",
            )
        ]
        self.app.scene = SCENE_SCORES
        self.assertEqual(self.app.render_frame(), SCENE_SCORES)

        self.app.engine.scores = []
        self.app._render_scores_scene()

    def test_render_game_scene_uses_alert_accents_and_overlay_cards(self) -> None:
        self.app.handle_key("n")
        state = self.app.engine.get_render_state()
        state.hud.alert = 4
        state.hud.alert_stage = ShipAlertStage.HUNT
        self.app.controller.pending_action = ActionType.KNOCK
        with (
            patch.object(self.app, "_current_game_state", return_value=state),
            patch.object(self.app, "_draw_map"),
            patch.object(self.app, "_draw_sidebar"),
            patch.object(self.app, "_draw_log_strip"),
            patch.object(self.app, "_draw_center_card") as draw_center_card,
            patch.object(self.app, "_draw_banner") as draw_banner,
        ):
            self.app._render_game_scene()
        draw_banner.assert_called_once()
        self.assertEqual(draw_banner.call_args.kwargs["accent"], PALETTE["gold"])
        draw_center_card.assert_called_once()

        state.hud.alert = 9
        state.hud.alert_stage = ShipAlertStage.SWEEP
        self.app.controller.pending_action = None
        self.app.engine.mode = GameMode.GAME_OVER
        with (
            patch.object(self.app, "_current_game_state", return_value=state),
            patch.object(self.app, "_draw_map"),
            patch.object(self.app, "_draw_sidebar"),
            patch.object(self.app, "_draw_log_strip"),
            patch.object(self.app, "_draw_center_card"),
            patch.object(self.app, "_draw_banner") as draw_banner,
        ):
            self.app._render_game_scene()
        self.assertEqual(draw_banner.call_args.kwargs["accent"], PALETTE["danger_hot"])

    def test_draw_map_and_cell_helpers_cover_markers_intents_threats_and_effects(self) -> None:
        self.app.handle_key("n")
        self.app.pending_action = ActionType.KNOCK
        self.app.engine.decoy_target = Point(3, 1)
        self.app.engine.decoy_turns = 2
        self.app.threat_view_active = True
        state = self.app.engine.get_render_state()
        state.map_rows[1][1] = RenderCell("·", CellColor.PLAYER_HIDDEN, flash=True)
        state.map_rows[1][2] = RenderCell("·", CellColor.FOG)
        state.map_rows[1][3] = RenderCell("·", CellColor.FLOOR, dim=True, flash=True)
        state.effects = [
            RenderEffect(EffectKind.MOVE_TRAIL, [Point(1, 1)], CellColor.NOISE, 2, "·"),
            RenderEffect(EffectKind.ALERT_BAR, [], CellColor.RELAY_PULSE, 2, "!"),
        ]
        state.markers = [
            MapMarker(Point(4, 1), "Dock", CellColor.DOCK),
            MapMarker(Point(5, 1), "Relay", CellColor.RELAY, pulse=True),
        ]
        state.enemy_intents = [
            EnemyIntent(
                enemy_type=EnemyType.CRAWLER,
                alert=AlertState.INVESTIGATING,
                origin=Point(2, 2),
                destination=Point(3, 2),
            ),
            EnemyIntent(
                enemy_type=EnemyType.STALKER,
                alert=AlertState.CHASING,
                origin=Point(4, 2),
                destination=Point(4, 2),
                attack=True,
            ),
        ]
        state.threat_cells = [self.app.engine.player.position, Point(2, 3)]

        with patch("voidcat.gfx_app.pygame.time.get_ticks", return_value=180):
            self.app._draw_map(state)
            self.app._draw_cell(RenderCell("·", CellColor.VOID), 0, 0, move_active=False)

    def test_redraw_player_preview_helpers_and_layout_helpers_cover_guard_paths(self) -> None:
        self.app.handle_key("n")
        state = self.app.engine.get_render_state()
        self.assertIsNotNone(self.app._pounce_target("d"))
        self.assertIsNone(self.app._pounce_target("northwest"))

        self.app.pending_action = None
        self.assertEqual(self.app._preview_knock_paths(), [])
        self.assertEqual(self.app._preview_pounce_targets(), [])

        self.app.engine.mode = GameMode.GAME_OVER
        self.app.pending_action = ActionType.KNOCK
        self.assertEqual(self.app._preview_knock_paths(), [])
        self.app.pending_action = ActionType.POUNCE
        self.assertEqual(self.app._preview_pounce_targets(), [])

        self.app.engine.mode = GameMode.PLAYING
        self.app.engine.floor = None
        self.app._redraw_player_cell(state, move_active=False)

        self.app.engine = gfx_app_module.GameEngine(seed=11, score_file=self.app.engine.score_file)
        self.app.controller = gfx_app_module.GameController(self.app.engine)
        self.app.engine.player.position = Point(99, 99)
        self.app._redraw_player_cell(self.app.engine.get_render_state(), move_active=False)

        bounds = pygame.Rect(20, 20, 40, 40)
        clamped = self.app._clamp_rect(pygame.Rect(0, 0, 20, 20), bounds)
        self.assertEqual(clamped.left, bounds.left)
        self.assertEqual(clamped.top, bounds.top)

        candidates = self.app._marker_label_candidates(Point(1, 1), (60, 22))
        self.assertTrue(candidates)
        inset = self.app.map_panel_rect.inflate(-12, -12)
        self.assertTrue(all(inset.contains(frame) for frame in candidates))

    def test_sidebar_panel_log_and_present_helpers_cover_display_branches(self) -> None:
        self.app.handle_key("n")
        state = self.app.engine.get_render_state()
        self.app._draw_sidebar(state)
        self.app.engine.floor.objective.restored_relays = (
            self.app.engine.floor.objective.required_relays
        )
        self.app._draw_sidebar(self.app.engine.get_render_state())

        self.app._draw_status_bar("Power", 0, 0, BarColor.POWER, 20, 20, 140)
        self.app._draw_status_bar("Noise", 3, 9, BarColor.NOISE, 20, 48, 140)
        self.app._draw_noise_chart([], 20, 80, 200, 40)
        self.app._draw_noise_chart([0, 2, 5, 9], 20, 126, 200, 40)

        empty_log_state = replace(state, log_lines=[], footer="Quiet.")
        self.app._draw_log_strip(empty_log_state)
        self.app._draw_center_card(
            "Long Card",
            ["A" * 120, "B" * 120, "C" * 120, "D" * 120, "E" * 120],
        )
        self.app._draw_panel(pygame.Rect(100, 100, 180, 120), "PANEL", dense=True)
        self.app._draw_scores(pygame.Rect(100, 240, 300, 200), [], limit=4)
        self.app._draw_scores(
            pygame.Rect(100, 240, 300, 200),
            [
                ScoreEntry(
                    timestamp="2026-04-08T00:00:00+00:00",
                    score=300,
                    floor_reached=2,
                    scrap=1,
                    relays_restored=2,
                    rare_modules=0,
                    extracted=False,
                    title="Orange Cat Behavior",
                    build_path="Adaptive Route",
                )
            ],
            limit=4,
        )
        drawn = self.app._draw_lines(
            ["one", "two", "three"],
            pygame.Rect(10, 10, 80, 22),
            self.app.font_small,
            PALETTE["text"],
            line_height=18,
        )
        self.assertEqual(drawn, 1)

        with patch("voidcat.gfx_app.pygame.display.flip"):
            self.app.window = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))
            self.app._present()
            self.app.window = pygame.Surface((INTERNAL_WIDTH * 2, INTERNAL_HEIGHT * 2))
            self.app._present()
            self.app.window = pygame.Surface((INTERNAL_WIDTH // 2, INTERNAL_HEIGHT // 2))
            self.app._present()

    def test_overlay_and_helper_functions_cover_all_render_mappings(self) -> None:
        self.app.handle_key("n")

        self.app.quit_confirm = True
        self.assertEqual(
            self.app._game_overlay(self.app.engine.get_render_state())[0],
            "Quit Current Session?",
        )

        self.app.quit_confirm = False
        self.app.pending_action = ActionType.KNOCK
        self.assertEqual(self.app._game_overlay(self.app.engine.get_render_state())[0], "Aim Knock")
        self.app.pending_action = ActionType.POUNCE
        self.assertEqual(
            self.app._game_overlay(self.app.engine.get_render_state())[0],
            "Aim Pounce",
        )
        self.app.pending_action = None

        self.app.engine.mode = GameMode.DOCK_SHOP
        self.assertIsNotNone(self.app._game_overlay(self.app.engine.get_render_state()))
        self.app.engine.mode = GameMode.GAME_OVER
        self.assertEqual(self.app._game_overlay(self.app.engine.get_render_state())[0], "Run Over")
        self.app.engine.mode = GameMode.PLAYING
        self.assertIsNone(self.app._game_overlay(self.app.engine.get_render_state()))

        self.assertEqual(
            _key_from_event(
                pygame.event.Event(
                    pygame.KEYDOWN, key=pygame.K_SLASH, mod=pygame.KMOD_SHIFT, unicode="?"
                )
            ),
            "?",
        )
        self.assertEqual(
            _key_from_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB, unicode="")),
            "tab",
        )
        self.assertEqual(
            _key_from_event(pygame.event.Event(pygame.KEYDOWN, key=0, unicode="N")),
            "n",
        )
        self.assertIsNone(_key_from_event(pygame.event.Event(pygame.KEYDOWN, key=0, unicode="")))
        self.assertTrue(_is_direction_key("KEY_LEFT"))
        self.assertFalse(_is_direction_key("enter"))

        self.assertIsNone(
            _sprite_name_for_cell(RenderCell(" ", CellColor.VOID), move_active=False)
        )
        self.assertEqual(
            _sprite_name_for_cell(RenderCell("@", CellColor.PLAYER), move_active=True),
            "player_walk",
        )
        self.assertEqual(
            _sprite_name_for_cell(RenderCell("⌂", CellColor.DOCK), move_active=False),
            "dock",
        )
        self.assertEqual(
            _sprite_name_for_cell(RenderCell("◆", CellColor.RELAY_RESTORED), move_active=False),
            "relay_restored",
        )
        self.assertEqual(
            _sprite_name_for_cell(RenderCell("≈", CellColor.HEAT), move_active=False),
            "heat",
        )
        self.assertEqual(
            _sprite_name_for_cell(RenderCell("▣", CellColor.BATTERY), move_active=False),
            "battery",
        )
        self.assertEqual(
            _sprite_name_for_cell(RenderCell("✦", CellColor.SCRAP), move_active=False),
            "scrap",
        )
        self.assertEqual(
            _sprite_name_for_cell(RenderCell("◎", CellColor.SIGNAL), move_active=False),
            "signal",
        )
        self.assertEqual(
            _sprite_name_for_cell(RenderCell("◌", CellColor.NOISE), move_active=False),
            "noise",
        )
        self.assertEqual(
            _sprite_name_for_cell(RenderCell("◍", CellColor.ENEMY_RED), move_active=False),
            "crawler",
        )
        self.assertEqual(
            _sprite_name_for_cell(RenderCell("▲", CellColor.ENEMY_HOT), move_active=False),
            "stalker",
        )
        self.assertEqual(
            _sprite_name_for_cell(RenderCell("◆", CellColor.ENEMY_RED_COOL), move_active=False),
            "mimic_reveal",
        )
        self.assertEqual(
            _sprite_name_for_cell(RenderCell("?", CellColor.FLOOR), move_active=False),
            "floor",
        )

        self.assertEqual(
            _sprite_name_for_effect(
                RenderEffect(EffectKind.KNOCK_FLASH, [], CellColor.NOISE, 1, "*")
            ),
            "signal",
        )
        self.assertEqual(
            _sprite_name_for_effect(RenderEffect(EffectKind.RELAY, [], CellColor.RELAY, 1, "*")),
            "relay_restored",
        )
        self.assertEqual(_sprite_name_for_effect(SimpleNamespace(kind="mystery")), "noise")

        self.assertEqual(_bar_color(BarColor.POWER), BAR_COLORS[BarColor.POWER])
        self.assertEqual(_bar_color("mystery"), (31, 54, 70))
        self.assertEqual(_accent_for_cell(CellColor.SIGNAL), PALETTE["noise"])
        self.assertEqual(_accent_for_cell(CellColor.FLOOR), PALETTE["muted"])
        self.assertEqual(_intent_color(AlertState.CHASING, False), PALETTE["danger"])
        self.assertEqual(_intent_color(AlertState.SCARED, False), PALETTE["cyan"])
        self.assertEqual(_intent_color(SimpleNamespace(name="mystery"), False), PALETTE["muted"])
        self.assertEqual(_intent_color(AlertState.DORMANT, True), PALETTE["danger_hot"])

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
