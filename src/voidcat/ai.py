from __future__ import annotations

import random
from collections import deque
from copy import deepcopy
from dataclasses import dataclass

from .models import AlertState, EnemyType, Entity, FloorState, Point, ShipAlertStage, TileType


@dataclass
class EnemyTurn:
    destination: Point
    attacked: bool = False


def advance_enemy(
    enemy: Entity,
    floor: FloorState,
    player_pos: Point,
    *,
    player_hidden: bool,
    ship_alert_stage: ShipAlertStage,
    noise: int,
    noise_pos: Point | None,
    decoy_target: Point | None,
    occupied: set[Point],
    rng: random.Random,
) -> EnemyTurn:
    if enemy.wake_delay > 0:
        enemy.wake_delay -= 1
        return EnemyTurn(enemy.position)
    if enemy.scared_turns > 0:
        enemy.alert = AlertState.SCARED
        enemy.scared_turns -= 1
        step = next_step_away(floor, enemy.position, player_pos, occupied)
        return EnemyTurn(step or enemy.position)

    if enemy.enemy_type in {EnemyType.CRAWLER, EnemyType.MIMIC}:
        return _advance_crawler(
            enemy,
            floor,
            player_pos,
            noise,
            noise_pos,
            decoy_target,
            occupied,
            rng,
        )
    return _advance_stalker(
        enemy,
        floor,
        player_pos,
        player_hidden,
        ship_alert_stage,
        noise,
        noise_pos,
        decoy_target,
        occupied,
        rng,
    )


def preview_enemy_turn(
    enemy: Entity,
    floor: FloorState,
    player_pos: Point,
    *,
    player_hidden: bool,
    ship_alert_stage: ShipAlertStage,
    noise: int,
    noise_pos: Point | None,
    decoy_target: Point | None,
    occupied: set[Point],
    rng: random.Random,
) -> EnemyTurn:
    simulated = deepcopy(enemy)
    preview_rng = random.Random()
    preview_rng.setstate(rng.getstate())
    return advance_enemy(
        simulated,
        floor,
        player_pos,
        player_hidden=player_hidden,
        ship_alert_stage=ship_alert_stage,
        noise=noise,
        noise_pos=noise_pos,
        decoy_target=decoy_target,
        occupied=occupied,
        rng=preview_rng,
    )


def _advance_crawler(
    enemy: Entity,
    floor: FloorState,
    player_pos: Point,
    noise: int,
    noise_pos: Point | None,
    decoy_target: Point | None,
    occupied: set[Point],
    rng: random.Random,
) -> EnemyTurn:
    if enemy.position.distance(player_pos) == 1:
        enemy.alert = AlertState.CHASING
        return EnemyTurn(player_pos, attacked=True)

    if decoy_target and enemy.position != decoy_target:
        enemy.alert = AlertState.INVESTIGATING
        enemy.last_known_player = decoy_target
        step = next_step_towards(floor, enemy.position, decoy_target, occupied)
        return EnemyTurn(step or enemy.position)

    if noise_pos and noise > 0:
        enemy.alert = AlertState.INVESTIGATING
        enemy.last_known_player = noise_pos
        step = next_step_towards(floor, enemy.position, noise_pos, occupied)
        return EnemyTurn(step or enemy.position)

    if enemy.last_known_player and enemy.position != enemy.last_known_player:
        step = next_step_towards(floor, enemy.position, enemy.last_known_player, occupied)
        if step:
            return EnemyTurn(step)
    enemy.last_known_player = None

    wander = random_walkable_neighbor(floor, enemy.position, occupied, rng)
    return EnemyTurn(wander or enemy.position)


