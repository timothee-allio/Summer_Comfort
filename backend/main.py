from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import numpy as np
import json
import math

from building_sim import Weather, Building, SurfaceDef, WindowDef, simulate, example_house

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
try:
    with open("simulation_database.json", "r") as f:
        SIM_DB = json.load(f)
        
    bounds = {"cooling": [math.inf, -math.inf], "heating": [math.inf, -math.inf]}
    for case, data in SIM_DB.items():
        for key, results in data.items():
            c, h = results["cool"], results["heat"]
            if c < bounds["cooling"][0]: bounds["cooling"][0] = c
            if c > bounds["cooling"][1]: bounds["cooling"][1] = c
            if h < bounds["heating"][0]: bounds["heating"][0] = h
            if h > bounds["heating"][1]: bounds["heating"][1] = h
            
    if bounds["cooling"][0] == math.inf: bounds["cooling"] = [0.0, 100.0]
    if bounds["heating"][0] == math.inf: bounds["heating"] = [0.0, 100.0]
    
except FileNotFoundError:
    SIM_DB = {}
    bounds = {"cooling": [0.0, 100.0], "heating": [0.0, 100.0]}
    print("WARNING: simulation_database.json not found. Run generate_database.py first.")

def get_nearest(val, grid_array):
    return min(grid_array, key=lambda x: abs(x - val))

@app.get("/health")
def health_check():
    return {"status": "ok"}

# ---------------------------------------------------------
# SINGLE SIMULATION (For the top Stats Cards)
# ---------------------------------------------------------
@app.post("/api/simulate")
def run_sim(req: SimRequest):
    # Dynamically injects "2050_typical", "2090_heatwave", etc.
    epw_file = f"weather/FRA_{req.weather_case}.epw"
    
    if not os.path.exists(epw_file):
        return {"error": "Weather file not found"}

    wx = Weather(epw_file)
    bld = example_house()
    
    bld.vent_max_ach = req.vent_max_ach
    bld.external_shading_enabled = req.external_shading_enabled
    
    wall_u_value = 1.0 / req.wall_r if req.wall_r > 0 else 5.0
    for s in bld.surfaces:
        if s.name.startswith("wall"):
            s.U = wall_u_value

    if len(bld.windows) > 0:
        area_per_window = req.global_window_area / len(bld.windows)
        for i, w in enumerate(bld.windows):
            w.area = area_per_window
            if i == 0:
                w.overhang_depth = req.overhang_depth
            else:
                w.overhang_depth = 0.0

    res = simulate(bld, wx)

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
        }
    }

# ---------------------------------------------------------
# FAST HEATMAP GENERATOR (Database Lookup)
# ---------------------------------------------------------
@app.post("/api/heatmap")
def generate_heatmap(req: HeatmapRequest):
    if not SIM_DB:
        return {"cooling": [], "heating": [], "bounds": bounds}

    grid_r = np.linspace(0.5, 10.0, 5)
    grid_win = np.linspace(2.0, 60.0, 8)
    grid_over = np.linspace(0.0, 2.0, 5)
    grid_vent = np.linspace(0.0, 20.0, 5)

    param_ranges = {
        "wallR": grid_r,
        "globalWindowArea": grid_win,
        "overhang": grid_over,
        "ventilation": grid_vent
    }

    x_values = param_ranges[req.x_axis]
    y_values = param_ranges[req.y_axis]

    cooling_matrix = []
    heating_matrix = []
    db_case = SIM_DB.get(req.weather_case, {})
    shade_int = int(req.external_shading_enabled)

    for x_val in x_values:
        cooling_col = []
        heating_col = []
        for y_val in y_values:
            current_params = {
                "wallR": req.wall_r,
                "globalWindowArea": req.global_window_area,
                "overhang": req.overhang_depth,
                "ventilation": req.vent_max_ach
            }
            current_params[req.x_axis] = x_val
            current_params[req.y_axis] = y_val

            snap_r = get_nearest(current_params["wallR"], grid_r)
            snap_win = get_nearest(current_params["globalWindowArea"], grid_win)
            snap_over = get_nearest(current_params["overhang"], grid_over)
            snap_vent = get_nearest(current_params["ventilation"], grid_vent)

            key = f"{snap_r:.2f}_{snap_win:.1f}_{snap_over:.2f}_{snap_vent:.1f}_{shade_int}"
            result = db_case.get(key, {"cool": 0.0, "heat": 0.0})
            
            cooling_col.append(result["cool"])
            heating_col.append(result["heat"])

        cooling_matrix.append(cooling_col)
        heating_matrix.append(heating_col)

    return {
        "cooling": cooling_matrix,
        "heating": heating_matrix,
        "bounds": bounds 
    }