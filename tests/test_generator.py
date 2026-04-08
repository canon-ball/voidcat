from __future__ import annotations

import random
import unittest
from collections import deque
from itertools import permutations

from voidcat.generator import generate_floor, relay_quota
from voidcat.models import (
    MAX_POWER,
    RELAY_RECHARGE,
    FloorCondition,
    ItemType,
    Point,
    TileType,
)


class GeneratorTests(unittest.TestCase):
    def test_floor_is_connected_and_specials_are_reachable(self) -> None:
        floor = generate_floor(4, random.Random(11))
        reachable = self._reachable(floor)
        walkable = {point for point in floor.iter_points() if floor.tile_at(point) != TileType.WALL}
        self.assertEqual(walkable, reachable)

        self.assertEqual(floor.tile_at(floor.dock), TileType.DOCK)
        relay_count = sum(
            1 for point in floor.iter_points() if floor.tile_at(point) == TileType.RELAY
        )
        self.assertEqual(relay_count, relay_quota(4))

        for item in floor.items:
            self.assertIn(item.position, reachable)

    def test_relay_quota_scales_by_floor(self) -> None:
        self.assertEqual(relay_quota(1), 2)
        self.assertEqual(relay_quota(3), 3)
        self.assertEqual(relay_quota(5), 4)

    def test_objective_route_and_early_battery_are_reasonable(self) -> None:
        for floor_number in [1, 3, 5]:
            for seed in range(25):
                floor = generate_floor(floor_number, random.Random(seed))
                distances = self._distances(floor)
                batteries = [
                    distances[item.position]
                    for item in floor.items
                    if item.kind == ItemType.BATTERY
                ]
                self.assertTrue(batteries)
                self.assertLessEqual(min(batteries), 8)
                if floor_number <= 3:
                    route_cost = self._objective_route_cost(floor)
                    relay_count = sum(
                        1 for point in floor.iter_points() if floor.tile_at(point) == TileType.RELAY
                    )
                    effective_budget = MAX_POWER + 8 + relay_count * (RELAY_RECHARGE - 1)
                    self.assertLessEqual(route_cost + relay_count, effective_budget)

    def test_battery_pickups_follow_rebalanced_ranges(self) -> None:
        for floor_number in [1, 3, 5]:
            floor = generate_floor(floor_number, random.Random(17 + floor_number))
            amounts = [item.amount for item in floor.items if item.kind == ItemType.BATTERY]
            self.assertTrue(amounts)
            self.assertTrue(all(10 <= amount <= 16 for amount in amounts))
            self.assertTrue(any(amount <= 14 for amount in amounts))

    def test_floor_conditions_shift_generation_profile(self) -> None:
        training = generate_floor(1, random.Random(7), FloorCondition.TRAINING)
        hot_deck = generate_floor(3, random.Random(7), FloorCondition.HOT_DECK)
        signal_surge = generate_floor(3, random.Random(7), FloorCondition.SIGNAL_SURGE)

        self.assertEqual(training.condition, FloorCondition.TRAINING)
        self.assertEqual(len(training.enemies), 1)
        self.assertFalse(
            any(training.tile_at(point) == TileType.HEAT for point in training.iter_points())
        )
        self.assertGreaterEqual(
            sum(1 for item in signal_surge.items if item.kind == ItemType.SIGNAL),
            sum(1 for item in hot_deck.items if item.kind == ItemType.SIGNAL),
        )
        self.assertGreater(
            sum(1 for point in hot_deck.iter_points() if hot_deck.tile_at(point) == TileType.HEAT),
            sum(
                1
                for point in signal_surge.iter_points()
                if signal_surge.tile_at(point) == TileType.HEAT
            ),
        )

    def _reachable(self, floor) -> set[Point]:
        seen = {floor.dock}
        queue: deque[Point] = deque([floor.dock])
        while queue:
            current = queue.popleft()
            for neighbor in [
                Point(current.x + 1, current.y),
                Point(current.x - 1, current.y),
                Point(current.x, current.y + 1),
                Point(current.x, current.y - 1),
            ]:
                if not floor.in_bounds(neighbor):
                    continue
                if floor.tile_at(neighbor) == TileType.WALL:
                    continue
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                queue.append(neighbor)
        return seen

    def _distances(self, floor) -> dict[Point, int]:
        seen = {floor.dock: 0}
        queue: deque[Point] = deque([floor.dock])
        while queue:
            current = queue.popleft()
            for neighbor in [
                Point(current.x + 1, current.y),
                Point(current.x - 1, current.y),
                Point(current.x, current.y + 1),
                Point(current.x, current.y - 1),
            ]:
                if not floor.in_bounds(neighbor):
                    continue
                if floor.tile_at(neighbor) == TileType.WALL:
                    continue
                if neighbor in seen:
                    continue
                seen[neighbor] = seen[current] + 1
                queue.append(neighbor)
        return seen

    def _objective_route_cost(self, floor) -> int:
        relays = [point for point in floor.iter_points() if floor.tile_at(point) == TileType.RELAY]
        points = [floor.dock, *relays]
        maps = {point: self._distances_from(floor, point) for point in points}
        best = 10**9
        for order in permutations(relays):
            cost = 0
            current = floor.dock
            for relay in order:
                cost += maps[current][relay]
                current = relay
            cost += maps[current][floor.dock]
            best = min(best, cost)
        return best

    def _distances_from(self, floor, start: Point) -> dict[Point, int]:
        seen = {start: 0}
        queue: deque[Point] = deque([start])
        while queue:
            current = queue.popleft()
            for neighbor in [
                Point(current.x + 1, current.y),
                Point(current.x - 1, current.y),
                Point(current.x, current.y + 1),
                Point(current.x, current.y - 1),
            ]:
                if not floor.in_bounds(neighbor):
                    continue
                if floor.tile_at(neighbor) == TileType.WALL:
                    continue
                if neighbor in seen:
                    continue
                seen[neighbor] = seen[current] + 1
                queue.append(neighbor)
        return seen
