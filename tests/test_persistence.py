from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voidcat.models import MAX_HIGH_SCORES, ScoreEntry
from voidcat.persistence import load_scores, save_scores, score_path


class PersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.score_file = Path(self.tempdir.name) / "scores.json"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_missing_scores_file_returns_empty_list(self) -> None:
        self.assertEqual(load_scores(self.score_file), [])

    def test_score_path_prefers_xdg_and_falls_back_to_home(self) -> None:
        with patch.dict("os.environ", {"XDG_DATA_HOME": "/tmp/voidcat-data"}, clear=False):
            self.assertEqual(score_path(), Path("/tmp/voidcat-data") / "voidcat" / "scores.json")

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("pathlib.Path.home", return_value=Path("/tmp/home-cat")),
        ):
            self.assertEqual(score_path(), Path("/tmp/home-cat/.local/share/voidcat/scores.json"))

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

    def test_load_scores_rejects_non_list_and_trims_sorted_entries(self) -> None:
        entries = [
            ScoreEntry(
                timestamp=f"2026-04-07T00:00:{index:02d}+00:00",
                score=index,
                floor_reached=1,
                scrap=0,
                relays_restored=0,
                rare_modules=0,
                extracted=False,
                title=f"Run {index}",
            )
            for index in range(MAX_HIGH_SCORES + 5)
        ]
        ok, error = save_scores(entries, self.score_file)
        self.assertTrue(ok)
        self.assertIsNone(error)

        loaded = load_scores(self.score_file)
        self.assertEqual(len(loaded), MAX_HIGH_SCORES)
        self.assertEqual(loaded[0].score, MAX_HIGH_SCORES + 4)
        self.assertEqual(loaded[-1].score, 5)

        self.score_file.write_text('{"bad": "shape"}', encoding="utf-8")
        self.assertEqual(load_scores(self.score_file), [])

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

    def test_save_scores_returns_os_error_message(self) -> None:
        entry = ScoreEntry(
            timestamp="2026-04-07T00:00:00+00:00",
            score=10,
            floor_reached=1,
            scrap=0,
            relays_restored=0,
            rare_modules=0,
            extracted=False,
            title="Oops",
        )
        with patch("pathlib.Path.write_text", side_effect=OSError("disk full")):
            ok, error = save_scores([entry], self.score_file)

        self.assertFalse(ok)
        self.assertEqual(error, "disk full")
