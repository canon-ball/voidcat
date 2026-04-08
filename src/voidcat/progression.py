from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from .generator import generate_floor
from .models import (
    MAX_POWER,
    NOISE_HISTORY_LENGTH,
    RELAY_RECHARGE,
    BuildPath,
    CellColor,
    DockOffer,
    EffectKind,
    FloorCondition,
    GameMode,
    ItemType,
    ModuleType,
    PlayerState,
    Point,
    RunStats,
    SignalOutcome,
    TileType,
)

if TYPE_CHECKING:
    from .engine import GameEngine


class ProgressionRules:
    def __init__(self, engine: GameEngine) -> None:
        self.engine = engine

    def new_game(self) -> None:
        self.engine.mode = GameMode.PLAYING
        self.engine.floor_number = 1
        self.engine.score = 0
        self.engine.current_noise = 0
        self.engine.ship_alert = 0
        self.engine.heard_position = None
        self.engine.turn_count = 0
        self.engine.stats = RunStats()
        self.engine.logs.clear()
        self.engine.noise_history = deque([0] * NOISE_HISTORY_LENGTH, maxlen=NOISE_HISTORY_LENGTH)
        self.engine.generated_noise_this_turn = False
        self.engine.decoy_target = None
        self.engine.decoy_turns = 0
        self.engine.last_turn_effects = []
        self.engine.current_run_saved = False
        self.engine.tutorial_flags = set()
        self.engine.game_over_lines = []
        self.engine.game_over_title = ""
        self.engine.floor_sweep_spawned = False
        self.engine.current_floor_condition = FloorCondition.STANDARD
        self.engine.floor_condition_history = []
        self.engine.dock_offers = []
        self.engine.dock_purchase_made = False
        self.engine.dock_purchase_index = None
        self.engine.extraction_bonus = 0
        self.engine.player = PlayerState(
            position=Point(0, 0), power=MAX_POWER, power_capacity=MAX_POWER
        )
        self.start_floor(reset_power=True)

    def start_floor(self, reset_power: bool) -> None:
        condition = self.pick_floor_condition(self.engine.floor_number)
        self.engine.current_floor_condition = condition
        self.engine.floor_condition_history.append(condition)
        self.engine.floor = generate_floor(self.engine.floor_number, self.engine.rng, condition)
        self.engine.restored_relays = set()
        self.engine.player.position = self.engine.floor.dock
        self.engine.player.hidden_turns = 0
        self.engine.player.hiss_cooldown = 0
        self.engine.player.pounce_cooldown = 0
        if reset_power:
            self.engine.player.power = self.engine.player.power_capacity
        self.engine.current_noise = 0
        self.engine.ship_alert = 0
        self.engine.heard_position = None
        self.engine.noise_history = deque([0] * NOISE_HISTORY_LENGTH, maxlen=NOISE_HISTORY_LENGTH)
        self.engine.generated_noise_this_turn = False
        self.engine.decoy_target = None
        self.engine.decoy_turns = 0
        self.engine.last_turn_effects = []
        self.engine.floor_sweep_spawned = False
        self.engine.dock_offers = []
        self.engine.dock_purchase_made = False
        self.engine.dock_purchase_index = None
        self.engine.extraction_bonus = 0
        self.engine.gameplay.update_visibility()
        self.engine.logs.clear()
        self.engine.add_log("You slip through the vent.")
        self.engine.add_log(f"Deck condition: {condition.label}.")
        self.engine.add_log(condition.summary)
        if self.engine.floor_number == 1:
            self.engine.add_log("The ship is dying. Find the relays and return to the dock.")
            self.engine.add_log("Tip: Space waits. ? opens the codex with full tool breakdowns.")
        else:
            self.engine.add_log(f"Floor {self.engine.floor_number}. The dark feels closer now.")
            self.engine.add_log(
                "Dock capacitors surge back online. "
                f"Power restored to {self.engine.player.power_capacity}."
            )
        if self.engine.persistence_warning:
            self.engine.add_log(f"Score save disabled: {self.engine.persistence_warning}")

    def pick_floor_condition(self, floor_number: int) -> FloorCondition:
        if floor_number == 1:
            return FloorCondition.TRAINING
        options = [
            FloorCondition.LOW_LIGHT,
            FloorCondition.HOT_DECK,
            FloorCondition.SIGNAL_SURGE,
        ]
        previous = (
            self.engine.floor_condition_history[-1] if self.engine.floor_condition_history else None
        )
        candidates = [condition for condition in options if condition != previous] or options
        return self.engine.rng.choice(candidates)

    def descend(self) -> None:
        if self.engine.mode != GameMode.DOCK_SHOP:
            return
        self.engine.floor_number += 1
        self.engine.mode = GameMode.PLAYING
        self.start_floor(reset_power=True)

    def finish_run(self) -> None:
        if self.engine.mode != GameMode.DOCK_SHOP:
            return
        self.engine.run_records.end_run(
            "You curl up in the dock and live to nap another shift.",
            extracted=True,
        )

    def buy_dock_offer(self, slot: int) -> bool:
        if self.engine.mode != GameMode.DOCK_SHOP:
            return False
        index = slot - 1
        if index < 0 or index >= len(self.engine.dock_offers):
            return False
        if self.engine.dock_purchase_made:
            self.engine.add_log("The dock only parts with one upgrade per floor.")
            return False

        offer = self.engine.dock_offers[index]
        if self.engine.player.scrap < offer.cost:
            self.engine.add_log("Not enough scrap for that dock offer.")
            return False

        self.engine.player.scrap -= offer.cost
        self.engine.dock_purchase_made = True
        self.engine.dock_purchase_index = index
        if offer.module is not None:
            self.engine.player.modules.add(offer.module)
            self.engine.stats.rare_modules += 1
            self.engine.stats.modules_installed += 1
            self.engine.add_log(
                f"Dock tech installed: {offer.module.label} [{offer.module.path.label}]."
            )
        if offer.power_capacity_bonus:
            self.engine.player.power_capacity += offer.power_capacity_bonus
            self.engine.player.power += offer.power_capacity_bonus
            self.engine.add_log(f"Overcharge cell fitted. Power cap +{offer.power_capacity_bonus}.")
        return True

    def interact(self) -> bool:
        if self.engine.floor is None:
            return False
        point = self.engine.player.position
        tile = self.engine.floor.tile_at(point)
        item = self.engine.floor.item_at(point)

        if tile == TileType.RELAY:
            if point in self.engine.restored_relays:
                self.engine.add_log("This relay is already humming.")
                return False
            self.engine.restored_relays.add(point)
            self.engine.floor.objective.restored_relays += 1
            relay_score = 100
            if ModuleType.RELAY_BOOST in self.engine.player.modules:
                relay_score += 50
            self.engine.score += relay_score
            self.engine.stats.relays_restored += 1
            self.engine.gameplay.consume_turn(power_cost=1, noise=1, noise_pos=point)
            if ModuleType.THREAT_SINK in self.engine.player.modules:
                self.engine.gameplay.adjust_ship_alert(-2)
            self.engine.player.power += RELAY_RECHARGE
            self.engine.gameplay.push_effect(
                EffectKind.RELAY, [point], CellColor.RELAY_PULSE, 3, "◆"
            )
            self.engine.gameplay.push_effect(
                EffectKind.ALERT_BAR, [], CellColor.RELAY_PULSE, 2, "!"
            )
            self.engine.add_log(f"Relay restored. Ship power reroutes. Power +{RELAY_RECHARGE}.")
            return True

        if tile == TileType.DOCK:
            if not self.engine.floor.objective.complete:
                remaining = (
                    self.engine.floor.objective.required_relays
                    - self.engine.floor.objective.restored_relays
                )
                self.engine.add_log(f"The dock stays dark. {remaining} relay(s) still dead.")
                return False
            self.engine.extraction_bonus = 250 + max(0, self.engine.player.power) * 5
            self.engine.score += self.engine.extraction_bonus
            self.engine.stats.floors_cleared += 1
            self.engine.stats.safe_extractions += 1
            self.engine.mode = GameMode.DOCK_SHOP
            self.engine.dock_offers = self.generate_dock_offers()
            self.engine.dock_purchase_made = False
            self.engine.dock_purchase_index = None
            self.engine.add_log("Dock exchange open. Spend scrap before the next descent.")
            if self.engine.floor_number == 1:
                self.engine.add_log(
                    "Tip: The dock lets you bank safety or push deeper for a bigger run."
                )
            return True

        if item and item.kind == ItemType.SIGNAL:
            self.engine.gameplay.consume_turn(power_cost=1, noise=1, noise_pos=point)
            self.engine.floor.items.remove(item)
            self.engine.stats.signals_touched += 1
            self.engine.tutorial_once(
                "signal_tip",
                "Tip: Signals are gambles. Touch them when you can survive noise, "
                "static, or an ambush.",
            )
            self.resolve_signal()
            return True

        self.engine.add_log("Nothing here but ship smell.")
        return False

    def resolve_signal(self) -> None:
        choices = [
            (
                SignalOutcome.BATTERY_CACHE,
                max(6, 30 - self.engine.current_noise * 2 - self.engine.ship_alert),
            ),
            (SignalOutcome.SCRAP_CACHE, max(6, 24 - self.engine.ship_alert)),
            (
                SignalOutcome.MODULE,
                max(4, 18 - self.engine.current_noise - self.engine.ship_alert // 2),
            ),
            (
                SignalOutcome.AMBUSH,
                0
                if ModuleType.SIGNAL_FILTER in self.engine.player.modules
                else 10 + self.engine.current_noise + self.engine.ship_alert,
            ),
            (
                SignalOutcome.STATIC_BURST,
                10 + self.engine.current_noise + self.engine.ship_alert * 2,
            ),
        ]
        available = [(outcome, weight) for outcome, weight in choices if weight > 0]
        total = sum(weight for _, weight in available)
        roll = self.engine.rng.randint(1, total)
        outcome = SignalOutcome.STATIC_BURST
        for candidate, weight in available:
            roll -= weight
            if roll <= 0:
                outcome = candidate
                break

        if outcome == SignalOutcome.BATTERY_CACHE:
            amount = self.engine.rng.randint(10, 16)
            self.engine.player.power += amount
            self.engine.stats.batteries_found += 1
            self.engine.add_log(f"Battery cache found. Power +{amount}.")
            return

        if outcome == SignalOutcome.SCRAP_CACHE:
            amount = self.engine.rng.randint(2, 3)
            self.engine.player.scrap += amount
            self.engine.score += amount * 15
            self.engine.add_log(f"You pry open a scrap stash. +{amount} scrap.")
            return

        if outcome == SignalOutcome.MODULE:
            module = self.award_module()
            if module is not None:
                self.engine.add_log(f"Rare module recovered: {module.label}.")
            return

        if outcome == SignalOutcome.AMBUSH:
            self.engine.gameplay.add_noise(4, self.engine.player.position)
            if self.engine.gameplay.spawn_enemy_near_player(min_distance=2):
                self.engine.add_log("The signal twitches. Something answers.")
            else:
                self.engine.add_log("The signal chatters, but nothing can get a clean angle.")
            return

        self.engine.gameplay.add_noise(5, self.engine.player.position)
        self.engine.add_log("Static cracks through the vent. Something heard that.")

    def award_module(self) -> ModuleType | None:
        available = [module for module in ModuleType if module not in self.engine.player.modules]
        if not available:
            amount = self.engine.rng.randint(6, 10)
            self.engine.player.power += amount
            self.engine.add_log(f"No new module slot. Emergency charge +{amount}.")
            return None
        module = self.engine.rng.choice(available)
        self.engine.player.modules.add(module)
        self.engine.stats.rare_modules += 1
        self.engine.score += 75
        return module

    def generate_dock_offers(self) -> list[DockOffer]:
        missing_modules = [
            module for module in ModuleType if module not in self.engine.player.modules
        ]
        offers: list[DockOffer] = []
        chosen_modules: set[ModuleType] = set()

        for path in BuildPath:
            candidates = [module for module in missing_modules if module.path == path]
            if not candidates:
                continue
            module = self.engine.rng.choice(candidates)
            chosen_modules.add(module)
            offers.append(
                DockOffer(
                    label=module.label,
                    cost=self.module_cost(module),
                    module=module,
                    path=path,
                    tagline=path.summary,
                )
            )

        remaining_modules = [module for module in missing_modules if module not in chosen_modules]
        while len(offers) < 3 and remaining_modules:
            module = self.engine.rng.choice(remaining_modules)
            remaining_modules.remove(module)
            offers.append(
                DockOffer(
                    label=module.label,
                    cost=self.module_cost(module),
                    module=module,
                    path=module.path,
                    tagline=module.path.summary,
                )
            )

        while len(offers) < 3:
            preferred_path = self.engine.dominant_build_path or BuildPath.SCAVENGER
            offers.append(
                DockOffer(
                    label="Overcharge Cell",
                    cost=2,
                    power_capacity_bonus=10,
                    path=preferred_path,
                    tagline="Bank a deeper power refill for the next descent.",
                )
            )
        return offers

    def module_cost(self, module: ModuleType) -> int:
        if module in {ModuleType.SIGNAL_FILTER, ModuleType.THREAT_SINK}:
            return 5
        return 4
