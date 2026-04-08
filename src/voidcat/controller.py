from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .engine import GameEngine
from .help import HELP_PAGES
from .models import ActionType, GameMode


class Scene(Enum):
    TITLE = "title"
    GAME = "game"
    HELP = "help"
    SCORES = "scores"


class OverlayKind(Enum):
    NONE = "none"
    HELP = "help"
    QUIT = "quit"
    KNOCK = "knock"
    POUNCE = "pounce"
    DOCK = "dock"
    GAME_OVER = "game_over"


@dataclass(frozen=True)
class ControllerResult:
    engine_changed: bool = False
    should_quit: bool = False


class GameController:
    def __init__(self, engine: GameEngine) -> None:
        self.engine = engine
        self.scene = Scene.TITLE
        self.return_scene = Scene.TITLE
        self.help_page_index = 0
        self.pending_action: ActionType | None = None
        self.quit_confirm = False

    def handle_key(self, key: str) -> ControllerResult:
        if self.scene == Scene.HELP:
            return self._handle_help_key(key)
        if self.scene == Scene.SCORES:
            return self._handle_scores_key(key)
        if self.scene == Scene.TITLE:
            return self._handle_title_key(key)
        return self._handle_game_key(key)

    def current_overlay(self) -> OverlayKind:
        if self.scene == Scene.HELP:
            return OverlayKind.HELP
        if self.quit_confirm:
            return OverlayKind.QUIT
        if self.pending_action == ActionType.KNOCK:
            return OverlayKind.KNOCK
        if self.pending_action == ActionType.POUNCE:
            return OverlayKind.POUNCE
        if self.engine.mode == GameMode.DOCK_SHOP:
            return OverlayKind.DOCK
        if self.engine.mode == GameMode.GAME_OVER:
            return OverlayKind.GAME_OVER
        return OverlayKind.NONE

    def _handle_title_key(self, key: str) -> ControllerResult:
        if key == "n":
            self.engine.daily_run_active = False
            self.engine.new_game()
            self.scene = Scene.GAME
            self.pending_action = None
            self.quit_confirm = False
            return ControllerResult(engine_changed=True)
        if key == "d":
            self.engine.prepare_daily_run()
            self.engine.new_game()
            self.scene = Scene.GAME
            self.pending_action = None
            self.quit_confirm = False
            return ControllerResult(engine_changed=True)
        if key == "r":
            self.engine.reroll_seed()
            return ControllerResult()
        if key == "h":
            self.return_scene = Scene.TITLE
            self.scene = Scene.SCORES
            return ControllerResult()
        if key == "?":
            self.return_scene = Scene.TITLE
            self.help_page_index = 0
            self.scene = Scene.HELP
            return ControllerResult()
        if key in {"q", "esc"}:
            return ControllerResult(should_quit=True)
        return ControllerResult()

    def _handle_help_key(self, key: str) -> ControllerResult:
        total = len(HELP_PAGES)
        if key in {"KEY_RIGHT", "tab"}:
            self.help_page_index = (self.help_page_index + 1) % total
        elif key == "KEY_LEFT":
            self.help_page_index = (self.help_page_index - 1) % total
        elif key in {"?", "esc", "enter", " "}:
            self.scene = self.return_scene
        return ControllerResult()

    def _handle_scores_key(self, key: str) -> ControllerResult:
        if key == "?":
            self.return_scene = Scene.SCORES
            self.help_page_index = 0
            self.scene = Scene.HELP
            return ControllerResult()
        if key in {"h", "esc", "enter", " "}:
            self.scene = self.return_scene
            return ControllerResult()
        if key == "q" and self.return_scene == Scene.TITLE:
            return ControllerResult(should_quit=True)
        return ControllerResult()

    def _handle_game_key(self, key: str) -> ControllerResult:
        if key == "?":
            self.return_scene = Scene.GAME
            self.help_page_index = 0
            self.scene = Scene.HELP
            return ControllerResult()

        if self.quit_confirm:
            if key == "y":
                return ControllerResult(should_quit=True)
            if key in {"n", "q", "esc"}:
                self.quit_confirm = False
            return ControllerResult()

        if self.engine.mode == GameMode.DOCK_SHOP:
            return self._handle_dock_key(key)
        if self.engine.mode == GameMode.GAME_OVER:
            return self._handle_game_over_key(key)
        if self.pending_action is not None:
            return self._handle_pending_action_key(key)

        if key in {"w", "a", "s", "d", "KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT"}:
            return ControllerResult(engine_changed=self.engine.perform_action(ActionType.MOVE, key))
        if key == "e":
            return ControllerResult(engine_changed=self.engine.perform_action(ActionType.INTERACT))
        if key == "h":
            return ControllerResult(engine_changed=self.engine.perform_action(ActionType.HISS))
        if key == "x":
            return ControllerResult(engine_changed=self.engine.perform_action(ActionType.HIDE))
        if key == "k":
            self.pending_action = ActionType.KNOCK
            return ControllerResult()
        if key == "p":
            self.pending_action = ActionType.POUNCE
            return ControllerResult()
        if key == " ":
            return ControllerResult(engine_changed=self.engine.perform_action(ActionType.WAIT))
        if key == "q":
            self.quit_confirm = True
        return ControllerResult()

    def _handle_dock_key(self, key: str) -> ControllerResult:
        if key in {"1", "2", "3"}:
            return ControllerResult(engine_changed=self.engine.buy_dock_offer(int(key)))
        if key == "d":
            self.engine.descend()
            return ControllerResult(engine_changed=True)
        if key == "e":
            self.engine.finish_run()
            return ControllerResult(engine_changed=True)
        if key == "q":
            self.quit_confirm = True
        return ControllerResult()

    def _handle_game_over_key(self, key: str) -> ControllerResult:
        if key == "n":
            self.engine.new_game()
            self.pending_action = None
            self.quit_confirm = False
            return ControllerResult(engine_changed=True)
        if key == "h":
            self.return_scene = Scene.GAME
            self.scene = Scene.SCORES
            return ControllerResult()
        if key == "?":
            self.return_scene = Scene.GAME
            self.help_page_index = 0
            self.scene = Scene.HELP
            return ControllerResult()
        if key == "q":
            return ControllerResult(should_quit=True)
        return ControllerResult()

    def _handle_pending_action_key(self, key: str) -> ControllerResult:
        if key == "esc":
            self.pending_action = None
            return ControllerResult()
        if key in {"w", "a", "s", "d", "KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT"}:
            action = self.pending_action
            self.pending_action = None
            return ControllerResult(
                engine_changed=self.engine.perform_action(action or ActionType.WAIT, key)
            )
        return ControllerResult()
