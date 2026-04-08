from __future__ import annotations

import random
import unittest

from tests.helpers import build_box_floor, crawler, stalker
from voidcat.ai import advance_enemy
from voidcat.models import AlertState, EnemyType, Point, ShipAlertStage


class AITests(unittest.TestCase):
    def test_crawler_moves_toward_noise(self) -> None:
        floor = build_box_floor(enemies=[crawler(Point(5, 3))])
        enemy = floor.enemies[0]

        turn = advance_enemy(
            enemy,
            floor,
            Point(1, 3),
            player_hidden=False,
            ship_alert_stage=ShipAlertStage.CALM,
            noise=5,
            noise_pos=Point(3, 3),
            decoy_target=None,
            occupied=set(),
            rng=random.Random(3),
        )

        self.assertEqual(turn.destination, Point(4, 3))
        self.assertEqual(enemy.alert, AlertState.INVESTIGATING)

    def test_stalker_chases_visible_player(self) -> None:
        floor = build_box_floor(enemies=[stalker(Point(5, 1))])
        enemy = floor.enemies[0]

        turn = advance_enemy(
            enemy,
            floor,
            Point(1, 1),
            player_hidden=False,
            ship_alert_stage=ShipAlertStage.CALM,
            noise=0,
            noise_pos=None,
            decoy_target=None,
            occupied=set(),
            rng=random.Random(3),
        )

        self.assertEqual(turn.destination, Point(4, 1))
        self.assertEqual(enemy.alert, AlertState.CHASING)

    def test_hide_breaks_stalker_lock_when_not_adjacent(self) -> None:
        floor = build_box_floor(enemies=[stalker(Point(4, 1), alert=AlertState.CHASING)])
        enemy = floor.enemies[0]
        enemy.last_known_player = Point(1, 1)

        turn = advance_enemy(
            enemy,
            floor,
            Point(1, 1),
            player_hidden=True,
            ship_alert_stage=ShipAlertStage.CALM,
            noise=0,
            noise_pos=None,
            decoy_target=None,
            occupied=set(),
            rng=random.Random(5),
        )

        self.assertEqual(enemy.alert, AlertState.INVESTIGATING)
        self.assertFalse(turn.attacked)

    def test_mimic_uses_crawler_sound_logic(self) -> None:
        floor = build_box_floor()
        enemy = crawler(Point(5, 3))
        enemy.enemy_type = EnemyType.MIMIC

        turn = advance_enemy(
            enemy,
            floor,
            Point(1, 3),
            player_hidden=False,
            ship_alert_stage=ShipAlertStage.CALM,
            noise=6,
            noise_pos=Point(3, 3),
            decoy_target=None,
            occupied=set(),
            rng=random.Random(9),
        )

        self.assertEqual(turn.destination, Point(4, 3))

    def test_hunt_stage_makes_stalker_react_to_lower_noise(self) -> None:
        floor = build_box_floor(width=13, height=7, enemies=[stalker(Point(10, 3))])
        enemy = floor.enemies[0]

        turn = advance_enemy(
            enemy,
            floor,
            Point(1, 1),
            player_hidden=False,
            ship_alert_stage=ShipAlertStage.HUNT,
            noise=2,
            noise_pos=Point(6, 3),
            decoy_target=None,
            occupied=set(),
            rng=random.Random(4),
        )

        self.assertEqual(enemy.alert, AlertState.INVESTIGATING)
        self.assertEqual(turn.destination, Point(9, 3))

    def test_decoy_target_reprioritizes_crawler_and_stalker(self) -> None:
        floor = build_box_floor(
            width=13, height=7, enemies=[crawler(Point(10, 3)), stalker(Point(10, 1))]
        )

        crawler_turn = advance_enemy(
            floor.enemies[0],
            floor,
            Point(1, 1),
            player_hidden=False,
            ship_alert_stage=ShipAlertStage.CALM,
            noise=0,
            noise_pos=None,
            decoy_target=Point(6, 3),
            occupied={floor.enemies[1].position},
            rng=random.Random(4),
        )
        stalker_turn = advance_enemy(
            floor.enemies[1],
            floor,
            Point(1, 1),
            player_hidden=False,
            ship_alert_stage=ShipAlertStage.CALM,
            noise=0,
            noise_pos=None,
            decoy_target=Point(6, 3),
            occupied={floor.enemies[0].position},
            rng=random.Random(4),
        )

        self.assertEqual(crawler_turn.destination, Point(9, 3))
        self.assertEqual(stalker_turn.destination, Point(9, 1))
        self.assertEqual(floor.enemies[1].alert, AlertState.INVESTIGATING)


if __name__ == "__main__":
    unittest.main()
