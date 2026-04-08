from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum, auto

MAP_WIDTH = 35
MAP_HEIGHT = 15
MAX_POWER = 52
MAX_NOISE = 9
MIN_TERM_WIDTH = 80
MIN_TERM_HEIGHT = 24
VISION_RADIUS = 6
MAX_LOG_LINES = 4
MAX_HIGH_SCORES = 10
RELAY_RECHARGE = 6
MAX_SHIP_ALERT = 12
SIDEBAR_WIDTH = 22
NOISE_HISTORY_LENGTH = 8


class TileType(Enum):
    WALL = "▓"
    FLOOR = "·"
    DOCK = "⌂"
    RELAY = "◇"
    HEAT = "≈"


class ItemType(Enum):
    BATTERY = auto()
    SCRAP = auto()
    SIGNAL = auto()
    MIMIC = auto()


class EnemyType(Enum):
    CRAWLER = "◍"
    STALKER = "▲"
    MIMIC = "◆"


class ActionType(Enum):
    MOVE = auto()
    INTERACT = auto()
    HISS = auto()
    HIDE = auto()
    KNOCK = auto()
    POUNCE = auto()
    WAIT = auto()


class AlertState(Enum):
    DORMANT = auto()
    INVESTIGATING = auto()
    CHASING = auto()
    SCARED = auto()


class GameMode(Enum):
    PLAYING = auto()
    DOCK_SHOP = auto()
    GAME_OVER = auto()


class FloorCondition(Enum):
    STANDARD = auto()
    TRAINING = auto()
    LOW_LIGHT = auto()
    HOT_DECK = auto()
    SIGNAL_SURGE = auto()

    @property
    def label(self) -> str:
        labels = {
            FloorCondition.STANDARD: "Standard Deck",
            FloorCondition.TRAINING: "Training Deck",
            FloorCondition.LOW_LIGHT: "Low Light",
            FloorCondition.HOT_DECK: "Hot Deck",
            FloorCondition.SIGNAL_SURGE: "Signal Surge",
        }
        return labels[self]

    @property
    def summary(self) -> str:
        summaries = {
            FloorCondition.STANDARD: "Balanced patrol routes and ordinary ship systems.",
            FloorCondition.TRAINING: "Lighter patrol load and cleaner routes for onboarding.",
            FloorCondition.LOW_LIGHT: (
                "Shorter sightlines, tighter visibility, and safer crossings."
            ),
            FloorCondition.HOT_DECK: "More heat pockets but richer battery routing.",
            FloorCondition.SIGNAL_SURGE: (
                "More ship chatter, more signal gambles, more loot routes."
            ),
        }
        return summaries[self]


class BuildPath(Enum):
    STEALTH = auto()
    MOBILITY = auto()
    SCAVENGER = auto()

    @property
    def label(self) -> str:
        labels = {
            BuildPath.STEALTH: "Stealth Route",
            BuildPath.MOBILITY: "Mobility Route",
            BuildPath.SCAVENGER: "Scavenger Route",
        }
        return labels[self]

    @property
    def summary(self) -> str:
        summaries = {
            BuildPath.STEALTH: "Cool alert spikes and control pursuit lanes.",
            BuildPath.MOBILITY: "Cross space fast and survive rough deck geometry.",
            BuildPath.SCAVENGER: "Push economy, relay value, and signal gambling.",
        }
        return summaries[self]


class ModuleType(Enum):
    QUIET_HIDE = auto()
    LIGHT_PAWS = auto()
    RELAY_BOOST = auto()
    THERMAL_LINING = auto()
    DEEP_HIDE = auto()
    SIGNAL_FILTER = auto()
    THREAT_SINK = auto()

    @property
    def label(self) -> str:
        labels = {
            ModuleType.QUIET_HIDE: "Quiet Hide",
            ModuleType.LIGHT_PAWS: "Light Paws",
            ModuleType.RELAY_BOOST: "Relay Boost",
            ModuleType.THERMAL_LINING: "Thermal Lining",
            ModuleType.DEEP_HIDE: "Deep Hide",
            ModuleType.SIGNAL_FILTER: "Signal Filter",
            ModuleType.THREAT_SINK: "Threat Sink",
        }
        return labels[self]

    @property
    def path(self) -> BuildPath:
        mapping = {
            ModuleType.QUIET_HIDE: BuildPath.STEALTH,
            ModuleType.DEEP_HIDE: BuildPath.STEALTH,
            ModuleType.THREAT_SINK: BuildPath.STEALTH,
            ModuleType.LIGHT_PAWS: BuildPath.MOBILITY,
            ModuleType.THERMAL_LINING: BuildPath.MOBILITY,
            ModuleType.RELAY_BOOST: BuildPath.SCAVENGER,
            ModuleType.SIGNAL_FILTER: BuildPath.SCAVENGER,
        }
        return mapping[self]


class ShipAlertStage(Enum):
    CALM = auto()
    HUNT = auto()
    SWEEP = auto()

    @property
    def label(self) -> str:
        return self.name


