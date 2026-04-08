from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from voidcat.engine import GameEngine
from voidcat.models import ActionType, OverlayState


class SmokeTests(unittest.TestCase):
    def test_engine_can_render_without_curses(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            engine = GameEngine(seed=123, score_file=Path(tempdir) / "scores.json")
            engine.perform_action(ActionType.HIDE)
            engine.perform_action(ActionType.MOVE, "d")
            state = engine.get_render_state()

        self.assertEqual(len(state.map_rows), 15)
        self.assertEqual(len(state.map_rows[0]), 35)
        self.assertEqual(state.hud.power, engine.player.power)
        self.assertEqual(len(state.noise_history), 8)
        self.assertEqual(state.sidebar.objective.title, "Objective")
        self.assertIsInstance(state.effects, list)
        self.assertLessEqual(len(state.log_lines), 4)

    def test_help_overlay_can_request_full_backdrop(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            engine = GameEngine(seed=321, score_file=Path(tempdir) / "scores.json")
            state = engine.get_render_state(OverlayState(title="VOIDCAT // HELP", backdrop=True))

        self.assertTrue(state.overlay.backdrop)
        self.assertEqual(state.overlay.title, "VOIDCAT // HELP")
