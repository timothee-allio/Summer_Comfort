from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import numpy as np
import json
import math

from building_sim import Weather, simulate, build_case, weather_path, WEATHER_CASES
from app_grid import GRID, AXES, SHADING, make_key

HERE = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Summer Comfort Simulation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SimRequest(BaseModel):
    wall_r: float = 4.0
    global_window_area: float = 15.0
    overhang_depth: float = 0.8
    vent_max_ach: float = 12.0
    external_shading_enabled: bool = False
    weather_case: str = "Paris_2090_heatwave"

class HeatmapRequest(BaseModel):
    wall_r: float
    global_window_area: float
    overhang_depth: float
    vent_max_ach: float
    external_shading_enabled: bool
    weather_case: str
    x_axis: str
    y_axis: str

# ---------------------------------------------------------
# DATABASE LOADING & GLOBAL BOUNDS
# ---------------------------------------------------------
# The database (see generate_database.py) is turned into one dense array per
# weather case and metric, indexed [wallR, window, overhang, ventilation, shading]
# on the grid of app_grid.py, so that it can be interpolated.
HEATMAP_RES = 30          # heatmap cells per axis

# Heatmap metrics: name used by the app -> key in the database.
# "overheating" = hours above 28 C operative temperature over the year in the
# same building WITHOUT air conditioning (free-running), i.e. summer comfort.
HEATMAP_METRICS = {
    "cooling": "cool",
    "heating": "heat",
    "overheating": "ff_hours_above_28",
}

def load_database(path):
    with open(path, "r") as f:
        raw = json.load(f)
    shape = tuple(len(GRID[a]) for a in AXES) + (len(SHADING),)
    tables = {}
    for case, data in raw.items():
        sample = next(iter(data.values()))
        metrics = [m for m in HEATMAP_METRICS.values() if m in sample]
        arrays = {m: np.full(shape, np.nan) for m in metrics}
        for idx in np.ndindex(shape):
            vals = [GRID[a][i] for a, i in zip(AXES, idx[:4])] + [SHADING[idx[4]]]
            entry = data.get(make_key(*vals))
            if entry is None:
                raise KeyError(f"{case}: grid point {make_key(*vals)} missing; "
                               "the database does not match app_grid.py, regenerate it")
            for m in arrays:
                arrays[m][idx] = entry[m]
        tables[case] = arrays
    return tables

try:
    SIM_DB = load_database(os.path.join(HERE, "simulation_database.json"))
    bounds = {
        name: [min(float(t[key].min()) for t in SIM_DB.values()),
               max(float(t[key].max()) for t in SIM_DB.values())]
        for name, key in HEATMAP_METRICS.items()
        if all(key in t for t in SIM_DB.values())
    }
except (FileNotFoundError, KeyError) as e:
    SIM_DB = {}
    bounds = {"cooling": [0.0, 100.0], "heating": [0.0, 100.0], "overheating": [0.0, 100.0]}
    print(f"WARNING: simulation database unavailable ({e}). Run generate_database.py first.")

def interpolate(table, points):
    """Multilinear interpolation of table[..., shade] at points (n, 4), in the
    order of AXES. Points outside the grid are clamped to its edges."""
    points = np.atleast_2d(points)
    n = points.shape[0]
    lo_idx, w_hi = [], []
    for k, a in enumerate(AXES):
        g = GRID[a]
        x = np.clip(points[:, k], g[0], g[-1])
        i = np.clip(np.searchsorted(g, x, side="right") - 1, 0, len(g) - 2)
        lo_idx.append(i)
        w_hi.append((x - g[i]) / (g[i + 1] - g[i]))
    result = np.zeros(n)
    for corner in np.ndindex(*(2,) * len(AXES)):        # 16 corners
        w = np.ones(n)
        idx = []
        for k, c in enumerate(corner):
            w = w * (w_hi[k] if c else 1.0 - w_hi[k])
            idx.append(lo_idx[k] + c)
        result += w * table[tuple(idx)]
    return result

_WEATHER_CACHE = {}