def _advance_stalker(
    enemy: Entity,
    floor: FloorState,
    player_pos: Point,
    player_hidden: bool,
    ship_alert_stage: ShipAlertStage,
    noise: int,
    noise_pos: Point | None,
    decoy_target: Point | None,
    occupied: set[Point],
    rng: random.Random,
) -> EnemyTurn:
    if ship_alert_stage in {ShipAlertStage.HUNT, ShipAlertStage.SWEEP}:
        sight_range = 9
        noise_threshold = 2
        noise_range = 12
    else:
        sight_range = 7
        noise_threshold = 4
        noise_range = 10

    sees_player = (
        not player_hidden
        and line_of_sight(floor, enemy.position, player_pos)
        and enemy.position.distance(player_pos) <= sight_range
    )

    if sees_player:
        enemy.alert = AlertState.CHASING
        enemy.last_known_player = player_pos
    elif (
        player_hidden
        and enemy.alert == AlertState.CHASING
        and enemy.position.distance(player_pos) > 1
    ):
        enemy.alert = AlertState.INVESTIGATING
        enemy.last_known_player = noise_pos
    elif decoy_target and enemy.position.distance(decoy_target) <= noise_range + 2:
        enemy.alert = AlertState.INVESTIGATING
        enemy.last_known_player = decoy_target
    elif (
        noise_pos and noise >= noise_threshold and enemy.position.distance(noise_pos) <= noise_range
    ):
        enemy.alert = AlertState.INVESTIGATING
        enemy.last_known_player = noise_pos

    if enemy.position.distance(player_pos) == 1 and enemy.alert == AlertState.CHASING:
        return EnemyTurn(player_pos, attacked=True)

    if enemy.alert == AlertState.CHASING and enemy.last_known_player:
        step = next_step_towards(floor, enemy.position, enemy.last_known_player, occupied)
        if step:
            return EnemyTurn(step)
        enemy.alert = AlertState.INVESTIGATING

    if enemy.alert == AlertState.INVESTIGATING and enemy.last_known_player:
        if enemy.position == enemy.last_known_player:
            enemy.alert = AlertState.DORMANT
            enemy.last_known_player = None
        else:
            step = next_step_towards(floor, enemy.position, enemy.last_known_player, occupied)
            if step:
                return EnemyTurn(step)

    if enemy.patrol_target is None or enemy.position == enemy.patrol_target:
        enemy.patrol_target = pick_patrol_target(floor, enemy.home or enemy.position, rng)
    step = next_step_towards(floor, enemy.position, enemy.patrol_target, occupied)
    return EnemyTurn(step or enemy.position)


def line_of_sight(floor: FloorState, start: Point, end: Point) -> bool:
    forward = _bresenham_line(start, end)
    backward = list(reversed(_bresenham_line(end, start)))
    return _line_is_clear(floor, forward) and _line_is_clear(floor, backward)


def _line_is_clear(floor: FloorState, points: list[Point]) -> bool:
    for point in points[1:-1]:
        if floor.tile_at(point) == TileType.WALL:
            return False
    return True


def next_step_towards(
    floor: FloorState,
    start: Point,
    goal: Point,
    occupied: set[Point],
) -> Point | None:
    if start == goal:
        return start
    path = shortest_path(floor, start, goal, occupied)
    if len(path) >= 2:
        return path[1]
    return None


def next_step_away(
    floor: FloorState,
    start: Point,
    threat: Point,
    occupied: set[Point],
) -> Point | None:
    best: Point | None = None
    best_distance = start.distance(threat)
    for neighbor in orthogonal_neighbors(start):
        if not floor.is_walkable(neighbor):
            continue
        if neighbor in occupied:
            continue
        distance = neighbor.distance(threat)
        if distance > best_distance:
            best_distance = distance
            best = neighbor
    return best


def random_walkable_neighbor(
    floor: FloorState,
    start: Point,
    occupied: set[Point],
    rng: random.Random,
) -> Point | None:
    candidates = [
        point
        for point in orthogonal_neighbors(start)
        if floor.is_walkable(point) and point not in occupied
    ]
    if not candidates:
        return None
    return rng.choice(candidates)


def pick_patrol_target(floor: FloorState, home: Point, rng: random.Random) -> Point:
    candidates = [point for point in orthogonal_neighbors(home) if floor.is_walkable(point)]
    if not candidates:
        return home
    return rng.choice(candidates)


def shortest_path(
    floor: FloorState,
    start: Point,
    goal: Point,
    occupied: set[Point],
) -> list[Point]:
    blocked = {point for point in occupied if point != goal}
    queue: deque[Point] = deque([start])
    came_from: dict[Point, Point | None] = {start: None}
    while queue:
        current = queue.popleft()
        if current == goal:
            break
        for neighbor in orthogonal_neighbors(current):
            if neighbor in came_from:
                continue
            if neighbor in blocked:
                continue
            if not floor.is_walkable(neighbor):
                continue
            came_from[neighbor] = current
            queue.append(neighbor)
    if goal not in came_from:
        return [start]
    path = [goal]
    current = goal
    while True:
        previous = came_from[current]
        if previous is None:
            break
        current = previous
        path.append(previous)
    path.reverse()
    return path


def orthogonal_neighbors(point: Point) -> list[Point]:
    return [
        Point(point.x + 1, point.y),
        Point(point.x - 1, point.y),
        Point(point.x, point.y + 1),
        Point(point.x, point.y - 1),
    ]


def _bresenham_line(start: Point, end: Point) -> list[Point]:
    points: list[Point] = []
    x1, y1 = start.x, start.y
    x2, y2 = end.x, end.y
    dx = abs(x2 - x1)
    dy = -abs(y2 - y1)
    sx = 1 if x1 < x2 else -1
    sy = 1 if y1 < y2 else -1
    error = dx + dy

    while True:
        points.append(Point(x1, y1))
        if x1 == x2 and y1 == y2:
            break
        double_error = 2 * error
        if double_error >= dy:
            error += dy
            x1 += sx
        if double_error <= dx:
            error += dx
            y1 += sy
    return points
