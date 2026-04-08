from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from .ai import advance_enemy, line_of_sight
from .models import (
    INPUT_TO_DIRECTION,
    MAX_NOISE,
    MAX_SHIP_ALERT,
    NOISE_HISTORY_LENGTH,
    VISION_RADIUS,
    ActionType,
    AlertState,
    CellColor,
    EffectKind,
    EnemyType,
    Entity,
    FloorCondition,
    GameMode,
    Item,
    ItemType,
    ModuleType,
    Point,
    RenderEffect,
    ShipAlertStage,
    TileType,
)

if TYPE_CHECKING:
    from .engine import GameEngine


class GameplayRules:
    def __init__(self, engine: GameEngine) -> None:
        self.engine = engine

    def perform_action(self, action: ActionType, direction: str | None = None) -> bool:
        if self.engine.mode != GameMode.PLAYING or self.engine.floor is None:
            return False

        if action in {ActionType.MOVE, ActionType.KNOCK, ActionType.POUNCE} and direction is None:
            self.engine.add_log("Choose a direction.")
            return False

        self.engine.generated_noise_this_turn = False
        self.engine.last_turn_effects = []
        turn_spent = False

        if action == ActionType.MOVE:
            turn_spent = self.move(direction or "")
        elif action == ActionType.INTERACT:
            turn_spent = self.engine.progression.interact()
        elif action == ActionType.HISS:
            turn_spent = self.hiss()
        elif action == ActionType.HIDE:
            turn_spent = self.hide()
        elif action == ActionType.KNOCK:
            turn_spent = self.knock(direction or "")
        elif action == ActionType.POUNCE:
            turn_spent = self.pounce(direction or "")
        elif action == ActionType.WAIT:
            self.consume_turn(power_cost=1, noise=0, noise_pos=self.engine.player.position)
            self.engine.add_log("You wait and listen.")
            turn_spent = True

        if not turn_spent:
            return False

        self.engine.turn_count += 1
        self.tick_cooldowns()

        if self.engine.mode != GameMode.PLAYING:
            return True

        if self.engine.player.power <= 0:
            self.engine.run_records.end_run(
                "The lights go out. You do not make it back.", extracted=False
            )
            return True

        self.run_enemy_phase()
        if self.engine.mode != GameMode.PLAYING:
            return True

        self.finish_turn()
        return True

    def direction_vector(self, direction: str) -> Point | None:
        key = INPUT_TO_DIRECTION.get(direction, direction)
        vectors = {
            "UP": Point(0, -1),
            "DOWN": Point(0, 1),
            "LEFT": Point(-1, 0),
            "RIGHT": Point(1, 0),
        }
        return vectors.get(key)

    def preview_knock_path(self, direction: str) -> list[Point] | None:
        if self.engine.floor is None:
            return None
        vector = self.direction_vector(direction)
        if vector is None:
            return None
        point = self.engine.player.position
        path = [point]
        for _ in range(5):
            candidate = point + vector
            if (
                not self.engine.floor.in_bounds(candidate)
                or self.engine.floor.tile_at(candidate) == TileType.WALL
            ):
                break
            point = candidate
            path.append(point)
        return path

    def preview_knock_paths(self) -> dict[str, list[Point]]:
        return {
            direction: path
            for direction in ("w", "a", "s", "d")
            if (path := self.preview_knock_path(direction)) is not None
        }

    def preview_pounce_target(self, direction: str) -> Point | None:
        if self.engine.floor is None:
            return None
        vector = self.direction_vector(direction)
        if vector is None:
            return None
        near = self.engine.player.position + vector
        far = near + vector
        if self.engine.floor.is_walkable(far) and self.engine.floor.enemy_at(far) is None:
            return far
        if self.engine.floor.is_walkable(near) and self.engine.floor.enemy_at(near) is None:
            return near
        return None

    def preview_pounce_targets(self) -> dict[str, Point]:
        return {
            direction: target
            for direction in ("w", "a", "s", "d")
            if (target := self.preview_pounce_target(direction)) is not None
        }

    def move(self, direction: str) -> bool:
        if self.engine.floor is None:
            return False
        vector = self.direction_vector(direction)
        if vector is None:
            self.engine.add_log("Unknown direction.")
            return False
        origin = self.engine.player.position
        destination = self.engine.player.position + vector
        if not self.engine.floor.in_bounds(destination):
            self.engine.add_log("Metal. Wall. Whiskers.")
            return False
        if self.engine.floor.tile_at(destination) == TileType.WALL:
            self.engine.add_log("The vent wall stops you cold.")
            return False
        enemy = self.engine.floor.enemy_at(destination)
        if enemy:
            self.engine.run_records.end_run(
                f"The {enemy.enemy_type.name.lower()} catches you in the dark.",
                extracted=False,
            )
            return True
        item = self.engine.floor.item_at(destination)
        if item and item.kind == ItemType.MIMIC and not item.revealed:
            self.reveal_mimic(item)
            return True

        self.engine.player.position = destination
        self.push_effect(EffectKind.MOVE_TRAIL, [origin], CellColor.TRAIL, 1, "·")
        power_cost = 1
        if (
            self.engine.floor.tile_at(destination) == TileType.HEAT
            and ModuleType.THERMAL_LINING not in self.engine.player.modules
        ):
            power_cost += 1
            self.engine.add_log("The metal is hot enough to sting.")
        self.consume_turn(power_cost=power_cost, noise=0, noise_pos=destination)
        self.collect_items(destination)
        return True

    def hiss(self) -> bool:
        if self.engine.player.hiss_cooldown > 0:
            self.engine.add_log(f"Hiss cooling down: {self.engine.player.hiss_cooldown} turns.")
            return False
        self.engine.player.hiss_cooldown = 5
        scared_points: list[Point] = []
        for enemy in list(self.engine.floor.enemies if self.engine.floor else []):
            if enemy.position.distance(self.engine.player.position) != 1:
                continue
            if enemy.enemy_type in {EnemyType.CRAWLER, EnemyType.MIMIC}:
                enemy.scared_turns = 1
                enemy.alert = AlertState.SCARED
                scared_points.append(enemy.position)
        self.consume_turn(power_cost=1, noise=2, noise_pos=self.engine.player.position)
        if scared_points:
            self.push_effect(EffectKind.HISS, scared_points, CellColor.ENEMY_HOT, 2, "!")
            self.engine.add_log("A sharp hiss sends something skittering back.")
        else:
            self.engine.add_log("Your hiss rings down the vent.")
        self.engine.tutorial_once(
            "hiss_tip",
            "Tip: Hiss only hits adjacent crawlers and mimics. Save it for close calls.",
        )
        return True

    def hide(self) -> bool:
        self.engine.stats.hides_used += 1
        self.engine.player.hidden_turns = (
            3 if ModuleType.DEEP_HIDE in self.engine.player.modules else 2
        )
        reduction = 3
        if ModuleType.QUIET_HIDE in self.engine.player.modules:
            reduction += 2
        self.engine.current_noise = max(0, self.engine.current_noise - reduction)
        self.adjust_ship_alert(-1)
        if self.engine.current_noise == 0:
            self.engine.heard_position = None
        for enemy in list(self.engine.floor.enemies if self.engine.floor else []):
            if (
                enemy.enemy_type == EnemyType.STALKER
                and enemy.alert == AlertState.CHASING
                and enemy.position.distance(self.engine.player.position) > 1
            ):
                enemy.alert = AlertState.INVESTIGATING
                enemy.last_known_player = self.engine.heard_position
        self.consume_turn(power_cost=1, noise=0, noise_pos=self.engine.player.position, quiet=True)
        self.push_effect(
            EffectKind.HIDE, [self.engine.player.position], CellColor.RELAY_PULSE, 2, "◌"
        )
        self.engine.add_log("You flatten into the dark and hold still.")
        self.engine.tutorial_once(
            "hide_tip",
            "Tip: Hide is strongest after you break sightlines. "
            "It cools noise and shakes distant stalkers.",
        )
        return True

    def knock(self, direction: str) -> bool:
        noise_path = self.preview_knock_path(direction)
        if noise_path is None:
            self.engine.add_log("Unknown direction.")
            return False
        self.engine.stats.knocks_used += 1
        noise_point = noise_path[-1]
        self.engine.decoy_target = noise_point
        self.engine.decoy_turns = 2
        self.consume_turn(power_cost=1, noise=5, noise_pos=noise_point)
        self.push_effect(EffectKind.KNOCK, noise_path, CellColor.NOISE, 3, "◌")
        self.push_effect(EffectKind.KNOCK_FLASH, [noise_point], CellColor.NOISE_FLASH, 2, "◎")
        self.engine.add_log("You bat a loose panel down the corridor.")
        self.engine.tutorial_once(
            "knock_tip",
            "Tip: Knock plants a loud decoy for two enemy phases. "
            "Throw it past the lane you want to cross.",
        )
        return True

    def pounce(self, direction: str) -> bool:
        if self.engine.player.pounce_cooldown > 0:
            self.engine.add_log(f"Pounce cooling down: {self.engine.player.pounce_cooldown} turns.")
            return False
        destination = self.preview_pounce_target(direction)
        if destination is None:
            vector = self.direction_vector(direction)
            if vector is None:
                self.engine.add_log("Unknown direction.")
            else:
                self.engine.add_log("No place to land that pounce.")
            return False
        self.engine.stats.pounces_used += 1
        item = self.engine.floor.item_at(destination) if self.engine.floor else None
        if item and item.kind == ItemType.MIMIC and not item.revealed:
            self.reveal_mimic(item)
            self.engine.player.pounce_cooldown = 4
            return True
        self.engine.player.position = destination
        self.push_effect(EffectKind.MOVE_TRAIL, [destination], CellColor.TRAIL, 1, "▲")
        power_cost = 1 if ModuleType.LIGHT_PAWS in self.engine.player.modules else 2
        self.engine.player.pounce_cooldown = 4
        extra_heat = (
            1
            if self.engine.floor
            and self.engine.floor.tile_at(destination) == TileType.HEAT
            and ModuleType.THERMAL_LINING not in self.engine.player.modules
            else 0
        )
        self.consume_turn(power_cost=power_cost + extra_heat, noise=2, noise_pos=destination)
        if extra_heat:
            self.engine.add_log("You land in a wave of trapped heat.")
        self.collect_items(destination)
        self.engine.tutorial_once(
            "pounce_tip",
            "Tip: Pounce is burst movement. Use it to steal space or loot, "
            "not to drift into fresh danger.",
        )
        return True

    def collect_items(self, point: Point) -> None:
        if self.engine.floor is None:
            return
        while True:
            item = self.engine.floor.item_at(point)
            if item is None:
                return
            if item.kind == ItemType.BATTERY:
                self.engine.player.power += item.amount
                self.engine.stats.batteries_found += 1
                self.engine.floor.items.remove(item)
                self.engine.add_log(f"Battery found. Power +{item.amount}.")
                continue
            if item.kind == ItemType.SCRAP:
                self.engine.player.scrap += item.amount
                self.engine.score += item.amount * 15
                self.engine.floor.items.remove(item)
                self.engine.add_log(f"Scrap recovered. +{item.amount}.")
                continue
            return

    def spawn_enemy_near_player(self, *, min_distance: int) -> bool:
        if self.engine.floor is None:
            return False
        candidates: list[Point] = []
        occupied = {enemy.position for enemy in self.engine.floor.enemies}
        for radius in range(2, 5):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    point = Point(
                        self.engine.player.position.x + dx, self.engine.player.position.y + dy
                    )
                    if point == self.engine.player.position:
                        continue
                    if not self.engine.floor.in_bounds(point) or not self.engine.floor.is_walkable(
                        point
                    ):
                        continue
                    if (
                        point in occupied
                        or point.distance(self.engine.player.position) < min_distance
                    ):
                        continue
                    candidates.append(point)
            if candidates:
                break
        if not candidates:
            return False
        point = self.engine.rng.choice(candidates)
        enemy_type = (
            EnemyType.STALKER
            if self.engine.floor_number >= 3 and self.engine.rng.random() < 0.5
            else EnemyType.CRAWLER
        )
        self.engine.floor.enemies.append(
            Entity(
                enemy_type=enemy_type,
                position=point,
                home=point,
                alert=AlertState.INVESTIGATING,
                last_known_player=self.engine.player.position,
            )
        )
        return True

    def spawn_sweep_reinforcement(self) -> bool:
        floor = self.engine.floor
        if floor is None:
            return False
        occupied = {enemy.position for enemy in floor.enemies}
        candidates = [
            point
            for point in floor.iter_points()
            if floor.is_walkable(point)
            and point not in occupied
            and point != self.engine.player.position
            and point.distance(self.engine.player.position) >= 6
            and point.distance(floor.dock) >= 5
        ]
        if not candidates:
            return False
        ranked = sorted(
            candidates,
            key=lambda point: (
                point.distance(self.engine.player.position) + point.distance(floor.dock),
                self.engine.rng.random(),
            ),
            reverse=True,
        )
        point = self.engine.rng.choice(ranked[: min(8, len(ranked))])
        enemy_type = EnemyType.STALKER if self.engine.floor_number >= 2 else EnemyType.CRAWLER
        floor.enemies.append(
            Entity(
                enemy_type=enemy_type,
                position=point,
                home=point,
                alert=AlertState.INVESTIGATING,
                last_known_player=self.engine.heard_position or self.engine.player.position,
            )
        )
        return True

    def consume_turn(
        self,
        *,
        power_cost: int,
        noise: int,
        noise_pos: Point,
        quiet: bool = False,
    ) -> None:
        self.engine.player.power -= power_cost
        if noise:
            self.add_noise(noise, noise_pos)
        elif not quiet:
            self.engine.heard_position = noise_pos

    def add_noise(self, amount: int, point: Point) -> None:
        self.engine.current_noise = min(MAX_NOISE, self.engine.current_noise + amount)
        self.engine.heard_position = point
        self.engine.stats.max_noise = max(self.engine.stats.max_noise, self.engine.current_noise)
        self.engine.generated_noise_this_turn = True
        self.adjust_ship_alert(amount)

    def adjust_ship_alert(self, delta: int) -> None:
        if delta == 0:
            return
        old_value = self.engine.ship_alert
        new_value = max(0, min(MAX_SHIP_ALERT, old_value + delta))
        if new_value == old_value:
            return

        stage_order = [ShipAlertStage.CALM, ShipAlertStage.HUNT, ShipAlertStage.SWEEP]
        old_stage = self.engine.ship_alert_stage
        new_stage = self.engine.ship_alert_for_value(new_value)
        self.engine.ship_alert = new_value
        self.engine.stats.max_alert = max(self.engine.stats.max_alert, new_value)

        old_index = stage_order.index(old_stage)
        new_index = stage_order.index(new_stage)
        if old_index == new_index:
            return

        step = 1 if new_index > old_index else -1
        for index in range(old_index + step, new_index + step, step):
            stage = stage_order[index]
            rising = step > 0
            self.engine.add_log(self.alert_stage_message(stage, rising))
            if rising and stage == ShipAlertStage.SWEEP:
                self.trigger_sweep_response()
            if rising and stage == ShipAlertStage.HUNT:
                self.engine.tutorial_once(
                    "hunt_tip",
                    "Tip: HUNT means the ship is listening. "
                    "Knock can pull patrols off your route before SWEEP starts.",
                )
            if rising and stage == ShipAlertStage.SWEEP:
                self.engine.tutorial_once(
                    "sweep_tip",
                    "Tip: SWEEP punishes noise. Break line of sight, then hide "
                    "or wait to bleed alert back down.",
                )

    def alert_stage_message(self, stage: ShipAlertStage, rising: bool) -> str:
        if rising:
            messages = {
                ShipAlertStage.HUNT: "Ship alert rises to HUNT.",
                ShipAlertStage.SWEEP: "Ship alert rises to SWEEP.",
            }
            return messages.get(stage, "Ship alert shifts.")
        messages = {
            ShipAlertStage.HUNT: "Ship alert drops to HUNT.",
            ShipAlertStage.CALM: "Ship alert settles to CALM.",
        }
        return messages.get(stage, "Ship alert eases.")

    def trigger_sweep_response(self) -> None:
        if self.engine.floor is None:
            return
        if not self.engine.floor_sweep_spawned:
            spawned = self.spawn_sweep_reinforcement()
            self.engine.floor_sweep_spawned = True
            if spawned:
                self.engine.add_log("Reinforcement claws into the ducts.")
        if self.engine.heard_position is None:
            return
        for enemy in self.engine.floor.enemies:
            enemy.alert = AlertState.INVESTIGATING
            enemy.last_known_player = self.engine.heard_position

    def run_enemy_phase(self) -> None:
        if self.engine.floor is None:
            return
        occupied = {enemy.position for enemy in self.engine.floor.enemies}
        for enemy in list(self.engine.floor.enemies):
            occupied.discard(enemy.position)
            previous_alert = enemy.alert
            enemy_turn = advance_enemy(
                enemy,
                self.engine.floor,
                self.engine.player.position,
                player_hidden=self.engine.player.hidden_turns > 0,
                ship_alert_stage=self.engine.ship_alert_stage,
                noise=self.engine.current_noise,
                noise_pos=self.engine.heard_position,
                decoy_target=self.engine.decoy_target,
                occupied=occupied,
                rng=self.engine.rng,
            )
            if enemy_turn.attacked or enemy_turn.destination == self.engine.player.position:
                self.push_effect(
                    EffectKind.ENEMY_SPOT, [enemy.position], CellColor.ENEMY_HOT, 2, "✸"
                )
                self.engine.run_records.end_run(
                    f"The {enemy.enemy_type.name.lower()} finds you.",
                    extracted=False,
                )
                return
            enemy.position = enemy_turn.destination
            if enemy.alert == AlertState.CHASING and previous_alert != AlertState.CHASING:
                self.push_effect(
                    EffectKind.ENEMY_SPOT, [enemy.position], CellColor.ENEMY_HOT, 2, "✸"
                )
                if enemy.enemy_type == EnemyType.STALKER:
                    self.engine.tutorial_once(
                        "stalker_tip",
                        "Tip: Stalkers keep pressure until you break line of sight, "
                        "then hide while they search.",
                    )
            occupied.add(enemy.position)

    def finish_turn(self) -> None:
        noise_snapshot = self.engine.current_noise
        if noise_snapshot <= 1:
            self.engine.stats.quiet_turns += 1
        if noise_snapshot >= 6:
            self.engine.stats.loud_turns += 1
            self.adjust_ship_alert(1)
        if not self.engine.generated_noise_this_turn:
            self.adjust_ship_alert(-1)
        self.engine.noise_history.append(noise_snapshot)
        if self.engine.current_noise > 0:
            self.engine.current_noise -= 1
        if self.engine.current_noise == 0:
            self.engine.heard_position = None
        if self.engine.player.hidden_turns > 0:
            self.engine.player.hidden_turns -= 1
        if self.engine.decoy_turns > 0:
            self.engine.decoy_turns -= 1
            if self.engine.decoy_turns == 0:
                self.engine.decoy_target = None
        self.engine.generated_noise_this_turn = False
        self.update_visibility()

    def update_visibility(self) -> None:
        if self.engine.floor is None:
            return
        vision_radius = VISION_RADIUS
        if self.engine.floor.condition == FloorCondition.TRAINING:
            vision_radius += 1
        elif self.engine.floor.condition == FloorCondition.LOW_LIGHT:
            vision_radius = max(4, VISION_RADIUS - 2)
        visible: set[Point] = set()
        for point in self.engine.floor.iter_points():
            if self.engine.player.position.distance(point) > vision_radius:
                continue
            if line_of_sight(self.engine.floor, self.engine.player.position, point):
                visible.add(point)
        self.engine.floor.visible = visible
        self.engine.floor.explored.update(visible)

    def tick_cooldowns(self) -> None:
        if self.engine.player.hiss_cooldown > 0:
            self.engine.player.hiss_cooldown -= 1
        if self.engine.player.pounce_cooldown > 0:
            self.engine.player.pounce_cooldown -= 1

    def reveal_mimic(self, item: Item) -> None:
        if self.engine.floor is None:
            return
        item.revealed = True
        self.engine.floor.items.remove(item)
        self.engine.floor.enemies.append(
            Entity(
                enemy_type=EnemyType.MIMIC,
                position=item.position,
                home=item.position,
                alert=AlertState.CHASING,
                last_known_player=self.engine.player.position,
                wake_delay=1,
            )
        )
        self.consume_turn(power_cost=1, noise=5, noise_pos=item.position)
        self.push_effect(EffectKind.MIMIC, [item.position], CellColor.ENEMY_HOT, 3, "◆")
        self.engine.add_log("The battery screams. It was waiting for you.")

    def push_effect(
        self,
        kind: EffectKind,
        points: list[Point],
        color: CellColor,
        frames: int,
        glyph: str,
    ) -> None:
        self.engine.last_turn_effects.append(
            RenderEffect(
                kind=kind,
                points=list(points),
                color=color,
                frames=frames,
                glyph=glyph,
            )
        )

    def reset_noise_history(self) -> None:
        self.engine.noise_history = deque([0] * NOISE_HISTORY_LENGTH, maxlen=NOISE_HISTORY_LENGTH)
