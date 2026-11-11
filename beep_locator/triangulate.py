"""
Triangulation utilities for Beep Locator.
"""

import numpy as np
from scipy.optimize import least_squares


def _invalid_result() -> dict:
    """Return the standard failed triangulation result."""
    return {
        "x": 0.0,
        "y": 0.0,
        "error_m": float("inf"),
        "confidence": 0.0,
        "valid": False,
        "used_nodes": [],
    }


def triangulate(
    positions: list,
    intervals: list,
    chirp_distances: list,
    sound_speed_mps: float = 343.0,
    room_width_m: float = 8.0,
    room_height_m: float = 6.0,
) -> dict:
    """
    Solve for a source position using multilateration with TDOA.

    Node positions are normalized map coordinates in the range 0..1. They are
    converted to metres using ``room_width_m`` and ``room_height_m`` before
    solving. ``chirp_distances`` are physical distances in metres to the chirp
    anchor. The returned ``x``/``y`` are normalized map coordinates.

    Args:
        positions: List of normalized (x, y) node positions.
        intervals: Per-node ``beep_onset - chirp_onset`` in seconds.
        chirp_distances: Per-node distance to the chirp anchor in metres.
        sound_speed_mps: Speed of sound in metres per second.
        room_width_m: Physical room width in metres.
        room_height_m: Physical room height in metres.

    Returns:
        Dictionary with 'x', 'y', 'error_m', 'confidence', 'valid',
        'used_nodes'. ``used_nodes`` contains the non-reference node indices.
    """
    node_count = len(positions)
    if (
        node_count < 3
        or len(intervals) != node_count
        or len(chirp_distances) != node_count
        or sound_speed_mps <= 0.0
        or room_width_m <= 0.0
        or room_height_m <= 0.0
    ):
        return _invalid_result()

    try:
        positions_norm = np.asarray(positions, dtype=float)
        intervals = np.asarray(intervals, dtype=float)
        chirp_distances = np.asarray(chirp_distances, dtype=float)
    except (TypeError, ValueError):
        return _invalid_result()

    if (
        positions_norm.shape != (node_count, 2)
        or intervals.shape != (node_count,)
        or chirp_distances.shape != (node_count,)
        or not np.all(np.isfinite(positions_norm))
        or not np.all(np.isfinite(intervals))
        or not np.all(np.isfinite(chirp_distances))
    ):
        return _invalid_result()

    room_size = np.array([room_width_m, room_height_m], dtype=float)
    positions_m = positions_norm * room_size

    # Reject degenerate node geometry: the nodes must span a 2-D area.
    offsets = positions_m - positions_m[0]
    rank_tolerance = 1e-6 * max(room_width_m, room_height_m)
    if np.linalg.matrix_rank(offsets, tol=rank_tolerance) < 2:
        return _invalid_result()

    # The anchor (smallest chirp distance) is the best TDOA reference.
    reference_index = int(np.argmin(np.abs(chirp_distances)))
    other_indices = np.flatnonzero(np.arange(node_count) != reference_index)
    reference_pos = positions_m[reference_index]
    other_pos = positions_m[other_indices]

    # Signed TDOA distance difference in metres:
    # tau_i = c * (interval_i - interval_ref) + (chirp_i - chirp_ref)
    tau = (
        sound_speed_mps
        * (intervals[other_indices] - intervals[reference_index])
        + (chirp_distances[other_indices] - chirp_distances[reference_index])
    )

    def residuals(point):
        ranges = np.linalg.norm(other_pos - point, axis=1)
        reference_range = np.linalg.norm(reference_pos - point)
        return ranges - reference_range - tau

    # Coarse grid initialization avoids converging to the mirror solution.
    grid_size = 21
    best_guess = np.array([room_width_m / 2.0, room_height_m / 2.0])
    best_cost = float("inf")
    for x in np.linspace(0.0, room_width_m, grid_size):
        for y in np.linspace(0.0, room_height_m, grid_size):
            candidate = np.array([x, y])
            cost = float(np.sum(residuals(candidate) ** 2))
            if cost < best_cost:
                best_cost = cost
                best_guess = candidate

    try:
        result = least_squares(
            residuals,
            best_guess,
            bounds=([0.0, 0.0], [room_width_m, room_height_m]),
            method="trf",
            xtol=1e-12,
            ftol=1e-12,
            gtol=1e-12,
            max_nfev=2000,
        )
    except Exception:
        return _invalid_result()

    if not result.success or not np.all(np.isfinite(result.x)):
        return _invalid_result()

    final_residuals = residuals(result.x)
    error_m = float(np.sqrt(np.mean(final_residuals**2)))

    # Approximate GDOP from the range-difference Jacobian. Poor geometry
    # (near-collinear nodes or a source on top of a node) lowers confidence.
    reference_vector = result.x - reference_pos
    reference_norm = float(np.linalg.norm(reference_vector))
    if reference_norm < 1e-9:
        geometry_confidence = 0.0
    else:
        rows = []
        for node_pos in other_pos:
            node_vector = result.x - node_pos
            node_norm = float(np.linalg.norm(node_vector))
            if node_norm < 1e-9:
                rows = []
                break
            rows.append(node_vector / node_norm - reference_vector / reference_norm)

        if len(rows) < 2:
            geometry_confidence = 0.0
        else:
            singular_values = np.linalg.svd(np.asarray(rows), compute_uv=False)
            if singular_values.size < 2 or singular_values[-1] < 1e-9:
                geometry_confidence = 0.0
            else:
                gdop = float(np.sqrt(np.sum(1.0 / singular_values**2)))
                geometry_confidence = 1.0 / (1.0 + max(0.0, gdop - 1.0))

    error_confidence = 1.0 / (1.0 + error_m / 0.5)
    confidence = float(
        np.clip(error_confidence * geometry_confidence, 0.0, 1.0)
    )

    estimated_norm = result.x / room_size
    return {
        "x": float(np.clip(estimated_norm[0], 0.0, 1.0)),
        "y": float(np.clip(estimated_norm[1], 0.0, 1.0)),
        "error_m": error_m,
        "confidence": confidence,
        "valid": True,
        "used_nodes": [int(index) for index in other_indices],
    }


def triangulate_simple(
    positions: list,
    intervals: list,
    chirp_distances: list,
    sound_speed_mps: float = 343.0,
    room_width_m: float = 8.0,
    room_height_m: float = 6.0,
) -> dict:
    """Backward-compatible wrapper around :func:`triangulate`."""
    return triangulate(
        positions,
        intervals,
        chirp_distances,
        sound_speed_mps=sound_speed_mps,
        room_width_m=room_width_m,
        room_height_m=room_height_m,
    )