def get_weather(case):
    """Parse each EPW file once and keep it (and its sun positions) in memory."""
    if case not in _WEATHER_CACHE:
        _WEATHER_CACHE[case] = Weather(weather_path(case))
    return _WEATHER_CACHE[case]

@app.get("/health")
def health_check():
    return {"status": "ok"}

# ---------------------------------------------------------
# SINGLE SIMULATION (For the top Stats Cards)
# ---------------------------------------------------------
@app.post("/api/simulate")
def run_sim(req: SimRequest):
    # Dynamically injects "2050_typical", "2090_heatwave", etc.
    if req.weather_case not in WEATHER_CASES:
        raise HTTPException(status_code=400,
                            detail=f"Unknown weather case, expected one of {list(WEATHER_CASES)}")
    if not os.path.exists(weather_path(req.weather_case)):
        raise HTTPException(status_code=404, detail="Weather file not found")

    wx = get_weather(req.weather_case)
    try:
        bld = build_case(req.wall_r, req.global_window_area, req.overhang_depth,
                         req.vent_max_ach, req.external_shading_enabled)
    except ValueError as e:            # e.g. windows larger than the facade
        raise HTTPException(status_code=400, detail=str(e))

    res = simulate(bld, wx)

    # Same building without air conditioning: summer comfort indicators.
    bld.cooling_enabled = False
    t_op_ff = simulate(bld, wx)["t_op"]

    return {
        "t_out": res["t_out"].tolist(),
        "t_air": res["t_air"].tolist(),
        "t_op": res["t_op"].tolist(),
        "q_cool": res["q_cool"].tolist(),
        "ach_vent": res["ach_vent"].tolist(),
        "summary": {
            "total_cooling_kwh": float(res["q_cool"].sum() / 1000.0),
            "total_heating_kwh": float(res.get("q_heat", np.zeros(1)).sum() / 1000.0),
            "hours_above_26": int((res["t_op"] > 26.0).sum()),
            "hours_above_28": int((res["t_op"] > 28.0).sum()),
            "peak_t_op": float(res["t_op"].max()),
            "ff_hours_above_26": int((t_op_ff > 26.0).sum()),
            "ff_hours_above_28": int((t_op_ff > 28.0).sum()),
            "ff_peak_t_op": float(t_op_ff.max()),
        }
    }

# ---------------------------------------------------------
# FAST HEATMAP GENERATOR (multilinear interpolation of the database)
# ---------------------------------------------------------
@app.post("/api/heatmap")
def generate_heatmap(req: HeatmapRequest):
    empty = {name: [] for name in HEATMAP_METRICS}
    if not SIM_DB or req.weather_case not in SIM_DB:
        return {**empty, "bounds": bounds}
    if req.x_axis not in GRID or req.y_axis not in GRID:
        raise HTTPException(status_code=400, detail="Unknown heatmap axis")

    current = {
        "wallR": req.wall_r,
        "globalWindowArea": req.global_window_area,
        "overhang": req.overhang_depth,
        "ventilation": req.vent_max_ach,
    }
    # Evenly spaced cells over each axis' full range (the app draws them evenly)
    x_values = np.linspace(GRID[req.x_axis][0], GRID[req.x_axis][-1], HEATMAP_RES)
    y_values = np.linspace(GRID[req.y_axis][0], GRID[req.y_axis][-1], HEATMAP_RES)
    xx, yy = np.meshgrid(x_values, y_values, indexing="ij")   # [x][y]

    points = np.empty((xx.size, len(AXES)))
    for k, a in enumerate(AXES):
        points[:, k] = current[a]
    points[:, AXES.index(req.x_axis)] = xx.ravel()
    points[:, AXES.index(req.y_axis)] = yy.ravel()

    shade = int(bool(req.external_shading_enabled))
    tables = SIM_DB[req.weather_case]
    result = dict(empty)
    for name, key in HEATMAP_METRICS.items():
        if key in tables:
            result[name] = interpolate(tables[key][..., shade], points).reshape(xx.shape).tolist()
    result["bounds"] = bounds
    return result