class SignalOutcome(Enum):
    BATTERY_CACHE = auto()
    SCRAP_CACHE = auto()
    MODULE = auto()
    AMBUSH = auto()
    STATIC_BURST = auto()


class CellColor(Enum):
    VOID = "void"
    WALL = "wall"
    FLOOR = "floor"
    FOG = "fog"
    PLAYER = "player"
    PLAYER_HIDDEN = "player_hidden"
    DOCK = "dock"
    RELAY = "relay"
    RELAY_RESTORED = "relay_restored"
    BATTERY = "battery"
    SCRAP = "scrap"
    SIGNAL = "signal"
    HEAT = "heat"
    ENEMY_RED = "enemy_red"
    ENEMY_RED_COOL = "enemy_red_cool"
    ENEMY_HOT = "enemy_hot"
    HEARD = "heard"
    BORDER = "border"
    TITLE = "title"
    BAR_POWER = "bar_power"
    BAR_NOISE = "bar_noise"
    BAR_ALERT = "bar_alert"
    RELAY_PULSE = "relay_pulse"
    NOISE = "noise"
    NOISE_FLASH = "noise_flash"
    TRAIL = "trail"
    BACKDROP = "backdrop"
    PANEL_FILL = "panel_fill"


class EffectKind(Enum):
    MOVE_TRAIL = "move_trail"
    RELAY = "relay"
    ALERT_BAR = "alert_bar"
    HISS = "hiss"
    HIDE = "hide"
    KNOCK = "knock"
    KNOCK_FLASH = "knock_flash"
    MIMIC = "mimic"
    ENEMY_SPOT = "enemy_spot"


class BarColor(Enum):
    POWER = CellColor.BAR_POWER.value
    NOISE = CellColor.BAR_NOISE.value
    ALERT = CellColor.BAR_ALERT.value


@dataclass(frozen=True, order=True)
class Point:
    x: int
    y: int

    def __add__(self, other: Point) -> Point:
        return Point(self.x + other.x, self.y + other.y)

    def distance(self, other: Point) -> int:
        return abs(self.x - other.x) + abs(self.y - other.y)


INPUT_TO_DIRECTION: dict[str, str] = {
    "w": "UP",
    "s": "DOWN",
    "a": "LEFT",
    "d": "RIGHT",
    "KEY_UP": "UP",
    "KEY_DOWN": "DOWN",
    "KEY_LEFT": "LEFT",
    "KEY_RIGHT": "RIGHT",
}


@dataclass
class Item:
    kind: ItemType
    position: Point
    amount: int = 0
    revealed: bool = False

    @property
    def glyph(self) -> str:
        if self.kind == ItemType.MIMIC and not self.revealed:
            return "▣"
        glyphs = {
            ItemType.BATTERY: "▣",
            ItemType.SCRAP: "✦",
            ItemType.SIGNAL: "◎",
            ItemType.MIMIC: "◆",
        }
        return glyphs[self.kind]


@dataclass
class Entity:
    enemy_type: EnemyType
    position: Point
    alert: AlertState = AlertState.DORMANT
    home: Point | None = None
    last_known_player: Point | None = None
    patrol_target: Point | None = None
    scared_turns: int = 0
    wake_delay: int = 0

    @property
    def glyph(self) -> str:
        return self.enemy_type.value


@dataclass
class FloorObjective:
    required_relays: int
    restored_relays: int = 0

    @property
    def complete(self) -> bool:
        return self.restored_relays >= self.required_relays


@dataclass
class PlayerState:
    position: Point
    power: int = MAX_POWER
    power_capacity: int = MAX_POWER
    scrap: int = 0
    modules: set[ModuleType] = field(default_factory=set)
    hiss_cooldown: int = 0
    pounce_cooldown: int = 0
    hidden_turns: int = 0


@dataclass
class FloorState:
    width: int
    height: int
    tiles: list[list[TileType]]
    dock: Point
    objective: FloorObjective
    items: list[Item]
    enemies: list[Entity]
    condition: FloorCondition = FloorCondition.STANDARD
    explored: set[Point] = field(default_factory=set)
    visible: set[Point] = field(default_factory=set)

    def in_bounds(self, point: Point) -> bool:
        return 0 <= point.x < self.width and 0 <= point.y < self.height

    def tile_at(self, point: Point) -> TileType:
        return self.tiles[point.y][point.x]

    def set_tile(self, point: Point, tile: TileType) -> None:
        self.tiles[point.y][point.x] = tile

    def is_walkable(self, point: Point) -> bool:
        return self.in_bounds(point) and self.tile_at(point) != TileType.WALL

    def item_at(self, point: Point) -> Item | None:
        return next((item for item in self.items if item.position == point), None)

    def enemy_at(self, point: Point) -> Entity | None:
        return next((enemy for enemy in self.enemies if enemy.position == point), None)

    def iter_points(self) -> Iterable[Point]:
        for y in range(self.height):
            for x in range(self.width):
                yield Point(x, y)


@dataclass
class RunStats:
    floors_cleared: int = 0
    relays_restored: int = 0
    rare_modules: int = 0
    safe_extractions: int = 0
    max_noise: int = 0
    max_alert: int = 0
    quiet_turns: int = 0
    loud_turns: int = 0
    batteries_found: int = 0
    signals_touched: int = 0
    knocks_used: int = 0
    hides_used: int = 0
    pounces_used: int = 0
    modules_installed: int = 0


