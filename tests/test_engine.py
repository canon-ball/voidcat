from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.helpers import battery, build_box_floor, build_engine, crawler, mimic, signal, stalker
from voidcat.engine import GameEngine
from voidcat.models import (
    MAX_POWER,
    ActionType,
    AlertState,
    BarColor,
    BuildPath,
    CellColor,
    EffectKind,
    FloorCondition,
    GameMode,
    ModuleType,
    OverlayState,
    Point,
)


class FakeRNG:
    def __init__(self, *rolls: int) -> None:
        self.rolls = list(rolls)

    def randint(self, start: int, end: int) -> int:
        return self.rolls.pop(0)

    def choice(self, values):
        return values[0]

    def random(self) -> float:
        return 0.5

    def sample(self, values, count: int):
        return list(values)[:count]


class EngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.score_file = Path(self.tempdir.name) / "scores.json"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_move_cost_and_battery_pickup(self) -> None:
        floor = build_box_floor(items=[battery(Point(2, 1), amount=6)])
        engine = build_engine(floor, score_file=self.score_file, power=10)

        engine.perform_action(ActionType.MOVE, "d")

        self.assertEqual(engine.player.position, Point(2, 1))
        self.assertEqual(engine.player.power, 15)
        self.assertFalse(engine.floor.items)
        self.assertTrue(
            any(effect.kind == EffectKind.MOVE_TRAIL for effect in engine.last_turn_effects)
        )

    def test_relay_restore_enters_dock_shop_and_descend_refills_power(self) -> None:
        floor = build_box_floor(relays=[Point(2, 1)])
        engine = build_engine(floor, score_file=self.score_file, power=12)

        engine.perform_action(ActionType.MOVE, "d")
        engine.perform_action(ActionType.INTERACT)
        self.assertEqual(engine.floor.objective.restored_relays, 1)
        self.assertEqual(engine.score, 100)
        self.assertEqual(engine.player.power, 16)
        self.assertTrue(any(effect.kind == EffectKind.RELAY for effect in engine.last_turn_effects))

        engine.perform_action(ActionType.MOVE, "a")
        engine.perform_action(ActionType.INTERACT)

        self.assertEqual(engine.mode, GameMode.DOCK_SHOP)
        self.assertGreaterEqual(engine.extraction_bonus, 250)

        engine.player.power = 7
        engine.descend()
        self.assertEqual(engine.floor_number, 2)
        self.assertEqual(engine.mode, GameMode.PLAYING)
        self.assertEqual(engine.player.power, MAX_POWER)

    def test_blackout_ends_run(self) -> None:
        floor = build_box_floor()
        engine = build_engine(floor, score_file=self.score_file, power=1)

        engine.perform_action(ActionType.MOVE, "d")

        self.assertEqual(engine.mode, GameMode.GAME_OVER)

    def test_hiss_cooldown_ticks_only_on_real_turns(self) -> None:
        floor = build_box_floor()
        engine = build_engine(floor, score_file=self.score_file, power=10)

        engine.perform_action(ActionType.HISS)
        self.assertEqual(engine.player.hiss_cooldown, 4)

        engine.perform_action(ActionType.HISS)
        self.assertEqual(engine.player.hiss_cooldown, 4)

        engine.perform_action(ActionType.MOVE, "d")
        self.assertEqual(engine.player.hiss_cooldown, 3)

    def test_hiss_marks_adjacent_crawler_with_effect(self) -> None:
        floor = build_box_floor(enemies=[crawler(Point(2, 1))])
        engine = build_engine(floor, score_file=self.score_file, power=10)

        engine.perform_action(ActionType.HISS)

        self.assertEqual(engine.floor.enemies[0].alert, AlertState.SCARED)
        self.assertTrue(any(effect.kind == EffectKind.HISS for effect in engine.last_turn_effects))

    def test_mimic_reveal_creates_enemy_and_flash_effect(self) -> None:
        floor = build_box_floor(items=[mimic(Point(2, 1))])
        engine = build_engine(floor, score_file=self.score_file, power=10)

        engine.perform_action(ActionType.MOVE, "d")

        self.assertEqual(engine.player.position, Point(1, 1))
        self.assertTrue(any(enemy.enemy_type.name == "MIMIC" for enemy in engine.floor.enemies))
        self.assertEqual(engine.current_noise, 4)
        self.assertTrue(any(effect.kind == EffectKind.MIMIC for effect in engine.last_turn_effects))

    def test_alert_meter_rises_and_quiet_turns_decay_it(self) -> None:
        floor = build_box_floor(width=9, height=9)
        engine = build_engine(floor, score_file=self.score_file, power=20)

        engine.perform_action(ActionType.KNOCK, "d")
        engine.perform_action(ActionType.KNOCK, "d")

        self.assertEqual(engine.ship_alert, 11)
        self.assertTrue(any("HUNT" in line for line in engine.logs))
        self.assertTrue(any("SWEEP" in line for line in engine.logs))

        for _ in range(12):
            engine.perform_action(ActionType.WAIT)

        self.assertLess(engine.ship_alert, 11)
        self.assertTrue(
            any("drops to HUNT" in line or "settles to CALM" in line for line in engine.logs)
        )

    def test_sweep_transition_spawns_reinforcement_and_redirects_enemies(self) -> None:
        floor = build_box_floor(
            width=11, height=11, enemies=[crawler(Point(8, 8)), stalker(Point(8, 6))]
        )
        engine = build_engine(floor, score_file=self.score_file, power=20)
        engine.ship_alert = 8
        engine.heard_position = Point(5, 5)

        enemy_count = len(engine.floor.enemies)
        engine._adjust_ship_alert(1)

        self.assertEqual(engine.ship_alert, 9)
        self.assertEqual(len(engine.floor.enemies), enemy_count + 1)
        self.assertTrue(engine.floor_sweep_spawned)
        for enemy in engine.floor.enemies:
            self.assertEqual(enemy.alert, AlertState.INVESTIGATING)
            self.assertEqual(enemy.last_known_player, Point(5, 5))

    def test_knock_projects_farther_and_sets_two_phase_decoy(self) -> None:
        floor = build_box_floor(
            width=11, height=9, enemies=[crawler(Point(8, 1)), stalker(Point(8, 5))]
        )
        engine = build_engine(floor, score_file=self.score_file, power=20)

        engine.perform_action(ActionType.KNOCK, "d")

        self.assertEqual(engine.heard_position, Point(6, 1))
        self.assertEqual(engine.current_noise, 4)
        self.assertEqual(engine.decoy_target, Point(6, 1))
        self.assertEqual(engine.decoy_turns, 1)
        self.assertTrue(any(effect.kind == EffectKind.KNOCK for effect in engine.last_turn_effects))
        self.assertEqual(engine.floor.enemies[0].alert, AlertState.INVESTIGATING)
        self.assertEqual(engine.floor.enemies[1].alert, AlertState.INVESTIGATING)

        engine.perform_action(ActionType.WAIT)
        self.assertIsNone(engine.decoy_target)

    def test_hide_is_stronger_and_breaks_distant_stalker_chase(self) -> None:
        floor = build_box_floor(
            width=9, height=9, enemies=[stalker(Point(6, 1), alert=AlertState.CHASING)]
        )
        engine = build_engine(floor, score_file=self.score_file, power=12)
        engine.current_noise = 5
        engine.ship_alert = 4

        engine.perform_action(ActionType.HIDE)

        self.assertEqual(engine.player.hidden_turns, 1)
        self.assertEqual(engine.current_noise, 1)
        self.assertEqual(engine.ship_alert, 2)
        self.assertEqual(engine.floor.enemies[0].alert, AlertState.INVESTIGATING)
        self.assertTrue(any(effect.kind == EffectKind.HIDE for effect in engine.last_turn_effects))

    def test_deep_hide_lasts_three_enemy_phases_total(self) -> None:
        floor = build_box_floor(width=9, height=9, enemies=[stalker(Point(6, 1))])
        engine = build_engine(floor, score_file=self.score_file, power=12)
        engine.player.modules.add(ModuleType.DEEP_HIDE)

        engine.perform_action(ActionType.HIDE)
        self.assertEqual(engine.player.hidden_turns, 2)

        engine.perform_action(ActionType.WAIT)
        self.assertEqual(engine.player.hidden_turns, 1)

        engine.perform_action(ActionType.WAIT)
        self.assertEqual(engine.player.hidden_turns, 0)

    def test_relay_boost_module_increases_relay_score(self) -> None:
        floor = build_box_floor(relays=[Point(2, 1)])
        engine = build_engine(floor, score_file=self.score_file, power=12)
        engine.player.modules.add(ModuleType.RELAY_BOOST)

        engine.perform_action(ActionType.MOVE, "d")
        engine.perform_action(ActionType.INTERACT)

        self.assertEqual(engine.score, 150)
        self.assertEqual(engine.player.power, 16)

    def test_thermal_lining_cancels_heat_cost(self) -> None:
        floor = build_box_floor(heat=[Point(2, 1)])
        engine = build_engine(floor, score_file=self.score_file, power=10)
        engine.player.modules.add(ModuleType.THERMAL_LINING)

        engine.perform_action(ActionType.MOVE, "d")

        self.assertEqual(engine.player.power, 9)

    def test_signal_filter_blocks_ambush_outcome(self) -> None:
        floor = build_box_floor()
        engine = build_engine(floor, score_file=self.score_file, power=12)
        engine.player.modules.add(ModuleType.SIGNAL_FILTER)
        engine.current_noise = 2
        engine.ship_alert = 2
        engine.rng = FakeRNG(62)

        engine._resolve_signal()

        self.assertFalse(engine.floor.enemies)
        self.assertTrue(any("Static" in line for line in engine.logs))

    def test_signal_ambush_never_spawns_adjacent_for_same_turn_death(self) -> None:
        floor = build_box_floor(width=4, height=4, items=[signal(Point(2, 1))])
        engine = build_engine(floor, score_file=self.score_file, power=12)
        engine.player.position = Point(2, 1)
        engine.rng = FakeRNG(68)

        spent_turn = engine.perform_action(ActionType.INTERACT)

        self.assertTrue(spent_turn)
        self.assertEqual(engine.mode, GameMode.PLAYING)
        self.assertTrue(engine.floor.enemies)
        self.assertTrue(
            all(
                enemy.home is not None and enemy.home.distance(engine.player.position) > 1
                for enemy in engine.floor.enemies
            )
        )

    def test_signal_ambush_falls_back_when_only_adjacent_spawn_exists(self) -> None:
        floor = build_box_floor(width=4, height=4, items=[signal(Point(2, 1))])
        floor.tiles[2][1] = floor.tiles[0][0].__class__.WALL
        floor.tiles[2][2] = floor.tiles[0][0].__class__.WALL
        engine = build_engine(floor, score_file=self.score_file, power=12)
        engine.player.position = Point(2, 1)
        engine.rng = FakeRNG(68)

        spent_turn = engine.perform_action(ActionType.INTERACT)

        self.assertTrue(spent_turn)
        self.assertEqual(engine.mode, GameMode.PLAYING)
        self.assertFalse(engine.floor.enemies)
        self.assertTrue(any("nothing can get a clean angle" in line for line in engine.logs))

    def test_threat_sink_reduces_alert_on_relay_restore(self) -> None:
        floor = build_box_floor(relays=[Point(2, 1)])
        engine = build_engine(floor, score_file=self.score_file, power=12)
        engine.player.modules.add(ModuleType.THREAT_SINK)
        engine.ship_alert = 5

        engine.perform_action(ActionType.MOVE, "d")
        engine.perform_action(ActionType.INTERACT)

        self.assertEqual(engine.ship_alert, 3)

    def test_dock_shop_handles_affordability_and_single_purchase(self) -> None:
        floor = build_box_floor(relays=[Point(2, 1)])
        engine = build_engine(floor, score_file=self.score_file, power=20)
        engine.player.scrap = 10
        engine.player.modules.update(
            {
                ModuleType.LIGHT_PAWS,
                ModuleType.RELAY_BOOST,
                ModuleType.THERMAL_LINING,
                ModuleType.DEEP_HIDE,
                ModuleType.SIGNAL_FILTER,
                ModuleType.THREAT_SINK,
            }
        )

        engine.perform_action(ActionType.MOVE, "d")
        engine.perform_action(ActionType.INTERACT)
        engine.perform_action(ActionType.MOVE, "a")
        engine.perform_action(ActionType.INTERACT)

        self.assertEqual(engine.mode, GameMode.DOCK_SHOP)
        self.assertEqual(len(engine.dock_offers), 3)
        self.assertIn("BUY", " ".join(engine.summary_lines()))

        self.assertTrue(engine.buy_dock_offer(1))
        self.assertFalse(engine.buy_dock_offer(2))
        self.assertIn(ModuleType.QUIET_HIDE, engine.player.modules)
        self.assertEqual(engine.player.scrap, 6)

    def test_signal_battery_cache_uses_rebalanced_range(self) -> None:
        floor = build_box_floor()
        engine = build_engine(floor, score_file=self.score_file, power=12)
        engine.rng = FakeRNG(1, 10)

        engine._resolve_signal()

        self.assertEqual(engine.player.power, 22)
        self.assertTrue(any("Power +10" in line for line in engine.logs))

    def test_overcharge_cell_increases_capacity_and_next_floor_refills_to_it(self) -> None:
        floor = build_box_floor(relays=[Point(2, 1)])
        engine = build_engine(floor, score_file=self.score_file, power=20)
        engine.player.scrap = 6
        engine.player.modules.update(set(ModuleType))

        engine.perform_action(ActionType.MOVE, "d")
        engine.perform_action(ActionType.INTERACT)
        engine.perform_action(ActionType.MOVE, "a")
        engine.perform_action(ActionType.INTERACT)

        before = engine.player.power
        before_capacity = engine.player.power_capacity
        self.assertTrue(engine.buy_dock_offer(1))
        self.assertEqual(engine.player.power, before + 10)
        self.assertEqual(engine.player.power_capacity, before_capacity + 10)
        self.assertEqual(engine.player.scrap, 4)
        engine.player.power = 3
        engine.descend()
        self.assertEqual(engine.player.power, before_capacity + 10)

    def test_invalid_direction_returns_false_without_throwing_or_spending_turn(self) -> None:
        floor = build_box_floor()
        engine = build_engine(floor, score_file=self.score_file, power=20)
        turn_count = engine.turn_count

        spent_turn = engine.perform_action(ActionType.MOVE, "northwest")

        self.assertFalse(spent_turn)
        self.assertEqual(engine.turn_count, turn_count)
        self.assertTrue(any("Unknown direction" in line for line in engine.logs))

    def test_public_preview_queries_replace_private_frontend_calls(self) -> None:
        floor = build_box_floor(width=11, height=9)
        engine = build_engine(floor, score_file=self.score_file, power=20)

        knock_paths = engine.preview_knock_paths()
        pounce_targets = engine.preview_pounce_targets()

        self.assertEqual(set(knock_paths), {"w", "a", "s", "d"})
        self.assertTrue(knock_paths["d"])
        self.assertIn("d", pounce_targets)
        self.assertIsNone(engine.preview_knock_path("northwest"))
        self.assertIsNone(engine.preview_pounce_target("northwest"))

    def test_render_state_uses_typed_render_contract(self) -> None:
        floor = build_box_floor(
            width=9, height=7, enemies=[crawler(Point(3, 1)), stalker(Point(4, 1))]
        )
        engine = build_engine(floor, score_file=self.score_file, power=20)

        state = engine.get_render_state()
        crawler_cell = state.map_rows[1][3]
        stalker_cell = state.map_rows[1][4]

        self.assertEqual(crawler_cell.char, "◍")
        self.assertEqual(stalker_cell.char, "▲")
        self.assertEqual(crawler_cell.color, CellColor.ENEMY_RED)
        self.assertEqual(stalker_cell.color, CellColor.ENEMY_RED)
        self.assertTrue(crawler_cell.dim)
        self.assertFalse(crawler_cell.bold)
        self.assertTrue(stalker_cell.bold)
        self.assertEqual(state.hud.score, engine.score)
        self.assertEqual(state.hud.alert_stage, engine.ship_alert_stage)
        self.assertEqual(state.status_bars[0].color, BarColor.POWER)
        self.assertEqual(state.sidebar.objective.title, "Objective")
        self.assertEqual(state.overlay.title, "")

    def test_render_state_can_request_help_backdrop(self) -> None:
        floor = build_box_floor()
        engine = build_engine(floor, score_file=self.score_file, power=10)

        state = engine.get_render_state(OverlayState(title="VOIDCAT // HELP", backdrop=True))

        self.assertEqual(state.overlay.title, "VOIDCAT // HELP")
        self.assertTrue(state.overlay.backdrop)

    def test_footer_mentions_space_wait_and_hidden_player_has_unique_render_color(self) -> None:
        floor = build_box_floor()
        engine = build_engine(floor, score_file=self.score_file, power=10)
        engine.player.hidden_turns = 1

        state = engine.get_render_state()
        player_cell = state.map_rows[1][1]

        self.assertIn("Space wait", state.footer)
        self.assertEqual(player_cell.color, CellColor.PLAYER_HIDDEN)

    def test_sidebar_sections_include_tools_and_guidance(self) -> None:
        floor = build_box_floor()
        engine = build_engine(floor, score_file=self.score_file, power=10)
        engine.current_noise = 6

        state = engine.get_render_state()
        titles = [
            state.sidebar.objective.title,
            state.sidebar.tools.title,
            state.sidebar.guidance.title,
            state.sidebar.modules.title,
        ]

        self.assertIn("Tools", titles)
        self.assertIn("Guidance", titles)

    def test_generate_dock_offers_cover_distinct_build_paths(self) -> None:
        engine = GameEngine(seed=13, score_file=self.score_file)

        offers = engine.progression.generate_dock_offers()

        self.assertEqual(len(offers), 3)
        self.assertEqual({offer.path for offer in offers}, set(BuildPath))
        self.assertTrue(all(offer.tagline for offer in offers))

    def test_end_run_records_build_path_highlights_and_share_line(self) -> None:
        floor = build_box_floor()
        engine = build_engine(floor, score_file=self.score_file, power=12)
        engine.seed = 4242
        engine.daily_run_active = True
        engine.player.modules.add(ModuleType.QUIET_HIDE)
        engine.stats.signals_touched = 3
        engine.stats.knocks_used = 4
        engine.stats.hides_used = 3
        engine.stats.quiet_turns = 7
        engine.stats.max_alert = 9

        engine.run_records.end_run("You made the dock.", extracted=True)

        self.assertTrue(any("Build: Stealth Route" in line for line in engine.game_over_lines))
        self.assertTrue(any("Highlights:" in line for line in engine.game_over_lines))
        self.assertTrue(any("Share:" in line for line in engine.game_over_lines))
        self.assertEqual(engine.scores[0].seed, 4242)
        self.assertTrue(engine.scores[0].daily_run)
        self.assertEqual(engine.scores[0].build_path, "Stealth Route")

    def test_failed_score_save_sets_persistence_warning(self) -> None:
        score_dir = Path(self.tempdir.name)
        floor = build_box_floor()
        engine = build_engine(floor, score_file=score_dir, power=1)

        engine.perform_action(ActionType.MOVE, "d")

        self.assertEqual(engine.mode, GameMode.GAME_OVER)
        self.assertIsNotNone(engine.persistence_warning)

    def test_daily_run_summary_and_low_light_visibility_hooks_exist(self) -> None:
        floor = build_box_floor(width=11, height=11)
        floor.condition = FloorCondition.LOW_LIGHT
        engine = build_engine(floor, score_file=self.score_file, power=12)
        engine.daily_run_active = True
        engine.seed = engine.daily_seed()

        engine._update_visibility()
        visible_count = len(engine.floor.visible)

        self.assertLess(visible_count, 11 * 11)

        engine.run_records.end_run("Caught by the sweep.", extracted=False)

        self.assertTrue(any("Daily Run" in line for line in engine.game_over_lines))
        self.assertTrue(any("Seed:" in line for line in engine.game_over_lines))


if __name__ == "__main__":
    unittest.main()
