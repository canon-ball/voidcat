from __future__ import annotations

import random
import unittest
from collections import deque

from hypothesis import given, settings
from hypothesis import strategies as st

from voidcat.ai import line_of_sight, shortest_path
from voidcat.generator import generate_floor
from voidcat.models import Point, TileType


def _reachable_points(floor) -> set[Point]:
    seen = {floor.dock}
    queue: deque[Point] = deque([floor.dock])
    while queue:
        current = queue.popleft()
        for neighbor in (
            Point(current.x + 1, current.y),
            Point(current.x - 1, current.y),
            Point(current.x, current.y + 1),
            Point(current.x, current.y - 1),
        ):
            if not floor.in_bounds(neighbor):
                continue
            if floor.tile_at(neighbor) == TileType.WALL:
                continue
            if neighbor in seen:
                continue
            seen.add(neighbor)
            queue.append(neighbor)
    return seen


class PropertyTests(unittest.TestCase):
    @settings(deadline=None, max_examples=35)
    @given(
        floor_number=st.integers(min_value=1, max_value=6),
        seed=st.integers(min_value=0, max_value=50_000),
    )
    def test_generated_floors_preserve_core_invariants(self, floor_number: int, seed: int) -> None:
        floor = generate_floor(floor_number, random.Random(seed))
        reachable = _reachable_points(floor)
        walkable = {point for point in floor.iter_points() if floor.tile_at(point) != TileType.WALL}

        self.assertEqual(reachable, walkable)
        self.assertEqual(floor.tile_at(floor.dock), TileType.DOCK)
        self.assertTrue(all(item.position in reachable for item in floor.items))
        self.assertTrue(all(enemy.position in reachable for enemy in floor.enemies))
        self.assertEqual(len({item.position for item in floor.items}), len(floor.items))
        self.assertEqual(len({enemy.position for enemy in floor.enemies}), len(floor.enemies))

    @settings(deadline=None, max_examples=30)
    @given(
        floor_number=st.integers(min_value=1, max_value=6),
        seed=st.integers(min_value=0, max_value=50_000),
        sample_seed=st.integers(min_value=0, max_value=50_000),
    )
    def test_line_of_sight_is_symmetric(
        self, floor_number: int, seed: int, sample_seed: int
    ) -> None:
        floor = generate_floor(floor_number, random.Random(seed))
        walkable = [point for point in floor.iter_points() if floor.tile_at(point) != TileType.WALL]
        chooser = random.Random(sample_seed)
        start, end = chooser.sample(walkable, 2)

        self.assertEqual(
            line_of_sight(floor, start, end),
            line_of_sight(floor, end, start),
        )

    @settings(deadline=None, max_examples=30)
    @given(
        floor_number=st.integers(min_value=1, max_value=6),
        seed=st.integers(min_value=0, max_value=50_000),
        sample_seed=st.integers(min_value=0, max_value=50_000),
    )
    def test_shortest_path_stays_walkable_and_orthogonal(
        self,
        floor_number: int,
        seed: int,
        sample_seed: int,
    ) -> None:
        floor = generate_floor(floor_number, random.Random(seed))
        walkable = [point for point in floor.iter_points() if floor.tile_at(point) != TileType.WALL]
        chooser = random.Random(sample_seed)
        start, goal = chooser.sample(walkable, 2)

        path = shortest_path(floor, start, goal, occupied=set())

        self.assertEqual(path[0], start)
        self.assertEqual(path[-1], goal)
        for previous, current in zip(path, path[1:], strict=False):
            self.assertTrue(floor.is_walkable(current))
            self.assertEqual(previous.distance(current), 1)
