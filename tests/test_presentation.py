from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.helpers import battery, build_box_floor, build_engine, crawler
from voidcat.engine import GameEngine
from voidcat.models import (
    AlertState,
    BuildPath,
    CellColor,
    DockOffer,
    FloorCondition,
    GameMode,
    Item,
    ItemType,
    ModuleType,
    OverlayState,
    Point,
)


class PresentationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _score_file(self) -> Path:
        return Path(self.tempdir.name) / "scores.json"

    def test_get_render_state_requires_floor_but_cell_query_handles_missing_floor(self) -> None:
        engine = GameEngine(seed=5, score_file=self._score_file())
        engine.floor = None

        with self.assertRaises(RuntimeError):
            engine.presenter.get_render_state()

        self.assertEqual(
            engine.presenter.cell_for_point(Point(0, 0)).color,
            CellColor.VOID,
        )

    def test_cell_for_point_covers_visibility_items_heard_enemies_and_relays(self) -> None:
        floor = build_box_floor(
            width=9,
            height=7,
            relays=[Point(2, 1)],
            items=[
                battery(Point(3, 1), amount=9),
                Item(ItemType.MIMIC, Point(4, 1), revealed=False),
            ],
            enemies=[crawler(Point(5, 1))],
            heat=[Point(6, 1)],
        )
        engine = build_engine(floor, score_file=self._score_file(), power=12)
        presenter = engine.presenter

        floor.explored.clear()
        floor.visible.clear()
        self.assertEqual(presenter.cell_for_point(Point(7, 5)).color, CellColor.VOID)

        floor.explored = {Point(7, 5)}
        self.assertEqual(presenter.cell_for_point(Point(7, 5)).color, CellColor.FOG)

        floor.visible = set(floor.iter_points())
        self.assertEqual(presenter.cell_for_point(Point(3, 1)).color, CellColor.BATTERY)
        self.assertEqual(presenter.cell_for_point(Point(4, 1)).char, "▣")

        floor.enemies[0].alert = AlertState.SCARED
        self.assertEqual(presenter.cell_for_point(Point(5, 1)).color, CellColor.ENEMY_RED_COOL)

        engine.heard_position = Point(5, 2)
        engine.current_noise = 4
        self.assertEqual(presenter.cell_for_point(Point(5, 2)).color, CellColor.HEARD)

        engine.restored_relays = {Point(2, 1)}
        floor.objective.restored_relays = 1
        self.assertEqual(presenter.cell_for_point(Point(2, 1)).color, CellColor.RELAY_RESTORED)
        self.assertEqual(presenter.cell_for_point(Point(6, 1)).color, CellColor.HEAT)
        self.assertEqual(presenter.cell_for_point(floor.dock).color, CellColor.PLAYER)

    def test_guidance_lines_and_padded_noise_history_cover_state_variants(self) -> None:
        engine = build_engine(build_box_floor(), score_file=self._score_file(), power=10)
        presenter = engine.presenter

        engine.decoy_target = Point(4, 4)
        engine.decoy_turns = 2
        self.assertIn("Decoy live 2", presenter.guidance_lines()[0])

        engine.decoy_target = None
        engine.player.hidden_turns = 2
        self.assertIn("Hidden 2", presenter.guidance_lines()[0])

        engine.player.hidden_turns = 0
        engine.ship_alert = 9
        self.assertIn("Sweep is active.", presenter.guidance_lines()[0])

        engine.ship_alert = 0
        engine.current_noise = 7
        self.assertIn("Noise is hot.", presenter.guidance_lines()[0])

        engine.current_noise = 0
        engine.player.hiss_cooldown = 0
        self.assertIn("Hiss hits adjacent crawlers", presenter.guidance_lines()[0])

        engine.player.hiss_cooldown = 1
        engine.player.pounce_cooldown = 0
        self.assertIn("Pounce jumps 1-2 tiles.", presenter.guidance_lines()[0])

        engine.player.pounce_cooldown = 2
        self.assertIn("Knock before open crossings.", presenter.guidance_lines()[0])

        engine.noise_history.clear()
        engine.noise_history.extend([1, 2, 3])
        self.assertEqual(presenter.padded_noise_history()[-3:], [1, 2, 3])
        self.assertEqual(len(presenter.status_bars()), 3)

    def test_render_state_exposes_floor_condition_seed_markers_and_enemy_intents(self) -> None:
        floor = build_box_floor(
            width=9,
            height=7,
            dock=Point(1, 1),
            relays=[Point(2, 1)],
            items=[Item(ItemType.SIGNAL, Point(3, 1)), Item(ItemType.SCRAP, Point(4, 1), amount=2)],
            enemies=[crawler(Point(6, 1))],
        )
        floor.condition = FloorCondition.SIGNAL_SURGE
        engine = build_engine(floor, score_file=self._score_file(), power=11)
        engine.seed = 4242
        engine.daily_run_active = True
        floor.visible = set(floor.iter_points())
        floor.explored = set(floor.iter_points())

        state = engine.presenter.get_render_state()

        self.assertEqual(state.hud.condition, FloorCondition.SIGNAL_SURGE.label)
        self.assertIn("Daily", state.hud.seed_label)
        self.assertEqual(state.hud.build_path, "Adaptive Route")
        self.assertTrue(state.markers)
        self.assertTrue(any(marker.label == "Signal" for marker in state.markers))
        self.assertTrue(state.enemy_intents)
        self.assertTrue(state.threat_cells)
        self.assertEqual(state.enemy_intents[0].origin, Point(6, 1))

    def test_summary_lines_cover_dock_and_game_over_views(self) -> None:
        engine = build_engine(build_box_floor(), score_file=self._score_file(), power=10)
        engine.mode = GameMode.DOCK_SHOP
        engine.player.scrap = 3
        engine.extraction_bonus = 250
        engine.dock_offers = [
            DockOffer("Quiet Hide", 2, module=ModuleType.QUIET_HIDE, path=BuildPath.STEALTH),
            DockOffer("Threat Sink", 5, module=ModuleType.THREAT_SINK, path=BuildPath.STEALTH),
            DockOffer("Overcharge Cell", 2, power_capacity_bonus=10, path=BuildPath.SCAVENGER),
        ]

        dock_lines = engine.presenter.summary_lines()
        self.assertEqual(dock_lines[0], "Dock Exchange")
        self.assertTrue(any("BUY" in line for line in dock_lines))
        self.assertTrue(any("NEED SCRAP" in line for line in dock_lines))
        self.assertTrue(any("Stealth Route" in line for line in dock_lines))

        engine.dock_purchase_made = True
        engine.dock_purchase_index = 0
        locked_lines = engine.presenter.summary_lines()
        self.assertTrue(any("BOUGHT" in line for line in locked_lines))
        self.assertTrue(any("LOCKED" in line for line in locked_lines))

        engine.mode = GameMode.GAME_OVER
        engine.game_over_lines = ["Run Over", "Score: 25", "Seed: 42"]
        self.assertEqual(engine.presenter.summary_lines(), ["Run Over", "Score: 25", "Seed: 42"])

    def test_footer_and_sidebar_render_named_sections(self) -> None:
        floor = build_box_floor(relays=[Point(2, 1)])
        engine = build_engine(floor, score_file=self._score_file(), power=9)
        engine.mode = GameMode.DOCK_SHOP
        engine.player.modules.update(
            {ModuleType.QUIET_HIDE, ModuleType.LIGHT_PAWS, ModuleType.THREAT_SINK}
        )
        state = engine.presenter.get_render_state(
            OverlayState(title="Dock", lines=["Spend scrap."])
        )
        playing_engine = build_engine(
            build_box_floor(),
            score_file=self._score_file(),
            power=9,
        )
        playing_state = playing_engine.presenter.get_render_state()

        self.assertIn("descend", state.footer.lower())
        self.assertIn("threat", playing_state.footer.lower())
        self.assertEqual(state.sidebar.objective.title, "Objective")
        self.assertEqual(state.sidebar.tools.title, "Tools")
        self.assertEqual(state.sidebar.guidance.title, "Guidance")
        self.assertEqual(state.sidebar.modules.title, "Modules")
        self.assertEqual(state.sidebar.modules.lines[0], "Stealth Route")
        self.assertTrue(any(line.startswith("+") for line in state.sidebar.modules.lines))


if __name__ == "__main__":
    unittest.main()
