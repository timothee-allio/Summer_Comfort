import json
import numpy as np
import os
from building_sim import Weather, simulate, example_house

def run_parameter_sweep():
    print("Starting offline parameter sweep. This will take ~2-4 minutes...")
    
    r_vals = np.linspace(0.5, 10.0, 5)
    win_vals = np.linspace(2.0, 60.0, 8)
    over_vals = np.linspace(0.0, 2.0, 5)
    vent_vals = np.linspace(0.0, 20.0, 5)
    shading_vals = [False, True]
    
    # 4 distinct scenarios
    scenarios = ["Paris_2050_typical", "Paris_2050_heatwave", "Paris_2090_typical", "Paris_2090_heatwave"]
    database = {s: {} for s in scenarios}

    total_sims = len(r_vals) * len(win_vals) * len(over_vals) * len(vent_vals) * len(shading_vals) * len(scenarios)
    count = 0

    for scenario in scenarios:
        # Maps perfectly to FRA_Paris_2050_typical.epw, etc.
        epw = f"C:\\Users\\timotheea\\summer_comfort\\backend\\weather\\FRA_{scenario}.epw"
        
        if not os.path.exists(epw):
            print(f"Warning: {epw} not found, skipping {scenario}...")
            count += total_sims // len(scenarios)
            continue
            
        wx = Weather(epw)

        for r in r_vals:
            u_val = 1.0 / r if r > 0 else 5.0
            for win in win_vals:
                for over in over_vals:
                    for vent in vent_vals:
                        for shade in shading_vals:
                            bld = example_house()
                            
                            bld.vent_max_ach = vent
                            bld.external_shading_enabled = shade
                            
                            # Apply U-value to all walls
                            for s in bld.surfaces:
                                if s.name.startswith("wall"):
                                    s.U = u_val
                                    
                            # Distribute window area equally
                            if len(bld.windows) > 0:
                                area_per_window = win / len(bld.windows)
                                for i, w in enumerate(bld.windows):
                                    w.area = area_per_window
                                    w.overhang_depth = over if i == 0 else 0.0

                            res = simulate(bld, wx)
                            
                            cool = float(res["q_cool"].sum() / 1000.0)
                            heat = float(res.get("q_heat", np.zeros(1)).sum() / 1000.0)

                            # Create lookup key mapping all 5 states
                            key = f"{r:.2f}_{win:.1f}_{over:.2f}_{vent:.1f}_{int(shade)}"
                            database[scenario][key] = {"cool": cool, "heat": heat}

                            count += 1
                            if count % 200 == 0:
                                print(f"Processed {count} / {total_sims} scenarios...")

    with open("simulation_database.json", "w") as f:
        json.dump(database, f)
        
    print("Complete! Data saved to simulation_database.json")

if __name__ == "__main__":
    run_parameter_sweep()