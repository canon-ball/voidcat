from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from .models import BuildPath, GameMode, ScoreEntry
from .persistence import save_scores

if TYPE_CHECKING:
    from .engine import GameEngine


class RunRecorder:
    def __init__(self, engine: GameEngine) -> None:
        self.engine = engine

    def end_run(self, reason: str, *, extracted: bool) -> None:
        if self.engine.current_run_saved:
            self.engine.mode = GameMode.GAME_OVER
            return
        self.engine.mode = GameMode.GAME_OVER
        self.engine.game_over_title = self.end_title(extracted)
        self.engine.game_over_lines = [
            reason,
            f"Score: {self.engine.score}",
            f"Seed: {self.engine.seed}",
            self.run_label(),
            f"Build: {self.engine.build_path_label}",
            f"Floor reached: {self.engine.floor_number}",
            f"Decks: {self.condition_summary()}",
            f"Scrap: {self.engine.player.scrap}",
            f"Relays restored: {self.engine.stats.relays_restored}",
            f"Rare modules: {self.engine.stats.rare_modules}",
        ]
        highlights = self.highlight_lines(extracted)
        if highlights:
            self.engine.game_over_lines.append("Highlights:")
            self.engine.game_over_lines.extend(f"- {line}" for line in highlights[:3])
        self.engine.game_over_lines.extend(
            [
                f"Title: {self.engine.game_over_title}",
                f"Share: {self.engine.run_share_text}",
                "Press N for a new run, H for high scores, or Q to quit.",
            ]
        )
        entry = ScoreEntry(
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            score=self.engine.score,
            floor_reached=self.engine.floor_number,
            scrap=self.engine.player.scrap,
            relays_restored=self.engine.stats.relays_restored,
            rare_modules=self.engine.stats.rare_modules,
            extracted=extracted,
            title=self.engine.game_over_title,
            seed=self.engine.seed,
            daily_run=self.engine.daily_run_active,
            build_path=self.engine.build_path_label,
            highlight=highlights[0] if highlights else "",
        )
        self.engine.scores.append(entry)
        self.engine.scores.sort(key=lambda score: score.score, reverse=True)
        self.engine.scores = self.engine.scores[:10]
        ok, error = save_scores(self.engine.scores, self.engine.score_file)
        if not ok and error:
            self.engine.persistence_warning = error
        self.engine.current_run_saved = True

    def run_label(self) -> str:
        return "Daily Run" if self.engine.daily_run_active else "Seeded Run"

    def condition_summary(self) -> str:
        conditions = list(self.engine.floor_condition_history)
        if not conditions and self.engine.floor is not None:
            conditions = [self.engine.floor.condition]
        if not conditions:
            return "Unknown"
        return " | ".join(
            f"F{index} {condition.label}" for index, condition in enumerate(conditions, start=1)
        )

    def highlight_lines(self, extracted: bool) -> list[str]:
        highlights: list[str] = []
        if extracted and self.engine.stats.max_alert >= 9:
            highlights.append("Clawed through a full SWEEP and still made dock.")
        if self.engine.stats.signals_touched >= 3:
            highlights.append(
                f"Worked {self.engine.stats.signals_touched} live signals for extra value."
            )
        if self.engine.stats.knocks_used >= 3:
            highlights.append("Turned the ducts into a decoy maze.")
        if self.engine.stats.hides_used >= 3 and self.engine.stats.quiet_turns >= 6:
            highlights.append("Ran a cold, quiet route through the deck.")
        if self.engine.stats.pounces_used >= 3:
            highlights.append("Used mobility bursts to steal position under pressure.")
        if (
            len(
                {
                    condition
                    for condition in self.engine.floor_condition_history
                    if condition.name != "TRAINING"
                }
            )
            >= 3
        ):
            highlights.append("Survived every major deck state in one run.")
        if not highlights:
            highlights.append("Held the ship together for one more shift.")
        return highlights

    def end_title(self, extracted: bool) -> str:
        if extracted and self.engine.stats.safe_extractions >= 1 and self.engine.floor_number <= 2:
            return "Dock Nap Champion"
        if extracted and self.engine.stats.max_noise <= 3:
            return "Silent Gremlin"
        if extracted and self.engine.dominant_build_path == BuildPath.STEALTH:
            return "Vent Ghost"
        if extracted and self.engine.dominant_build_path == BuildPath.MOBILITY:
            return "Bolt Paws"
        if extracted and self.engine.dominant_build_path == BuildPath.SCAVENGER:
            return "Scrap Oracle"
        if self.engine.stats.batteries_found >= 5:
            return "Battery Goblin"
        if self.engine.stats.relays_restored >= 6:
            return "Unlicensed Void Mechanic"
        return "Orange Cat Behavior"
