"""
generate_database.py - Offline parameter sweep for the web app's heatmap.

Runs every combination of the five app parameters (grid defined in
app_grid.py: 9 x 9 x 9 x 9 x 2) for the four weather cases, i.e. 52 488 annual
simulations, and writes simulation_database.json, read by main.py.

* Parallel: uses all CPU cores by default (--workers N to change).
* Resumable: each finished simulation is appended to
  simulation_database.partial.jsonl; if the run stops, launching it again
  skips what is already done. The partial file is removed at the end.

Each entry stores the annual cooling and heating demand (kWh) used by the app,
plus comfort metrics from the same run (operative temperature).
"""
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np
from building_sim import Weather, simulate, build_case, weather_path, WEATHER_CASES
from app_grid import GRID, SHADING, make_key

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "simulation_database.json")
PARTIAL = os.path.join(HERE, "simulation_database.partial.jsonl")

R_VALS = GRID["wallR"]
WIN_VALS = GRID["globalWindowArea"]
OVER_VALS = GRID["overhang"]
VENT_VALS = GRID["ventilation"]
SHADING_VALS = SHADING


def all_jobs():
    for scenario in WEATHER_CASES:
        for r in R_VALS:
            for win in WIN_VALS:
                for over in OVER_VALS:
                    for vent in VENT_VALS:
                        for shade in SHADING_VALS:
                            yield scenario, float(r), float(win), float(over), float(vent), shade


_WEATHER = {}


def run_one(job):
    scenario, r, win, over, vent, shade = job
    if scenario not in _WEATHER:                       # one parse per worker
        _WEATHER[scenario] = Weather(weather_path(scenario))
    res = simulate(build_case(r, win, over, vent, shade), _WEATHER[scenario])
    t_op = res["t_op"]
    return scenario, make_key(r, win, over, vent, shade), {
        "cool": float(res["q_cool"].sum() / 1000.0),
        "heat": float(res["q_heat"].sum() / 1000.0),
        "hours_above_26": int((t_op > 26.0).sum()),
        "hours_above_28": int((t_op > 28.0).sum()),
        "peak_t_op": float(t_op.max()),
    }


def load_partial():
    done = {}
    if os.path.exists(PARTIAL):
        with open(PARTIAL) as f:
            for line in f:
                try:
                    scenario, key, val = json.loads(line)
                except ValueError:
                    continue                            # truncated last line
                done[(scenario, key)] = val
    return done


def run_parameter_sweep(workers=None):
    for scenario in WEATHER_CASES:
        if not os.path.exists(weather_path(scenario)):
            raise FileNotFoundError(f"{weather_path(scenario)} not found: run weather_gen.py first")

    jobs = list(all_jobs())
    done = load_partial()
    todo = [j for j in jobs if (j[0], make_key(*j[1:])) not in done]
    workers = workers or os.cpu_count() or 1
    print(f"{len(jobs)} simulations, {len(done)} already done, {len(todo)} to run "
          f"on {workers} worker(s).", flush=True)

    t0 = time.time()
    with open(PARTIAL, "a") as part, Pool(workers) as pool:
        for i, (scenario, key, val) in enumerate(pool.imap_unordered(run_one, todo, chunksize=4), 1):
            done[(scenario, key)] = val
            part.write(json.dumps([scenario, key, val]) + "\n")
            part.flush()
            if i % 100 == 0 or i == len(todo):
                el = time.time() - t0
                eta = el / i * (len(todo) - i)
                print(f"{len(done)} / {len(jobs)} done, {el/60:.1f} min elapsed, "
                      f"~{eta/60:.0f} min left", flush=True)

    database = {s: {} for s in WEATHER_CASES}
    for scenario, r, win, over, vent, shade in jobs:         # stable key order
        key = make_key(r, win, over, vent, shade)
        database[scenario][key] = done[(scenario, key)]

    with open(OUT, "w") as f:
        json.dump(database, f)
    try:
        os.remove(PARTIAL)
    except OSError as e:
        print(f"Could not remove {PARTIAL} ({e}); you can delete it.", flush=True)
    print(f"Complete! {len(jobs)} results saved to {OUT}", flush=True)


if __name__ == "__main__":
    n = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else None
    run_parameter_sweep(n)
