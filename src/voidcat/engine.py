from __future__ import annotations

import random
from collections import deque
from datetime import date
from pathlib import Path

from .gameplay import GameplayRules
from .models import (
    NOISE_HISTORY_LENGTH,
    ActionType,
    BuildPath,
    DockOffer,
    FloorCondition,
    FloorState,
    GameMode,
    OverlayState,
    PlayerState,
    Point,
    RenderEffect,
    RenderState,
    RunStats,
    ScoreEntry,
    ShipAlertStage,
)
from .persistence import load_scores
from .presentation import PresentationBuilder
from .progression import ProgressionRules
from .session import RunRecorder


class GameEngine:
    def __init__(self, seed: int | None = None, score_file: Path | None = None) -> None:
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self.rng = random.Random(self.seed)
        self.score_file = score_file
        self.scores = load_scores(score_file)
        self.persistence_warning: str | None = None
        self.daily_run_active = False
        self.mode = GameMode.PLAYING
        self.floor_number = 0
        self.score = 0
        self.current_noise = 0
        self.ship_alert = 0
        self.heard_position: Point | None = None
        self.turn_count = 0
        self.floor: FloorState | None = None
        self.player = PlayerState(position=Point(0, 0))
        self.stats = RunStats()
        self.logs: deque[str] = deque(maxlen=32)
        self.noise_history: deque[int] = deque(
            [0] * NOISE_HISTORY_LENGTH, maxlen=NOISE_HISTORY_LENGTH
        )
        self.generated_noise_this_turn = False
        self.restored_relays: set[Point] = set()
        self.decoy_target: Point | None = None
        self.decoy_turns = 0
        self.last_turn_effects: list[RenderEffect] = []
        self.floor_sweep_spawned = False
        self.current_floor_condition = FloorCondition.STANDARD
        self.floor_condition_history: list[FloorCondition] = []
        self.dock_offers: list[DockOffer] = []
        self.dock_purchase_made = False
        self.dock_purchase_index: int | None = None
        self.extraction_bonus = 0
        self.game_over_lines: list[str] = []
        self.game_over_title = ""
        self.current_run_saved = False
        self.tutorial_flags: set[str] = set()

        self.gameplay = GameplayRules(self)
        self.progression = ProgressionRules(self)
        self.presenter = PresentationBuilder(self)
        self.run_records = RunRecorder(self)

        self.new_game()

    @property
    def ship_alert_stage(self) -> ShipAlertStage:
        return self.ship_alert_for_value(self.ship_alert)

    def ship_alert_for_value(self, value: int) -> ShipAlertStage:
        if value >= 9:
            return ShipAlertStage.SWEEP
        if value >= 4:
            return ShipAlertStage.HUNT
        return ShipAlertStage.CALM

    def new_game(self) -> None:
        self.progression.new_game()

    @staticmethod
    def daily_seed_for_day(day: date) -> int:
        return day.toordinal() * 97 + 131

    def daily_seed(self) -> int:
        return self.daily_seed_for_day(date.today())

    def set_run_seed(self, seed: int, *, daily_run: bool) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.daily_run_active = daily_run

    def reroll_seed(self) -> int:
        self.set_run_seed(random.randrange(1 << 30), daily_run=False)
        return self.seed

    def prepare_daily_run(self) -> int:
        seed = self.daily_seed()
        self.set_run_seed(seed, daily_run=True)
        return seed

    @property
    def seed_label(self) -> str:
        prefix = "Daily Run" if self.daily_run_active else "Seed"
        return f"{prefix} {self.seed}"

    def build_path_scores(self) -> dict[BuildPath, int]:
        scores = {path: 0 for path in BuildPath}
        for module in self.player.modules:
            scores[module.path] += 3
        scores[BuildPath.STEALTH] += self.stats.hides_used + self.stats.knocks_used
        scores[BuildPath.MOBILITY] += self.stats.pounces_used
        scores[BuildPath.SCAVENGER] += self.stats.signals_touched + self.stats.relays_restored
        return scores

    @property
    def dominant_build_path(self) -> BuildPath | None:
        scores = self.build_path_scores()
        best_score = max(scores.values(), default=0)
        if best_score <= 0:
            return None
        order = list(BuildPath)
        return max(order, key=lambda path: (scores[path], -order.index(path)))

    @property
    def build_path_label(self) -> str:
        dominant = self.dominant_build_path
        if dominant is None:
            return "Adaptive Route"
        return dominant.label

    @property
    def run_share_text(self) -> str:
        return f"{self.seed_label} // {self.build_path_label} // Score {self.score}"

    def _start_floor(self, reset_power: bool) -> None:
        self.progression.start_floor(reset_power)

    def add_log(self, message: str) -> None:
        self.logs.append(message)

    def tutorial_once(self, key: str, message: str) -> None:
        if key in self.tutorial_flags:
            return
        self.tutorial_flags.add(key)
        self.add_log(message)

    def perform_action(self, action: ActionType, direction: str | None = None) -> bool:
        return self.gameplay.perform_action(action, direction)

    def descend(self) -> None:
        self.progression.descend()

    def finish_run(self) -> None:
        self.progression.finish_run()

    def buy_dock_offer(self, slot: int) -> bool:
        return self.progression.buy_dock_offer(slot)

    def get_render_state(self, overlay: OverlayState | None = None) -> RenderState:
        return self.presenter.get_render_state(overlay)

    def summary_lines(self) -> list[str]:
        return self.presenter.summary_lines()

    def get_scores(self) -> list[ScoreEntry]:
        return list(self.scores)

    def clear_effects(self) -> None:
        self.last_turn_effects = []

    def preview_knock_path(self, direction: str) -> list[Point] | None:
        return self.gameplay.preview_knock_path(direction)

    def preview_knock_paths(self) -> dict[str, list[Point]]:
        return self.gameplay.preview_knock_paths()

    def preview_pounce_target(self, direction: str) -> Point | None:
        return self.gameplay.preview_pounce_target(direction)

    def preview_pounce_targets(self) -> dict[str, Point]:
        return self.gameplay.preview_pounce_targets()

    def _adjust_ship_alert(self, delta: int) -> None:
        self.gameplay.adjust_ship_alert(delta)

    def _resolve_signal(self) -> None:
        self.progression.resolve_signal()

    def _update_visibility(self) -> None:
        self.gameplay.update_visibility()
