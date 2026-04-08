from __future__ import annotations

from typing import TYPE_CHECKING

from .ai import line_of_sight, orthogonal_neighbors, preview_enemy_turn
from .models import (
    MAX_LOG_LINES,
    MAX_NOISE,
    MAX_SHIP_ALERT,
    NOISE_HISTORY_LENGTH,
    AlertState,
    BarColor,
    CellColor,
    EnemyIntent,
    EnemyType,
    GameMode,
    HudState,
    ItemType,
    MapMarker,
    OverlayState,
    Point,
    RenderCell,
    RenderState,
    ShipAlertStage,
    SidebarSection,
    SidebarState,
    StatusBar,
    TileType,
)

if TYPE_CHECKING:
    from .engine import GameEngine


class PresentationBuilder:
    def __init__(self, engine: GameEngine) -> None:
        self.engine = engine

    def get_render_state(self, overlay: OverlayState | None = None) -> RenderState:
        if self.engine.floor is None:
            raise RuntimeError("Game floor is not initialized")
        floor_condition = self.engine.floor.condition
        hud = HudState(
            title="VOIDCAT",
            floor=self.engine.floor_number,
            condition=floor_condition.label,
            seed_label=self.engine.seed_label,
            build_path=self.engine.build_path_label,
            power=self.engine.player.power,
            scrap=self.engine.player.scrap,
            noise=self.engine.current_noise,
            alert=self.engine.ship_alert,
            alert_stage=self.engine.ship_alert_stage,
            relays=(
                f"{self.engine.floor.objective.restored_relays}/"
                f"{self.engine.floor.objective.required_relays}"
            ),
            score=self.engine.score,
        )
        map_rows: list[list[RenderCell]] = []
        for y in range(self.engine.floor.height):
            row: list[RenderCell] = []
            for x in range(self.engine.floor.width):
                row.append(self.cell_for_point(Point(x, y)))
            map_rows.append(row)
        return RenderState(
            hud=hud,
            map_rows=map_rows,
            log_lines=list(self.engine.logs)[-MAX_LOG_LINES:],
            footer=self.footer_text(),
            sidebar=self.sidebar_state(),
            status_bars=self.status_bars(),
            noise_history=self.padded_noise_history(),
            effects=list(self.engine.last_turn_effects),
            markers=self.map_markers(),
            enemy_intents=self.enemy_intents(),
            threat_cells=self.threat_cells(),
            overlay=overlay or OverlayState(),
        )

    def summary_lines(self) -> list[str]:
        if self.engine.mode == GameMode.DOCK_SHOP:
            return self.dock_shop_lines()
        if self.engine.mode == GameMode.GAME_OVER:
            return list(self.engine.game_over_lines)
        return []

    def cell_for_point(self, point: Point) -> RenderCell:
        if self.engine.floor is None:
            return RenderCell(" ", CellColor.VOID)
        if point not in self.engine.floor.explored and point not in self.engine.floor.visible:
            return RenderCell(" ", CellColor.VOID)
        visible = point in self.engine.floor.visible

        if visible and point == self.engine.player.position:
            color = (
                CellColor.PLAYER_HIDDEN if self.engine.player.hidden_turns > 0 else CellColor.PLAYER
            )
            return RenderCell("▲", color, bold=True)

        if visible:
            enemy = self.engine.floor.enemy_at(point)
            if enemy:
                color = CellColor.ENEMY_RED
                bold = enemy.enemy_type in {EnemyType.STALKER, EnemyType.MIMIC}
                dim = enemy.enemy_type == EnemyType.CRAWLER and enemy.alert != AlertState.CHASING
                flash = enemy.alert == AlertState.CHASING
                if enemy.alert == AlertState.SCARED:
                    color = CellColor.ENEMY_RED_COOL
                    dim = False
                return RenderCell(enemy.glyph, color, dim=dim, bold=bold, flash=flash)

            item = self.engine.floor.item_at(point)
            if item:
                color_map: dict[ItemType, CellColor] = {
                    ItemType.BATTERY: CellColor.BATTERY,
                    ItemType.SCRAP: CellColor.SCRAP,
                    ItemType.SIGNAL: CellColor.SIGNAL,
                    ItemType.MIMIC: CellColor.BATTERY,
                }
                return RenderCell(item.glyph, color_map[item.kind])

            if self.engine.heard_position == point and self.engine.current_noise > 0:
                return RenderCell("◌", CellColor.HEARD, bold=True)

        tile = self.engine.floor.tile_at(point)
        if not visible:
            return RenderCell(tile.value, CellColor.FOG, dim=True)

        if tile == TileType.RELAY and point in self.engine.restored_relays:
            return RenderCell("◆", CellColor.RELAY_RESTORED, bold=True)

        tile_colors: dict[TileType, CellColor] = {
            TileType.WALL: CellColor.WALL,
            TileType.FLOOR: CellColor.FLOOR,
            TileType.DOCK: CellColor.DOCK,
            TileType.RELAY: CellColor.RELAY,
            TileType.HEAT: CellColor.HEAT,
        }
        bold = tile in {TileType.DOCK, TileType.RELAY, TileType.HEAT}
        return RenderCell(tile.value, tile_colors[tile], bold=bold)

    def footer_text(self) -> str:
        if self.engine.mode == GameMode.DOCK_SHOP:
            return "1-3 buy | D descend | E end run | Q quit"
        if self.engine.mode == GameMode.GAME_OVER:
            return "N new run | H high scores | Q quit"
        return (
            "WASD move | Space wait | E interact | H hiss | X hide | "
            "K knock | P pounce | V threat | ? help | Q quit"
        )

    def sidebar_state(self) -> SidebarState:
        if self.engine.floor is None:
            empty = SidebarSection("", [])
            return SidebarState(empty, empty, empty, empty)
        modules = [
            module.label
            for module in sorted(self.engine.player.modules, key=lambda module: module.label)
        ]
        if not modules:
            modules = ["None installed"]
        elif len(modules) > 2:
            modules = modules[:2] + [f"+{len(modules) - 2} more"]
        modules = [self.engine.build_path_label, *modules]
        return SidebarState(
            objective=SidebarSection(
                "Objective",
                [
                    f"Floor {self.engine.floor_number}",
                    "Relays "
                    f"{self.engine.floor.objective.restored_relays}/"
                    f"{self.engine.floor.objective.required_relays}",
                    f"Scrap {self.engine.player.scrap}",
                ],
            ),
            tools=SidebarSection(
                "Tools",
                [
                    "Hide "
                    f"{'ON' if self.engine.player.hidden_turns > 0 else 'READY'} "
                    f"{self.engine.player.hidden_turns}",
                    (
                        "Hiss READY"
                        if self.engine.player.hiss_cooldown == 0
                        else f"Hiss CD {self.engine.player.hiss_cooldown}"
                    ),
                    (
                        "Pounce READY"
                        if self.engine.player.pounce_cooldown == 0
                        else f"Pounce CD {self.engine.player.pounce_cooldown}"
                    ),
                ],
            ),
            guidance=SidebarSection("Guidance", self.guidance_lines()),
            modules=SidebarSection("Modules", modules),
        )

    def guidance_lines(self) -> list[str]:
        if self.engine.decoy_target is not None:
            return [
                f"Decoy live {self.engine.decoy_turns}",
                "Cross now while patrols rotate.",
                f"Alert {self.engine.ship_alert_stage.label}",
            ]
        if self.engine.player.hidden_turns > 0:
            return [
                f"Hidden {self.engine.player.hidden_turns}",
                "Stay dark until sightlines break.",
                f"Alert {self.engine.ship_alert_stage.label}",
            ]
        if self.engine.ship_alert_stage == ShipAlertStage.SWEEP:
            return [
                "Sweep is active.",
                "Break sight, then hide or wait.",
                "Avoid noisy pounces unless forced.",
            ]
        if self.engine.current_noise >= 6:
            return [
                "Noise is hot.",
                "Hide now or throw a knock away.",
                "Wait if you need alert to cool.",
            ]
        if self.engine.player.hiss_cooldown == 0:
            return [
                "Hiss hits adjacent crawlers",
                "and mimics only.",
                "Keep it for emergencies.",
            ]
        if self.engine.player.pounce_cooldown == 0:
            return [
                "Pounce jumps 1-2 tiles.",
                "Use it to grab space or loot.",
                "Do not land on fresh threats.",
            ]
        return [
            "Knock before open crossings.",
            "Hide after breaking sightlines.",
            "Space-wait to read patrol rhythm.",
        ]

    def status_bars(self) -> list[StatusBar]:
        power_max = max(self.engine.player.power_capacity, self.engine.player.power)
        return [
            StatusBar("Power", self.engine.player.power, power_max, BarColor.POWER),
            StatusBar("Noise", self.engine.current_noise, MAX_NOISE, BarColor.NOISE),
            StatusBar("Alert", self.engine.ship_alert, MAX_SHIP_ALERT, BarColor.ALERT),
        ]

    def map_markers(self) -> list[MapMarker]:
        if self.engine.floor is None:
            return []
        markers: list[MapMarker] = []
        if self.engine.floor.objective.complete:
            if self.engine.floor.dock in self.engine.floor.explored:
                markers.append(
                    MapMarker(
                        point=self.engine.floor.dock,
                        label="Dock",
                        color=CellColor.DOCK,
                        pulse=True,
                    )
                )
        else:
            for point in self.engine.floor.iter_points():
                if self.engine.floor.tile_at(point) != TileType.RELAY:
                    continue
                if point not in self.engine.floor.visible or point in self.engine.restored_relays:
                    continue
                markers.append(
                    MapMarker(
                        point=point,
                        label="Relay",
                        color=CellColor.RELAY,
                        pulse=True,
                    )
                )
        for item in self.engine.floor.items:
            if item.position not in self.engine.floor.visible:
                continue
            label_map = {
                ItemType.BATTERY: ("Battery", CellColor.BATTERY),
                ItemType.SCRAP: ("Scrap", CellColor.SCRAP),
                ItemType.SIGNAL: ("Signal", CellColor.SIGNAL),
                ItemType.MIMIC: ("Cache?", CellColor.BATTERY),
            }
            label, color = label_map[item.kind]
            markers.append(MapMarker(point=item.position, label=label, color=color))
        return markers

    def enemy_intents(self) -> list[EnemyIntent]:
        if self.engine.floor is None:
            return []
        occupied = {enemy.position for enemy in self.engine.floor.enemies}
        intents: list[EnemyIntent] = []
        for enemy in self.engine.floor.enemies:
            if enemy.position not in self.engine.floor.visible:
                continue
            enemy_occupied = {point for point in occupied if point != enemy.position}
            turn = preview_enemy_turn(
                enemy,
                self.engine.floor,
                self.engine.player.position,
                player_hidden=self.engine.player.hidden_turns > 0,
                ship_alert_stage=self.engine.ship_alert_stage,
                noise=self.engine.current_noise,
                noise_pos=self.engine.heard_position,
                decoy_target=self.engine.decoy_target,
                occupied=enemy_occupied,
                rng=self.engine.rng,
            )
            intents.append(
                EnemyIntent(
                    enemy_type=enemy.enemy_type,
                    alert=enemy.alert,
                    origin=enemy.position,
                    destination=turn.destination,
                    attack=turn.attacked,
                )
            )
        return intents

    def threat_cells(self) -> list[Point]:
        if self.engine.floor is None:
            return []
        occupied = {enemy.position for enemy in self.engine.floor.enemies}
        threat: set[Point] = set()
        for enemy in self.engine.floor.enemies:
            if enemy.position not in self.engine.floor.visible:
                continue
            enemy_occupied = {point for point in occupied if point != enemy.position}
            turn = preview_enemy_turn(
                enemy,
                self.engine.floor,
                self.engine.player.position,
                player_hidden=self.engine.player.hidden_turns > 0,
                ship_alert_stage=self.engine.ship_alert_stage,
                noise=self.engine.current_noise,
                noise_pos=self.engine.heard_position,
                decoy_target=self.engine.decoy_target,
                occupied=enemy_occupied,
                rng=self.engine.rng,
            )
            threat.add(turn.destination)
            for neighbor in orthogonal_neighbors(turn.destination):
                if self.engine.floor.is_walkable(neighbor):
                    threat.add(neighbor)
            if enemy.enemy_type == EnemyType.STALKER and enemy.alert != AlertState.SCARED:
                sight_range = (
                    9
                    if self.engine.ship_alert_stage in {ShipAlertStage.HUNT, ShipAlertStage.SWEEP}
                    else 7
                )
                for point in self.engine.floor.visible:
                    if point == enemy.position:
                        continue
                    if enemy.position.distance(point) > sight_range:
                        continue
                    if line_of_sight(self.engine.floor, enemy.position, point):
                        threat.add(point)
        return sorted(threat, key=lambda point: (point.y, point.x))

    def padded_noise_history(self) -> list[int]:
        history = list(self.engine.noise_history)
        if len(history) < NOISE_HISTORY_LENGTH:
            return [0] * (NOISE_HISTORY_LENGTH - len(history)) + history
        return history

    def dock_shop_lines(self) -> list[str]:
        lines = [
            "Dock Exchange",
            f"Extraction bonus: {self.engine.extraction_bonus}",
            f"Score: {self.engine.score}",
            f"Scrap: {self.engine.player.scrap}",
            "",
        ]
        for index, offer in enumerate(self.engine.dock_offers, start=1):
            if self.engine.dock_purchase_index == index - 1:
                status = "BOUGHT"
            elif self.engine.dock_purchase_made:
                status = "LOCKED"
            elif self.engine.player.scrap >= offer.cost:
                status = "BUY"
            else:
                status = "NEED SCRAP"
            lines.append(f"{index}. {offer.label} [{offer.cost}] {status}")
            if offer.path is not None:
                lines.append(f"   {offer.path.label}")
            lines.append(f"   {offer.summary}")
            lines.append(f"   {offer.detail}")
        lines.append("")
        if self.engine.dock_purchase_made:
            lines.append("Press D to descend, or E to end the run.")
        else:
            lines.append("Press 1-3 to buy one offer.")
            lines.append("Then press D to descend or E to end the run.")
        lines.append("New floors begin with a fresh power refill.")
        return lines
