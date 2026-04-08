from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.helpers import build_box_floor, build_engine
from voidcat.models import BuildPath, FloorCondition


class SessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.score_file = Path(self.tempdir.name) / "scores.json"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_end_run_is_idempotent_when_current_run_already_saved(self) -> None:
        engine = build_engine(build_box_floor(), score_file=self.score_file, power=10)
        engine.current_run_saved = True

        engine.run_records.end_run("Already saved.", extracted=False)

        self.assertEqual(engine.mode.name, "GAME_OVER")
        self.assertEqual(engine.scores, [])
        self.assertEqual(engine.game_over_lines, [])

    def test_condition_summary_uses_history_floor_and_unknown_fallbacks(self) -> None:
        engine = build_engine(build_box_floor(), score_file=self.score_file, power=10)

        engine.floor_condition_history = []
        self.assertEqual(engine.run_records.condition_summary(), "F1 Standard Deck")

        engine.floor = None
        self.assertEqual(engine.run_records.condition_summary(), "Unknown")

        engine.floor_condition_history = [
            FloorCondition.TRAINING,
            FloorCondition.LOW_LIGHT,
            FloorCondition.HOT_DECK,
        ]
        self.assertEqual(
            engine.run_records.condition_summary(),
            "F1 Training Deck | F2 Low Light | F3 Hot Deck",
        )

    def test_highlight_lines_cover_fallback_and_multi_highlight_paths(self) -> None:
        engine = build_engine(build_box_floor(), score_file=self.score_file, power=10)
        self.assertEqual(
            engine.run_records.highlight_lines(extracted=False),
            ["Held the ship together for one more shift."],
        )

        engine.stats.max_alert = 9
        engine.stats.signals_touched = 3
        engine.stats.knocks_used = 3
        engine.stats.hides_used = 3
        engine.stats.quiet_turns = 6
        engine.stats.pounces_used = 3
        engine.floor_condition_history = [
            FloorCondition.TRAINING,
            FloorCondition.LOW_LIGHT,
            FloorCondition.HOT_DECK,
            FloorCondition.SIGNAL_SURGE,
        ]

        highlights = engine.run_records.highlight_lines(extracted=True)

        self.assertIn("Clawed through a full SWEEP and still made dock.", highlights)
        self.assertIn("Worked 3 live signals for extra value.", highlights)
        self.assertIn("Turned the ducts into a decoy maze.", highlights)
        self.assertIn("Ran a cold, quiet route through the deck.", highlights)
        self.assertIn("Used mobility bursts to steal position under pressure.", highlights)
        self.assertIn("Survived every major deck state in one run.", highlights)

    def test_end_title_covers_major_title_paths(self) -> None:
        engine = build_engine(build_box_floor(), score_file=self.score_file, power=10)
        engine.stats.safe_extractions = 1
        engine.floor_number = 2
        self.assertEqual(engine.run_records.end_title(True), "Dock Nap Champion")

        engine.stats.safe_extractions = 0
        engine.stats.max_noise = 3
        self.assertEqual(engine.run_records.end_title(True), "Silent Gremlin")

        engine.stats.max_noise = 9
        engine.player.modules.clear()
        engine.stats.hides_used = 4
        self.assertEqual(engine.dominant_build_path, BuildPath.STEALTH)
        self.assertEqual(engine.run_records.end_title(True), "Vent Ghost")

        engine.stats.hides_used = 0
        engine.stats.knocks_used = 0
        engine.stats.pounces_used = 4
        self.assertEqual(engine.dominant_build_path, BuildPath.MOBILITY)
        self.assertEqual(engine.run_records.end_title(True), "Bolt Paws")

        engine.stats.pounces_used = 0
        engine.stats.signals_touched = 4
        self.assertEqual(engine.dominant_build_path, BuildPath.SCAVENGER)
        self.assertEqual(engine.run_records.end_title(True), "Scrap Oracle")

        engine.stats.signals_touched = 0
        engine.stats.batteries_found = 5
        self.assertEqual(engine.run_records.end_title(False), "Battery Goblin")

        engine.stats.batteries_found = 0
        engine.stats.relays_restored = 6
        self.assertEqual(engine.run_records.end_title(False), "Unlicensed Void Mechanic")

        engine.stats.relays_restored = 0
        self.assertEqual(engine.run_records.end_title(False), "Orange Cat Behavior")


if __name__ == "__main__":
    unittest.main()
