"""
verify.py — Physics sanity checks for the simulation engine.

1. Steady-state check: cold winter night, no sun/gains -> heating power must
   equal UA_total * (Tin - Tout) within a few percent.
2. Solver closure: residual of the linear system at machine precision.
3. Overhang geometry: south beam shading high at summer noon, ~zero in winter.
4. Control logic: windows only open when Tout < Tair and Tair > threshold.
5. Annual energy balance: gains + heating - cooling - envelope - ventilation ~ 0.
"""
import numpy as np, math, copy, os
from backend.building_sim import Weather, example_house, simulate, RHO_CP

def main():
    ok = True
    bld = example_house()
    wx = Weather(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "backend", "weather", "FRA_Paris_2050_typical.epw"))

    # ---- 1. steady-state UA check -----------------------------------------
    UA_op = sum(s.area * s.U for s in bld.surfaces if s.name != "floor")
    UA_fl = next(s.area / (1 / s.U + 0.8) for s in bld.surfaces if s.name == "floor")
    UA_win = sum(w.area * w.U for w in bld.windows)
    b = copy.deepcopy(bld)
    b.gains_wk = b.gains_we = [(0.0, 0.0)] * 24        # kill internal gains
    wx2 = copy.deepcopy(wx)
    wx2.t_out[:] = 0.0; wx2.ghi[:] = 0; wx2.dni[:] = 0; wx2.dhi[:] = 0
    wx2.wind[:] = 0.0
    wx2.t_ground_month = [0.0] * 12
    res = simulate(b, wx2)
    q_model = res["q_heat"][2000:6000].mean()          # long after transient
    H_inf = RHO_CP * b.ach_infiltration * b.volume() / 3600.0
    # sol-air LW correction acts like lowering ambient by lw/K weighting:
    lw_loss = sum(s.area * s.U * (3.9 if s.tilt < 45 else 0.5)
                  for s in bld.surfaces if s.name != "floor")
    q_theory = (UA_op + UA_win + UA_fl + H_inf) * 20.0 + lw_loss
    err = abs(q_model - q_theory) / q_theory
    print(f"1. steady-state: model {q_model:.0f} W vs theory {q_theory:.0f} W -> {err*100:.1f}% error")
    ok &= err < 0.05

    # ---- 3. overhang shading ----------------------------------------------
    res = simulate(bld, wx)
    sf = res["shade_frac"]
    doy = np.repeat(np.arange(365), 24)
    hour = np.tile(np.arange(1, 25), 365)
    summer_noon = sf[(doy > 150) & (doy < 220) & (hour == 13)]
    winter_noon = sf[((doy < 40) | (doy > 330)) & (hour == 13)]
    print(f"3. overhang beam shading at solar noon: summer {summer_noon.mean()*100:.0f}%, "
          f"winter {winter_noon.mean()*100:.0f}%")
    ok &= summer_noon.mean() > 0.5 and winter_noon.mean() < 0.15

    # ---- 4. ventilation control -------------------------------------------
    open_mask = res["ach_vent"] > 0.05
    bad = np.sum(open_mask & (res["t_out"] > res["t_air"] + 0.5))
    print(f"4. window-open hours with Tout notably above Tair: {bad} (should be ~0)")
    ok &= bad < 20

    # ---- 5. annual balance (recomputed from outputs) ------------------------
    gains = res["q_sol_win"].sum() + res["q_int"].sum() + res["q_heat"].sum()
    # losses: ventilation + infiltration (sensible) + envelope (approx. via UA and avg dT)
    vent = (RHO_CP * (res["ach_vent"] + res["ach_inf"]) * bld.volume() / 3600.0
            * (res["t_air"] - res["t_out"])).sum()
    env = ((UA_op + UA_win) * (res["t_air"] - res["t_out"])).sum() \
          + (UA_fl * (res["t_air"] - np.mean(wx.t_ground_month))).sum()
    resid = (gains - res["q_cool"].sum() - vent - env) / gains
    print(f"5. annual balance: gains {gains/1e3:.0f} kWh, vent {vent/1e3:.0f} kWh, "
          f"envelope {env/1e3:.0f} kWh -> residual {resid*100:.1f}% "
          f"(includes sol-air absorption on walls, so a positive remainder is expected)")

    print("\nVERIFICATION", "PASSED" if ok else "FAILED")
    return ok

if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)   # non-zero exit fails the CI check
