from __future__ import annotations

import random
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import combinations, permutations

from .models import (
    MAP_HEIGHT,
    MAP_WIDTH,
    MAX_POWER,
    AlertState,
    EnemyType,
    Entity,
    FloorCondition,
    FloorObjective,
    FloorState,
    Item,
    ItemType,
    Point,
    TileType,
)


@dataclass(frozen=True)
class Room:
    x: int
    y: int
    width: int
    height: int

    @property
    def center(self) -> Point:
        return Point(self.x + self.width // 2, self.y + self.height // 2)

    def intersects(self, other: Room, padding: int = 1) -> bool:
        return not (
            self.x + self.width + padding <= other.x
            or other.x + other.width + padding <= self.x
            or self.y + self.height + padding <= other.y
            or other.y + other.height + padding <= self.y
        )


def relay_quota(floor_number: int) -> int:
    if floor_number >= 5:
        return 4
    if floor_number >= 3:
        return 3
    return 2


def generate_floor(
    floor_number: int,
    rng: random.Random,
    condition: FloorCondition = FloorCondition.STANDARD,
) -> FloorState:
    rooms = _generate_rooms(rng)
    tiles = [[TileType.WALL for _ in range(MAP_WIDTH)] for _ in range(MAP_HEIGHT)]
    for room in rooms:
        _carve_room(tiles, room)
    _connect_rooms(tiles, rooms, rng)
    _add_loops(tiles, rooms, rng)

    dock_room = _choose_dock_room(rooms)
    dock = dock_room.center
    tiles[dock.y][dock.x] = TileType.DOCK

    distance_map = _distance_map(tiles, dock)
    objective = FloorObjective(required_relays=relay_quota(floor_number))

    relay_points = _choose_relay_points(
        tiles, rooms, dock_room, dock, distance_map, objective.required_relays, floor_number
    )
    for point in relay_points:
        tiles[point.y][point.x] = TileType.RELAY

    special_points = {dock, *relay_points}
    open_cells = [
        point
        for point, tile in _iter_tiles(tiles)
        if tile == TileType.FLOOR and point not in special_points
    ]
    dead_ends = [point for point in open_cells if _walkable_degree(tiles, point) <= 1]
    far_cells = sorted(
        open_cells,
        key=lambda point: (distance_map.get(point, -1), rng.random()),
        reverse=True,
    )
    dead_end_cells = sorted(
        dead_ends,
        key=lambda point: (distance_map.get(point, -1), rng.random()),
        reverse=True,
    )

    occupied = set(special_points)
    items: list[Item] = []

    def take_cells(pool: list[Point], count: int) -> list[Point]:
        chosen: list[Point] = []
        for point in pool:
            if point in occupied:
                continue
            occupied.add(point)
            chosen.append(point)
            if len(chosen) >= count:
                break
        return chosen

    battery_count = min(3 + floor_number // 2, max(3, len(far_cells) // 8))
    scrap_count = min(3 + floor_number, max(4, len(far_cells) // 6))
    signal_count = 2 if floor_number < 4 else 3
    heat_count = 3 + min(3, floor_number)

    if condition == FloorCondition.TRAINING:
        battery_count += 1
        signal_count = min(signal_count, 1)
        heat_count = 0
    elif condition == FloorCondition.HOT_DECK:
        battery_count += 1
        heat_count += 2
    elif condition == FloorCondition.SIGNAL_SURGE:
        signal_count += 2
        scrap_count = max(3, scrap_count - 1)

    starter_battery = _starter_battery_cell(open_cells, occupied, distance_map)
    if starter_battery is not None:
        occupied.add(starter_battery)
        items.append(Item(ItemType.BATTERY, starter_battery, amount=rng.randint(10, 14)))

    remaining_batteries = max(
        0, battery_count - len([item for item in items if item.kind == ItemType.BATTERY])
    )
    for point in take_cells(dead_end_cells + far_cells, remaining_batteries):
        items.append(Item(ItemType.BATTERY, point, amount=rng.randint(11, 16)))
    for point in take_cells(dead_end_cells + far_cells, scrap_count):
        items.append(Item(ItemType.SCRAP, point, amount=rng.randint(1, 2)))
    for point in take_cells(dead_end_cells + far_cells, signal_count):
        items.append(Item(ItemType.SIGNAL, point))

    if floor_number >= 2 and condition != FloorCondition.TRAINING:
        mimic_cell = next((point for point in far_cells if point not in occupied), None)
        if mimic_cell:
            occupied.add(mimic_cell)
            items.append(Item(ItemType.MIMIC, mimic_cell, amount=rng.randint(8, 12)))

    heat_candidates = [
        point
        for point in far_cells
        if point not in occupied and _walkable_degree(tiles, point) == 2
    ]
    for point in heat_candidates[:heat_count]:
        tiles[point.y][point.x] = TileType.HEAT
        occupied.add(point)

    enemies = _generate_enemies(floor_number, far_cells, occupied, dock, rng, condition)

    return FloorState(
        width=MAP_WIDTH,
        height=MAP_HEIGHT,
        tiles=tiles,
        dock=dock,
        objective=objective,
        items=items,
        enemies=enemies,
        condition=condition,
    )


def _generate_rooms(rng: random.Random) -> list[Room]:
    desired = rng.randint(6, 9)
    rooms: list[Room] = []
    for _ in range(64):
        room = Room(
            x=rng.randint(1, MAP_WIDTH - 8),
            y=rng.randint(1, MAP_HEIGHT - 6),
            width=rng.randint(4, 7),
            height=rng.randint(3, 5),
        )
        if any(room.intersects(existing) for existing in rooms):
            continue
        rooms.append(room)
        if len(rooms) >= desired:
            break
    if len(rooms) < 6:
        fallback = [
            Room(2, 2, 5, 4),
            Room(10, 1, 6, 4),
            Room(19, 2, 6, 4),
            Room(27, 3, 5, 4),
            Room(6, 9, 6, 4),
            Room(18, 9, 7, 4),
        ]
        return fallback
    return rooms


def _choose_dock_room(rooms: list[Room]) -> Room:
    edge_sorted = sorted(rooms, key=lambda room: _edge_distance(room.center))
    candidate_count = min(len(rooms), max(2, len(rooms) // 3))
    candidates = edge_sorted[:candidate_count]
    return min(
        candidates,
        key=lambda room: sum(
            room.center.distance(other.center) for other in rooms if other is not room
        ),
    )


def _choose_relay_points(
    tiles: list[list[TileType]],
    rooms: list[Room],
    dock_room: Room,
    dock: Point,
    distance_map: dict[Point, int],
    required_relays: int,
    floor_number: int,
) -> list[Point]:
    candidates = [room.center for room in rooms if room != dock_room]
    pair_maps = {point: _distance_map(tiles, point) for point in [dock, *candidates]}
    budget = _relay_route_budget(floor_number)

    best_combo: tuple[Point, ...] | None = None
    best_key: tuple[int, int, int, int] | None = None
    for combo in combinations(candidates, required_relays):
        route_cost = _minimum_route_cost(dock, combo, pair_maps)
        over_budget = max(0, route_cost - budget)
        distance_score = sum(distance_map.get(point, 0) for point in combo)
        nearest_distance = min(distance_map.get(point, 0) for point in combo)
        key = (-over_budget, distance_score, nearest_distance, -route_cost)
        if best_key is None or key > best_key:
            best_key = key
            best_combo = combo
    if best_combo is None:
        raise ValueError("No relay placement candidates found")
    return list(best_combo)


def _relay_route_budget(floor_number: int) -> int:
    if floor_number >= 5:
        return MAX_POWER
    if floor_number >= 3:
        return MAX_POWER - 4
    return MAX_POWER - 8


def _minimum_route_cost(
    dock: Point,
    relays: tuple[Point, ...],
    pair_maps: dict[Point, dict[Point, int]],
) -> int:
    best = 10**9
    for order in permutations(relays):
        route_cost = 0
        current = dock
        for point in order:
            route_cost += pair_maps[current][point]
            current = point
        route_cost += pair_maps[current][dock]
        best = min(best, route_cost)
    return best


def _starter_battery_cell(
    open_cells: list[Point],
    occupied: set[Point],
    distance_map: dict[Point, int],
) -> Point | None:
    preferred = sorted(
        (
            point
            for point in open_cells
            if point not in occupied and 4 <= distance_map.get(point, 0) <= 8
        ),
        key=lambda point: (distance_map.get(point, 0), -point.y, point.x),
        reverse=True,
    )
    if preferred:
        return preferred[0]
    fallback = sorted(
        (point for point in open_cells if point not in occupied),
        key=lambda point: distance_map.get(point, 0),
    )
    return fallback[0] if fallback else None


def _carve_room(tiles: list[list[TileType]], room: Room) -> None:
    for y in range(room.y, room.y + room.height):
        for x in range(room.x, room.x + room.width):
            tiles[y][x] = TileType.FLOOR


def _connect_rooms(tiles: list[list[TileType]], rooms: list[Room], rng: random.Random) -> None:
    ordered = sorted(rooms, key=lambda room: room.center.x)
    for room_a, room_b in zip(ordered, ordered[1:], strict=False):
        if rng.random() < 0.5:
            _carve_h_corridor(tiles, room_a.center.x, room_b.center.x, room_a.center.y)
            _carve_v_corridor(tiles, room_a.center.y, room_b.center.y, room_b.center.x)
        else:
            _carve_v_corridor(tiles, room_a.center.y, room_b.center.y, room_a.center.x)
            _carve_h_corridor(tiles, room_a.center.x, room_b.center.x, room_b.center.y)


def _add_loops(tiles: list[list[TileType]], rooms: list[Room], rng: random.Random) -> None:
    pairs = []
    for index, room in enumerate(rooms):
        for other in rooms[index + 2 :]:
            pairs.append((room, other))
    rng.shuffle(pairs)
    for room_a, room_b in pairs[: rng.randint(2, 3)]:
        _carve_h_corridor(tiles, room_a.center.x, room_b.center.x, room_a.center.y)
        _carve_v_corridor(tiles, room_a.center.y, room_b.center.y, room_b.center.x)


def _carve_h_corridor(tiles: list[list[TileType]], start_x: int, end_x: int, y: int) -> None:
    for x in range(min(start_x, end_x), max(start_x, end_x) + 1):
        tiles[y][x] = TileType.FLOOR


def _carve_v_corridor(tiles: list[list[TileType]], start_y: int, end_y: int, x: int) -> None:
    for y in range(min(start_y, end_y), max(start_y, end_y) + 1):
        tiles[y][x] = TileType.FLOOR


def _distance_map(tiles: list[list[TileType]], start: Point) -> dict[Point, int]:
    distances = {start: 0}
    queue: deque[Point] = deque([start])
    while queue:
        current = queue.popleft()
        for neighbor in _neighbors(current):
            if not _point_in_bounds(neighbor):
                continue
            if tiles[neighbor.y][neighbor.x] == TileType.WALL:
                continue
            if neighbor in distances:
                continue
            distances[neighbor] = distances[current] + 1
            queue.append(neighbor)
    return distances


def _generate_enemies(
    floor_number: int,
    far_cells: list[Point],
    occupied: set[Point],
    dock: Point,
    rng: random.Random,
    condition: FloorCondition,
) -> list[Entity]:
    enemies: list[Entity] = []

    def take_enemy_spots(count: int) -> list[Point]:
        if count <= 0:
            return []
        chosen: list[Point] = []
        for point in far_cells:
            if point in occupied or point.distance(dock) < 6:
                continue
            occupied.add(point)
            chosen.append(point)
            if len(chosen) >= count:
                break
        return chosen

    crawler_count = min(1 + floor_number // 2, 4)
    stalker_count = 1 if floor_number >= 2 else 0
    if floor_number >= 4:
        stalker_count += 1

    if condition == FloorCondition.TRAINING:
        crawler_count = 1
        stalker_count = 0
    elif condition == FloorCondition.LOW_LIGHT:
        crawler_count = max(1, crawler_count - 1)

    for point in take_enemy_spots(crawler_count):
        enemies.append(Entity(enemy_type=EnemyType.CRAWLER, position=point, home=point))
    for point in take_enemy_spots(stalker_count):
        enemies.append(
            Entity(
                enemy_type=EnemyType.STALKER,
                position=point,
                home=point,
                patrol_target=point,
                alert=AlertState.DORMANT,
            )
        )
    return enemies


def _edge_distance(point: Point) -> int:
    return min(point.x, MAP_WIDTH - 1 - point.x, point.y, MAP_HEIGHT - 1 - point.y)


def _walkable_degree(tiles: list[list[TileType]], point: Point) -> int:
    return sum(
        1
        for neighbor in _neighbors(point)
        if _point_in_bounds(neighbor) and tiles[neighbor.y][neighbor.x] != TileType.WALL
    )


def _iter_tiles(tiles: list[list[TileType]]) -> Iterator[tuple[Point, TileType]]:
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            yield Point(x, y), tile


def _neighbors(point: Point) -> list[Point]:
    return [
        Point(point.x + 1, point.y),
        Point(point.x - 1, point.y),
        Point(point.x, point.y + 1),
        Point(point.x, point.y - 1),
    ]


def _point_in_bounds(point: Point) -> bool:
    return 0 <= point.x < MAP_WIDTH and 0 <= point.y < MAP_HEIGHT
