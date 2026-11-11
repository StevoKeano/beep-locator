# Beep Locator - TODO

## Mandatory Fixes (M7, M8)

M7: rooms.triangulate_if_needed still uses the hardcoded 0.5,0.5 broadcast;
    replace with real triangulation later. Do not fake it now.
    - File: beep_locator/rooms.py

M8: static/listener.js still uses Math.random simulated detection;
    replace with the real detector later.
    - File: static/listener.js