"""
Triangulation tests for Beep Locator.
"""

import unittest

import numpy as np

from beep_locator.triangulate import triangulate

ROOM_WIDTH_M = 8.0
ROOM_HEIGHT_M = 6.0
SPEED_OF_SOUND_MPS = 343.0


def synthetic_measurements(
    node_positions, source_position, anchor_index=0, common_gap_s=0.04
):
    """Generate exact intervals and chirp distances for a known source."""
    room_size = np.array([ROOM_WIDTH_M, ROOM_HEIGHT_M])
    nodes_m = np.asarray(node_positions, dtype=float) * room_size
    source_m = np.asarray(source_position, dtype=float) * room_size
    anchor_m = nodes_m[anchor_index]

    chirp_distances = np.linalg.norm(nodes_m - anchor_m, axis=1)
    beep_distances = np.linalg.norm(nodes_m - source_m, axis=1)
    intervals = common_gap_s + (beep_distances - chirp_distances) / SPEED_OF_SOUND_MPS
    return intervals, chirp_distances


class TestTriangulation(unittest.TestCase):

    def test_known_source_position(self):
        """Exact synthetic data recovers the known source position."""
        positions = [
            [0.10, 0.10],
            [0.90, 0.10],
            [0.50, 0.90],
        ]
        true_source = [0.35, 0.55]
        intervals, chirp_distances = synthetic_measurements(
            positions, true_source
        )

        result = triangulate(
            positions,
            intervals,
            chirp_distances,
            sound_speed_mps=SPEED_OF_SOUND_MPS,
            room_width_m=ROOM_WIDTH_M,
            room_height_m=ROOM_HEIGHT_M,
        )

        self.assertTrue(result["valid"])
        self.assertAlmostEqual(result["x"], true_source[0], places=6)
        self.assertAlmostEqual(result["y"], true_source[1], places=6)
        self.assertLess(result["error_m"], 1e-6)
        self.assertGreater(result["confidence"], 0.5)
        self.assertEqual(result["used_nodes"], [1, 2])

    def test_insufficient_nodes(self):
        """Test triangulation with less than 3 nodes."""
        positions = [[0.2, 0.3], [0.8, 0.4]]
        intervals = [0.01, 0.02]
        chirp_distances = [0.0, 0.5]

        result = triangulate(positions, intervals, chirp_distances)

        self.assertFalse(result["valid"])
        self.assertEqual(result["error_m"], float("inf"))
        self.assertEqual(result["used_nodes"], [])

    def test_collinear_nodes(self):
        """Collinear nodes are reported as a degenerate result."""
        positions = [
            [0.2, 0.3],
            [0.5, 0.6],
            [0.8, 0.9],
        ]
        intervals = [0.01, 0.02, 0.03]
        chirp_distances = [0.0, 0.5, 1.0]

        result = triangulate(positions, intervals, chirp_distances)

        self.assertFalse(result["valid"])
        self.assertEqual(result["error_m"], float("inf"))
        self.assertEqual(result["used_nodes"], [])


if __name__ == '__main__':
    unittest.main()