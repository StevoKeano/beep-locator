"""
GDOP (Geometric Dilution of Precision) calculation for Beep Locator.
"""

import numpy as np


def calculate_gdop(positions: list, source_pos: tuple, sound_speed_mps: float = 343.0) -> float:
    """
    Calculate GDOP for a given source position and node positions.
    
    Args:
        positions: List of (x, y) node positions
        source_pos: (x, y) source position
        sound_speed_mps: Speed of sound in meters per second
        
    Returns:
        GDOP value (float)
    """
    if len(positions) < 2:
        return float('inf')
        
    source_x, source_y = source_pos
    H = []
    
    # Compute Jacobian matrix H
    for i, (px, py) in enumerate(positions):
        # Vector from node to source
        dx = source_x - px
        dy = source_y - py
        
        # Distance from node to source
        dist = np.sqrt(dx**2 + dy**2)
        
        if dist < 1e-6:
            # Avoid division by zero
            return float('inf')
            
        # Gradient of range difference (normalized vector from node to source)
        h_i = np.array([dx, dy]) / dist
        
        H.append(h_i)
    
    # Convert to numpy array
    H = np.array(H)
    
    # Compute H^T * H
    try:
        # Use SVD to compute pseudo-inverse for robustness
        U, s, Vt = np.linalg.svd(H.T @ H)
        
        # Avoid singular matrix by using a small regularization
        # (This is a simplified approach; full GDOP would be sqrt(trace((H^T H)^-1)))
        if len(s) > 0:
            # Regularize to avoid numerical issues
            s_reg = np.maximum(s, 1e-8)
            inv_HTH = Vt.T @ np.diag(1.0 / s_reg) @ Vt
            
            # GDOP is sqrt(trace((H^T H)^-1))
            gdop = np.sqrt(np.trace(inv_HTH))
        else:
            gdop = float('inf')
            
    except Exception:
        # Fallback in case of numerical issues
        gdop = float('inf')
        
    return float(gdop)


def suggest_next_position(positions: list, room_width_m: float, room_height_m: float,
                         min_node_distance_m: float = 1.0) -> tuple:
    """
    Suggest the next best listener position by grid-searching for lowest GDOP.
    
    Args:
        positions: List of (x, y) node positions (normalized 0..1)
        room_width_m: Width of the room in meters
        room_height_m: Height of the room in meters
        min_node_distance_m: Minimum distance from existing nodes
        
    Returns:
        Suggested (x, y) position as normalized coordinates (0..1)
    """
    if len(positions) < 2:
        return (0.5, 0.5)
        
    # Convert to room coordinates for distance calculations
    node_positions_room = [(pos[0] * room_width_m, pos[1] * room_height_m) for pos in positions]
    
    # Grid resolution (smaller for better resolution)
    grid_resolution = 0.1  # meters
    
    min_gdop = float('inf')
    best_pos = (0.5, 0.5)
    
    # Grid search
    x_range = np.arange(0, room_width_m, grid_resolution)
    y_range = np.arange(0, room_height_m, grid_resolution)
    
    for x in x_range:
        for y in y_range:
            # Skip if too close to any existing node
            valid = True
            for nx, ny in node_positions_room:
                dist = np.sqrt((x - nx)**2 + (y - ny)**2)
                if dist < min_node_distance_m:
                    valid = False
                    break
                    
            if not valid:
                continue
                
            # Calculate GDOP
            gdop = calculate_gdop(positions, (x / room_width_m, y / room_height_m))
            
            if gdop < min_gdop:
                min_gdop = gdop
                best_pos = (x / room_width_m, y / room_height_m)
    
    return best_pos