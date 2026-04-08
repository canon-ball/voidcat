from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.helpers import build_box_floor, build_engine, mimic, scrap, signal, stalker
from voidcat.models import (
    ActionType,
    AlertState,
    BuildPath,
    DockOffer,
    EnemyType,
    FloorCondition,
    GameMode,
    ModuleType,
    Point,
    ShipAlertStage,
    TileType,
)


class StaticRNG:
    def __init__(self, *, roll: int = 1, random_value: float = 0.0) -> None:
        self.roll = roll
        self.random_value = random_value

    def randint(self, start: int, end: int) -> int:
        return min(max(self.roll, start), end)

    def choice(self, values):
        return values[0]

    def random(self) -> float:
        return self.random_value


class RulesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.score_file = Path(self.tempdir.name) / "scores.json"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_gameplay_perform_action_guards_and_move_failures(self) -> None:
        engine = build_engine(build_box_floor(), score_file=self.score_file, power=10)

        engine.mode = GameMode.GAME_OVER
        self.assertFalse(engine.gameplay.perform_action(ActionType.WAIT))

        engine.mode = GameMode.PLAYING
        engine.floor = None
        self.assertFalse(engine.gameplay.perform_action(ActionType.WAIT))

        engine = build_engine(build_box_floor(), score_file=self.score_file, power=10)
        self.assertFalse(engine.gameplay.perform_action(ActionType.MOVE))
        self.assertIn("Choose a direction.", list(engine.logs))

        engine.player.position = Point(0, 0)
        self.assertFalse(engine.gameplay.move("w"))
        self.assertTrue(any("Metal. Wall. Whiskers." in line for line in engine.logs))

        floor = build_box_floor(width=6, height=6)
        floor.set_tile(Point(2, 1), TileType.WALL)
        engine = build_engine(floor, score_file=self.score_file, power=10)
        self.assertFalse(engine.gameplay.move("d"))
        self.assertTrue(any("vent wall" in line for line in engine.logs))

        floor = build_box_floor(width=6, height=6, enemies=[stalker(Point(2, 1))])
        engine = build_engine(floor, score_file=self.score_file, power=10)
        self.assertTrue(engine.gameplay.move("d"))
        self.assertEqual(engine.mode, GameMode.GAME_OVER)

    def test_gameplay_pounce_hiss_collect_and_spawn_helpers_cover_branchy_paths(self) -> None:
        floor = build_box_floor(
            width=8, height=8, items=[mimic(Point(3, 1)), scrap(Point(2, 1), 2)]
        )
        floor.set_tile(Point(4, 1), TileType.HEAT)
        engine = build_engine(floor, score_file=self.score_file, power=12)

        engine.player.hiss_cooldown = 1
        self.assertFalse(engine.gameplay.hiss())
        engine.player.hiss_cooldown = 0
        self.assertTrue(engine.gameplay.hiss())
        self.assertTrue(any("rings down the vent" in line for line in engine.logs))

        engine.player.pounce_cooldown = 2
        self.assertFalse(engine.gameplay.pounce("d"))
        engine.player.pounce_cooldown = 0
        self.assertFalse(engine.gameplay.pounce("northwest"))
        self.assertFalse(engine.gameplay.pounce("w"))
        self.assertTrue(any("No place to land that pounce." in line for line in engine.logs))

        engine.player.position = Point(1, 1)
        self.assertTrue(engine.gameplay.pounce("d"))
        self.assertTrue(any(enemy.enemy_type == EnemyType.MIMIC for enemy in engine.floor.enemies))

        heat_floor = build_box_floor(width=8, height=8, heat=[Point(3, 1)])
        engine = build_engine(heat_floor, score_file=self.score_file, power=12)
        engine.player.position = Point(1, 1)
        self.assertTrue(engine.gameplay.pounce("d"))
        self.assertTrue(any("wave of trapped heat" in line for line in engine.logs))

        scrap_floor = build_box_floor(width=6, height=6, items=[scrap(Point(1, 1), 3)])
        engine = build_engine(scrap_floor, score_file=self.score_file, power=10)
        engine.gameplay.collect_items(Point(1, 1))
        self.assertEqual(engine.player.scrap, 3)
        self.assertEqual(engine.score, 45)

        engine.floor = None
        self.assertFalse(engine.gameplay.spawn_enemy_near_player(min_distance=2))

        tight_floor = build_box_floor(width=4, height=4)
        engine = build_engine(tight_floor, score_file=self.score_file, power=10)
        engine.floor.tiles[1][2] = TileType.WALL
        engine.floor.tiles[2][1] = TileType.WALL
        self.assertFalse(engine.gameplay.spawn_enemy_near_player(min_distance=3))

        wide_floor = build_box_floor(width=10, height=10)
        engine = build_engine(wide_floor, score_file=self.score_file, power=10)
        engine.floor_number = 3
        engine.rng = StaticRNG(random_value=0.0)
        self.assertTrue(engine.gameplay.spawn_enemy_near_player(min_distance=2))
        self.assertEqual(engine.floor.enemies[-1].enemy_type, EnemyType.STALKER)

    def test_gameplay_enemy_alert_visibility_and_reset_helpers(self) -> None:
        engine = build_engine(
            build_box_floor(width=10, height=10), score_file=self.score_file, power=10
        )
        engine.gameplay.adjust_ship_alert(0)
        self.assertEqual(engine.ship_alert, 0)
        self.assertEqual(
            engine.gameplay.alert_stage_message(ShipAlertStage.CALM, rising=True),
            "Ship alert shifts.",
        )
        self.assertEqual(
            engine.gameplay.alert_stage_message(ShipAlertStage.SWEEP, rising=False),
            "Ship alert eases.",
        )

        engine.floor = None
        self.assertFalse(engine.gameplay.spawn_sweep_reinforcement())
        engine.gameplay.trigger_sweep_response()
        engine.gameplay.run_enemy_phase()
        engine.gameplay.update_visibility()
        engine.gameplay.reveal_mimic(mimic(Point(2, 2)))

        floor = build_box_floor(width=7, height=7, enemies=[stalker(Point(5, 1))])
        engine = build_engine(floor, score_file=self.score_file, power=10)
        engine.current_noise = 7
        engine.generated_noise_this_turn = False
        engine.player.hidden_turns = 1
        engine.decoy_target = Point(4, 1)
        engine.decoy_turns = 1
        engine.gameplay.finish_turn()
        self.assertEqual(engine.stats.loud_turns, 1)
        self.assertEqual(engine.player.hidden_turns, 0)
        self.assertIsNone(engine.decoy_target)

        engine.player.hiss_cooldown = 2
        engine.player.pounce_cooldown = 2
        engine.gameplay.tick_cooldowns()
        self.assertEqual(engine.player.hiss_cooldown, 1)
        self.assertEqual(engine.player.pounce_cooldown, 1)

        engine.noise_history.clear()
        engine.gameplay.reset_noise_history()
        self.assertEqual(len(engine.noise_history), 8)

        engine.floor.condition = FloorCondition.TRAINING
        engine.gameplay.update_visibility()
        self.assertIn(engine.player.position, engine.floor.visible)

        with patch(
            "voidcat.gameplay.advance_enemy",
            return_value=SimpleNamespace(attacked=True, destination=engine.player.position),
        ):
            engine.gameplay.run_enemy_phase()
        self.assertEqual(engine.mode, GameMode.GAME_OVER)

        chasing_floor = build_box_floor(width=7, height=7, enemies=[stalker(Point(5, 1))])
        engine = build_engine(chasing_floor, score_file=self.score_file, power=10)
        def chase_turn(enemy, *args, **kwargs):
            enemy.alert = AlertState.CHASING
            return SimpleNamespace(attacked=False, destination=Point(4, 1))

        with patch("voidcat.gameplay.advance_enemy", side_effect=chase_turn):
            engine.gameplay.run_enemy_phase()
        self.assertTrue(
            any(effect.kind.name == "ENEMY_SPOT" for effect in engine.last_turn_effects)
        )

    def test_progression_guards_signal_outcomes_and_offer_generation_paths(self) -> None:
        engine = build_engine(build_box_floor(), score_file=self.score_file, power=10)
        engine.mode = GameMode.PLAYING
        before_floor = engine.floor_number
        engine.progression.descend()
        engine.progression.finish_run()
        self.assertEqual(engine.floor_number, before_floor)

        self.assertFalse(engine.progression.buy_dock_offer(1))
        engine.mode = GameMode.DOCK_SHOP
        self.assertFalse(engine.progression.buy_dock_offer(0))
        engine.dock_offers = [DockOffer(label="Quiet Hide", cost=5, module=ModuleType.QUIET_HIDE)]
        self.assertFalse(engine.progression.buy_dock_offer(1))
        self.assertTrue(any("Not enough scrap" in line for line in engine.logs))

        engine.floor = None
        self.assertFalse(engine.progression.interact())

        floor = build_box_floor(relays=[Point(2, 1)])
        engine = build_engine(floor, score_file=self.score_file, power=10)
        engine.player.position = Point(2, 1)
        engine.restored_relays.add(Point(2, 1))
        self.assertFalse(engine.progression.interact())
        self.assertTrue(any("already humming" in line for line in engine.logs))

        floor = build_box_floor(relays=[Point(3, 1)])
        engine = build_engine(floor, score_file=self.score_file, power=10)
        self.assertFalse(engine.progression.interact())
        self.assertTrue(any("dock stays dark" in line for line in engine.logs))

        empty_floor = build_box_floor(width=6, height=6)
        empty_floor.tiles[1][1] = TileType.FLOOR
        engine = build_engine(empty_floor, score_file=self.score_file, power=10)
        self.assertFalse(engine.progression.interact())
        self.assertTrue(any("Nothing here" in line for line in engine.logs))

        signal_floor = build_box_floor(width=6, height=6, items=[signal(Point(1, 1))])
        engine = build_engine(signal_floor, score_file=self.score_file, power=10)
        engine.rng = StaticRNG(roll=31)
        engine.progression.resolve_signal()
        self.assertTrue(any("scrap stash" in line for line in engine.logs))

        engine = build_engine(build_box_floor(), score_file=self.score_file, power=10)
        engine.rng = StaticRNG(roll=60)
        engine.player.modules = set(ModuleType)
        engine.progression.resolve_signal()
        self.assertTrue(any("Emergency charge" in line for line in engine.logs))

        self.assertIsNone(engine.progression.award_module())
        self.assertTrue(any("Emergency charge" in line for line in engine.logs))

        engine.player.modules = set(ModuleType)
        engine.stats.signals_touched = 4
        offers = engine.progression.generate_dock_offers()
        self.assertEqual(len(offers), 3)
        self.assertTrue(all(offer.label == "Overcharge Cell" for offer in offers))
        self.assertTrue(all(offer.path == BuildPath.SCAVENGER for offer in offers))
        self.assertEqual(engine.progression.module_cost(ModuleType.SIGNAL_FILTER), 5)
        self.assertEqual(engine.progression.module_cost(ModuleType.QUIET_HIDE), 4)

    def test_progression_start_floor_logs_warning_and_preserves_power_when_requested(self) -> None:
        engine = build_engine(build_box_floor(), score_file=self.score_file, power=10)
        custom_floor = build_box_floor(width=8, height=8)
        custom_floor.condition = FloorCondition.HOT_DECK
        engine.player.power = 7
        engine.player.power_capacity = 20
        engine.floor_number = 2
        engine.persistence_warning = "disk full"

        with (
            patch.object(
                engine.progression,
                "pick_floor_condition",
                return_value=FloorCondition.HOT_DECK,
            ),
            patch("voidcat.progression.generate_floor", return_value=custom_floor),
        ):
            engine.progression.start_floor(reset_power=False)

        self.assertEqual(engine.player.power, 7)
        self.assertTrue(any("Floor 2." in line for line in engine.logs))
        self.assertTrue(any("Score save disabled: disk full" in line for line in engine.logs))
        self.assertEqual(engine.floor_condition_history[-1], FloorCondition.HOT_DECK)


if __name__ == "__main__":
    unittest.main()
