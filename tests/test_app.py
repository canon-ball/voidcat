from __future__ import annotations

import unittest
from pathlib import Path

from voidcat.help import HELP_PAGES, help_overlay


class AppTests(unittest.TestCase):
    def test_help_codex_has_expected_pages_and_rules(self) -> None:
        self.assertEqual(len(HELP_PAGES), 6)
        self.assertTrue(any("CONTROLS" in line for line in HELP_PAGES[0]))
        self.assertTrue(any("HOW A RUN WORKS" in line for line in HELP_PAGES[1]))
        self.assertTrue(any("HISS AND HIDE" in line for line in HELP_PAGES[2]))
        self.assertTrue(any("KNOCK AND POUNCE" in line for line in HELP_PAGES[3]))
        self.assertTrue(any("STEALTH SYSTEMS" in line for line in HELP_PAGES[4]))
        self.assertTrue(any("Crawler" in line for line in HELP_PAGES[5]))
        self.assertTrue(any("Stalker" in line for line in HELP_PAGES[5]))
        self.assertTrue(any("Space" in line for line in HELP_PAGES[0]))
        self.assertTrue(any("threat overlay" in line for line in HELP_PAGES[0]))
        self.assertTrue(any("F11" in line for line in HELP_PAGES[0]))
        self.assertTrue(any("two enemy phases" in line for line in HELP_PAGES[3]))
        self.assertTrue(any("adjacent crawlers and mimics" in line for line in HELP_PAGES[2]))

    def test_help_overlay_lines_include_page_navigation(self) -> None:
        overlay = help_overlay(1)
        self.assertEqual(overlay.title, "VOIDCAT // HOW A RUN WORKS")
        self.assertIn("Page 2/6", overlay.lines[-1])
        self.assertIn("Tab", overlay.lines[-1])
        self.assertTrue(overlay.backdrop)

    def test_pyproject_declares_graphics_entrypoint_and_extra(self) -> None:
        raw = Path("pyproject.toml").read_text()
        self.assertIn('voidcat = "voidcat.gfx_app:main"', raw)
        self.assertIn('dependencies = ["pygame-ce>=2.5"]', raw)
        self.assertNotIn('voidcat-gfx = "voidcat.gfx_app:main"', raw)
        self.assertIn('dev = ["coverage', raw)
        self.assertFalse(Path("setup.py").exists())


if __name__ == "__main__":
    unittest.main()
