"""
app_grid.py - Parameter grid of the precomputed database, shared by
generate_database.py (which fills it) and main.py (which reads and
interpolates it). Change the grid here only, then regenerate the database.

Points are not evenly spaced where the response is not linear:
  * wall R: losses follow 1/R, so values are spaced geometrically;
  * ventilation: the cooling benefit saturates, so points are denser at low ACH.
"""
import numpy as np

# Axis names are the ones used by the API / Flutter app.
GRID = {
    "wallR": np.geomspace(0.5, 10.0, 9),                       # m2K/W
    "globalWindowArea": np.linspace(2.0, 60.0, 9),             # m2
    "overhang": np.linspace(0.0, 2.0, 9),                      # m
    "ventilation": np.array([0, 1, 2, 3, 4, 6, 9, 14, 20.0]),  # ACH
}
AXES = ("wallR", "globalWindowArea", "overhang", "ventilation")
SHADING = (False, True)
METRICS = ("cool", "heat", "hours_above_26", "hours_above_28", "peak_t_op")


def make_key(r, win, over, vent, shade):
    """Database key for one grid point."""
    return f"{r:.3f}_{win:.2f}_{over:.3f}_{vent:.2f}_{int(shade)}"
