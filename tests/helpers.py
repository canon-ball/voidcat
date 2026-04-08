from __future__ import annotations

from collections import deque
from pathlib import Path

from voidcat.engine import GameEngine
from voidcat.models import (
    MAX_POWER,
    NOISE_HISTORY_LENGTH,
    AlertState,
    EnemyType,
    Entity,
    FloorObjective,
    FloorState,
    GameMode,
    Item,
    ItemType,
    PlayerState,
    Point,
    RunStats,
    TileType,
)


class FakeWindow:
    def __init__(
        self,
        *,
        height: int = 32,
        width: int = 120,
        keycodes: list[int] | None = None,
    ) -> None:
        self.height = height
        self.width = width
        self.keycodes = list(keycodes or [])
        self.lines: list[str] = []
        self.operations: list[tuple[str, int, int, str, int, int]] = []
        self.refreshed = False
        self.keypad_enabled = False

    def getmaxyx(self) -> tuple[int, int]:
        return self.height, self.width

    def erase(self) -> None:
        self.lines.clear()

    def addnstr(self, y: int, x: int, text: str, limit: int, attrs: int = 0) -> None:
        chunk = text[:limit]
        self.lines.append(chunk)
        self.operations.append(("addnstr", y, x, chunk, limit, attrs))

    def addstr(self, y: int, x: int, text: str, attrs: int = 0) -> None:
        self.lines.append(text)
        self.operations.append(("addstr", y, x, text, len(text), attrs))

    def refresh(self) -> None:
        self.refreshed = True

    def getch(self) -> int:
        return self.keycodes.pop(0)

    def keypad(self, flag: bool) -> None:
        self.keypad_enabled = flag


def build_box_floor(
    *,
    width: int = 7,
    height: int = 7,
    dock: Point | None = None,
    relays: list[Point] | None = None,
    items: list[Item] | None = None,
    enemies: list[Entity] | None = None,
    heat: list[Point] | None = None,
) -> FloorState:
    dock = dock or Point(1, 1)
    relays = relays or []
    items = items or []
    enemies = enemies or []
    heat = heat or []
    tiles = [[TileType.WALL for _ in range(width)] for _ in range(height)]
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            tiles[y][x] = TileType.FLOOR
    tiles[dock.y][dock.x] = TileType.DOCK
    for point in relays:
        tiles[point.y][point.x] = TileType.RELAY
    for point in heat:
        tiles[point.y][point.x] = TileType.HEAT
    return FloorState(
        width=width,
        height=height,
        tiles=tiles,
        dock=dock,
        objective=FloorObjective(required_relays=len(relays)),
        items=items,
        enemies=enemies,
    )


def build_engine(
    floor: FloorState,
    *,
    score_file: Path,
    power: int = 10,
) -> GameEngine:
    engine = GameEngine(seed=7, score_file=score_file)
    engine.floor = floor
    engine.floor_number = 1
    engine.current_floor_condition = floor.condition
    engine.floor_condition_history = [floor.condition]
    engine.player = PlayerState(
        position=floor.dock, power=power, power_capacity=max(power, MAX_POWER)
    )
    engine.score = 0
    engine.mode = GameMode.PLAYING
    engine.current_noise = 0
    engine.ship_alert = 0
    engine.heard_position = None
    engine.logs.clear()
    engine.stats = RunStats()
    engine.noise_history = deque([0] * NOISE_HISTORY_LENGTH, maxlen=NOISE_HISTORY_LENGTH)
    engine.generated_noise_this_turn = False
    engine.restored_relays = set()
    engine.decoy_target = None
    engine.decoy_turns = 0
    engine.last_turn_effects = []
    engine.floor_sweep_spawned = False
    engine.dock_offers = []
    engine.dock_purchase_made = False
    engine.dock_purchase_index = None
    engine.extraction_bonus = 0
    engine.current_run_saved = False
    engine._update_visibility()
    return engine


def crawler(point: Point) -> Entity:
    return Entity(enemy_type=EnemyType.CRAWLER, position=point, home=point)


def stalker(point: Point, *, alert: AlertState = AlertState.DORMANT) -> Entity:
    return Entity(
        enemy_type=EnemyType.STALKER,
        position=point,
        home=point,
        patrol_target=point,
        alert=alert,
    )


def battery(point: Point, amount: int = 5) -> Item:
    return Item(ItemType.BATTERY, point, amount=amount)


def scrap(point: Point, amount: int = 1) -> Item:
    return Item(ItemType.SCRAP, point, amount=amount)


def signal(point: Point) -> Item:
    return Item(ItemType.SIGNAL, point)


def mimic(point: Point, amount: int = 8) -> Item:
    return Item(ItemType.MIMIC, point, amount=amount)