@dataclass
class DockOffer:
    label: str
    cost: int
    module: ModuleType | None = None
    power_capacity_bonus: int = 0
    path: BuildPath | None = None
    tagline: str = ""

    @property
    def detail(self) -> str:
        if self.module is not None:
            return self.module.label
        if self.power_capacity_bonus:
            return f"Power cap +{self.power_capacity_bonus}"
        return self.label

    @property
    def summary(self) -> str:
        if self.tagline:
            return self.tagline
        if self.path is not None:
            return self.path.summary
        return self.detail


@dataclass
class ScoreEntry:
    timestamp: str
    score: int
    floor_reached: int
    scrap: int
    relays_restored: int
    rare_modules: int
    extracted: bool
    title: str
    seed: int = 0
    daily_run: bool = False
    build_path: str = ""
    highlight: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp,
            "score": self.score,
            "floor_reached": self.floor_reached,
            "scrap": self.scrap,
            "relays_restored": self.relays_restored,
            "rare_modules": self.rare_modules,
            "extracted": self.extracted,
            "title": self.title,
            "seed": self.seed,
            "daily_run": self.daily_run,
            "build_path": self.build_path,
            "highlight": self.highlight,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> ScoreEntry:
        return cls(
            timestamp=_read_str(raw, "timestamp"),
            score=_read_int(raw, "score"),
            floor_reached=_read_int(raw, "floor_reached"),
            scrap=_read_int(raw, "scrap"),
            relays_restored=_read_int(raw, "relays_restored"),
            rare_modules=_read_int(raw, "rare_modules"),
            extracted=_read_bool(raw, "extracted"),
            title=_read_str(raw, "title"),
            seed=_read_optional_int(raw, "seed", 0),
            daily_run=_read_optional_bool(raw, "daily_run", False),
            build_path=_read_optional_str(raw, "build_path", ""),
            highlight=_read_optional_str(raw, "highlight", ""),
        )


def _read_str(raw: dict[str, object], key: str) -> str:
    value = raw[key]
    if not isinstance(value, str):
        raise ValueError(f"Expected {key} to be a string")
    return value


def _read_int(raw: dict[str, object], key: str) -> int:
    value = raw[key]
    if isinstance(value, bool):
        raise ValueError(f"Expected {key} to be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise ValueError(f"Expected {key} to be an integer")


def _read_bool(raw: dict[str, object], key: str) -> bool:
    value = raw[key]
    if not isinstance(value, bool):
        raise ValueError(f"Expected {key} to be a boolean")
    return value


def _read_optional_int(raw: dict[str, object], key: str, default: int) -> int:
    if key not in raw:
        return default
    return _read_int(raw, key)


def _read_optional_bool(raw: dict[str, object], key: str, default: bool) -> bool:
    if key not in raw:
        return default
    return _read_bool(raw, key)


def _read_optional_str(raw: dict[str, object], key: str, default: str) -> str:
    if key not in raw:
        return default
    return _read_str(raw, key)


@dataclass
class HudState:
    title: str
    floor: int
    condition: str
    seed_label: str
    build_path: str
    power: int
    scrap: int
    noise: int
    alert: int
    alert_stage: ShipAlertStage
    relays: str
    score: int


@dataclass
class RenderCell:
    char: str
    color: CellColor
    dim: bool = False
    bold: bool = False
    reverse: bool = False
    flash: bool = False


@dataclass
class RenderEffect:
    kind: EffectKind
    points: list[Point]
    color: CellColor
    frames: int
    glyph: str


@dataclass
class MapMarker:
    point: Point
    label: str
    color: CellColor
    pulse: bool = False


@dataclass
class EnemyIntent:
    enemy_type: EnemyType
    alert: AlertState
    origin: Point
    destination: Point
    attack: bool = False


@dataclass
class SidebarSection:
    title: str
    lines: list[str]


@dataclass
class SidebarState:
    objective: SidebarSection
    tools: SidebarSection
    guidance: SidebarSection
    modules: SidebarSection


@dataclass
class StatusBar:
    label: str
    value: int
    maximum: int
    color: BarColor


@dataclass
class OverlayState:
    title: str = ""
    lines: list[str] = field(default_factory=list)
    backdrop: bool = False

    @property
    def visible(self) -> bool:
        return bool(self.title or self.lines)


@dataclass
class RenderState:
    hud: HudState
    map_rows: list[list[RenderCell]]
    log_lines: list[str]
    footer: str
    sidebar: SidebarState
    status_bars: list[StatusBar] = field(default_factory=list)
    noise_history: list[int] = field(default_factory=list)
    effects: list[RenderEffect] = field(default_factory=list)
    markers: list[MapMarker] = field(default_factory=list)
    enemy_intents: list[EnemyIntent] = field(default_factory=list)
    threat_cells: list[Point] = field(default_factory=list)
    overlay: OverlayState = field(default_factory=OverlayState)
