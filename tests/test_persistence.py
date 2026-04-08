from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from voidcat.models import ScoreEntry
from voidcat.persistence import load_scores, save_scores


class PersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.score_file = Path(self.tempdir.name) / "scores.json"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_missing_scores_file_returns_empty_list(self) -> None:
        self.assertEqual(load_scores(self.score_file), [])

    def test_save_and_load_round_trip(self) -> None:
        entries = [
            ScoreEntry(
                timestamp="2026-04-07T00:00:00+00:00",
                score=420,
                floor_reached=3,
                scrap=5,
                relays_restored=4,
                rare_modules=1,
                extracted=True,
                title="Silent Gremlin",
                seed=71752389,
                daily_run=True,
                build_path="Stealth Route",
                highlight="Clawed through a full SWEEP and still made dock.",
            )
        ]
        ok, error = save_scores(entries, self.score_file)
        self.assertTrue(ok)
        self.assertIsNone(error)

        loaded = load_scores(self.score_file)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].score, 420)
        self.assertEqual(loaded[0].seed, 71752389)
        self.assertTrue(loaded[0].daily_run)
        self.assertEqual(loaded[0].build_path, "Stealth Route")

    def test_malformed_scores_file_falls_back_to_empty(self) -> None:
        self.score_file.write_text("{not-json", encoding="utf-8")
        self.assertEqual(load_scores(self.score_file), [])

    def test_partial_score_corruption_keeps_valid_entries(self) -> None:
        self.score_file.write_text(
            """
            [
              {
                "timestamp": "2026-04-07T00:00:00+00:00",
                "score": 420,
                "floor_reached": 3,
                "scrap": 5,
                "relays_restored": 4,
                "rare_modules": 1,
                "extracted": true,
                "title": "Silent Gremlin"
              },
              {
                "timestamp": "broken",
                "score": "oops"
              }
            ]
            """.strip(),
            encoding="utf-8",
        )

        loaded = load_scores(self.score_file)

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].score, 420)
