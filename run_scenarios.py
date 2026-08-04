"""
run_scenarios.py - 1980s single-family house vs 40 cm retrofit, Paris 2090,
each with and without the 0.8 m south overhang (4 buildings x 2 weather years).

Scenario "1980s":    150 m2, hollow-brick walls + 2 cm exterior insulation
                     (heavy layer facing inside), 1980s infiltration (0.5 ACH),
                     1980s double glazing (~15% window/floor ratio), brick
                     internal walls (medium mass), mech. ventilation 0.5 ACH,
                     ideal heating 21 C / cooling 24 C, windows open at maximum
                     for free cooling only when Tout < 24 C (closed above).
Scenario "retrofit": identical, but 40 cm exterior insulation and low-energy
                     airtightness. Nothing else changes.
"_no_overhang" variants: same buildings with the south overhang removed.

Metrics per case: yearly heating, mechanical cooling, ventilation (fan) energy,
total = heating + cooling + fan, overheating hours above 26 C and 28 C
(air and operative temperature).
"""
import os, csv, copy
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from backend.building_sim import Weather, Building, SurfaceDef, WindowDef, simulate

HERE = os.path.dirname(os.path.abspath(__file__))
WDIR, RDIR = os.path.join(HERE, "weather"), os.path.join(HERE, "results")

def house_1980s():
    w, l, h = 15.0, 10.0, 2.7
    az = dict(N=0.0, E=90.0, S=180.0, W=270.0)
    gross = dict(S=w*h, N=w*h, E=l*h, W=l*h)
    win = dict(S=9.0, N=3.0, E=5.0, W=5.0)
    surfaces, windows = [], []
    for o in "SNEW":
        surfaces.append(SurfaceDef(f"wall_{o}", gross[o] - win[o], az[o], 90.0,
                                   U=0.85, heat_cap=200e3, absorptivity=0.6,
                                   ext_frac=0.55))
    surfaces.append(SurfaceDef("roof", w*l, 0.0, 0.0, U=0.80, heat_cap=250e3,
                               absorptivity=0.8, ext_frac=0.55))
    surfaces.append(SurfaceDef("floor", w*l, 0.0, 180.0, U=0.90, heat_cap=300e3,
                               ext_frac=0.6))
    for o in "SNEW":
        windows.append(WindowDef(win[o], az[o], U=2.8, shgc=0.72, height=1.4,
                                 overhang_depth=0.8 if o == "S" else 0.0))
    people_wk = [220,220,220,220,220,220,280,280,70,70,70,70,70,70,70,70,
                 210,280,280,280,280,280,280,220]
    equip_wk  = [150,150,150,150,150,150,300,400,200,180,180,180,180,180,180,180,
                 300,500,600,600,550,450,300,200]
    people_we = [220,220,220,220,220,220,220,280,280,280,280,280,280,280,280,280,
                 280,280,280,280,280,280,280,220]
    equip_we  = [150,150,150,150,150,150,200,350,450,400,350,350,350,350,300,300,
                 350,500,600,600,550,450,300,200]
    return Building(
        floor_area=w*l, height=h, surfaces=surfaces, windows=windows,
        c_int=18e6, a_int=280.0, h_int=3.0,
        ach_infiltration=0.50, ach_wind_coeff=0.02,
        mech_vent_ach=0.50, fan_sfp=500.0,
        vent_open_area=4.0, vent_opening_height=1.4, vent_max_ach=12.0,
        heat_setpoint=21.0, cool_setpoint=24.0,
        heat_capacity_w=25000.0, cool_capacity_w=5000.0,   # modest 5 kW split system
        cooling_enabled=True,
        gains_wk=list(zip(people_wk, equip_wk)),
        gains_we=list(zip(people_we, equip_we)))

def house_retrofit():
    b = copy.deepcopy(house_1980s())
    for s in b.surfaces:
        base_r = 1.0 / s.U - 0.5
        s.U = 1.0 / (base_r + 10.0)
        s.ext_frac = 0.92
    b.ach_infiltration = 0.06
    b.ach_wind_coeff = 0.003
    return b

def no_overhang(bld):
    b = copy.deepcopy(bld)
    for w in b.windows:
        w.overhang_depth = 0.0
    return b

def larger_windows(bld, factor=2.0, orientations=(180.0, 90.0, 270.0)):
    """Scale S/E/W window areas by `factor`; carve the extra area out of the
    matching wall so total facade area is conserved."""
    b = copy.deepcopy(bld)
    for w in b.windows:
        if w.azimuth in orientations:
            extra = w.area * (factor - 1.0)
            w.area *= factor
            for s in b.surfaces:
                if s.name.startswith("wall") and s.azimuth == w.azimuth:
                    s.area -= extra
    return b

def write_csv(res, path):
    keys = ["month", "day", "hour", "t_out", "t_air", "t_op", "q_heat", "q_cool",
            "q_fan", "q_sol_win", "q_int", "ach_vent", "ach_inf", "ach_mech", "win_open"]
    with open(path, "w", newline="") as f:
        wcsv = csv.writer(f)
        wcsv.writerow(keys)
        for i in range(8760):
            wcsv.writerow([round(float(res[k][i]), 3) for k in keys])

def main():
    os.makedirs(RDIR, exist_ok=True)
    weathers = {"typical": Weather(os.path.join(WDIR, "FRA_Paris_2090_typical.epw")),
                "heatwave": Weather(os.path.join(WDIR, "FRA_Paris_2090_heatwave.epw"))}
    b80 = house_1980s()
    bre = house_retrofit()
    buildings = {
        "1980s": b80,
        "retrofit insulation": bre,
        "1980s + big windows + no overhang": larger_windows(no_overhang(b80)),
        "retrofit insulation + big windows + no overhang": larger_windows(no_overhang(bre)),
    }

    rows, cases = [], {}
    for bl, bld in buildings.items():
        for wl, wx in weathers.items():
            cache = os.path.join("/tmp", "scen_cache_" + bl.replace(" ", "_") + f"_{wl}.pkl")
            if os.path.exists(cache):
                import pickle
                with open(cache, "rb") as fh: res = pickle.load(fh)
                print(f"cached  {bl} / {wl}")
            else:
                print(f"running {bl} / {wl} ...")
                res = simulate(bld, wx)
                import pickle
                with open(cache, "wb") as fh: pickle.dump(res, fh)
            cases[(bl, wl)] = res
            safe = bl.replace(" + ", "+").replace(" ", "_")
            write_csv(res, os.path.join(RDIR, f"scenario_{safe}_{wl}.csv"))
            heat = res["q_heat"].sum() / 1000.0
            cool = res["q_cool"].sum() / 1000.0
            fan = res["q_fan"].sum() / 1000.0
            rows.append(dict(
                building=bl, weather=wl,
                heating_kWh=heat, cooling_kWh=cool, fan_kWh=fan,
                total_kWh=heat + cool + fan,
                oh_air24=int((res["t_air"] > 24.05).sum()),
                oh_air26=int((res["t_air"] > 26.0).sum()),
                oh_air28=int((res["t_air"] > 28.0).sum()),
                oh_op24=int((res["t_op"] > 24.05).sum()),
                oh_op26=int((res["t_op"] > 26.0).sum()),
                oh_op28=int((res["t_op"] > 28.0).sum()),
                peak_cool_kw=res["q_cool"].max() / 1000.0,
                cool_run_h=int((res["q_cool"] > 1).sum())))

    fa = b80.floor_area
    lines = ["# Scenario results - Paris 2090 (SSP2-4.5), 150 m2 single-family house",
             "",
             "Setpoints 21 C / 24 C, ideal heating, cooling capped at 5 kW, mech. ventilation 0.5 ACH,",
             "windows open at maximum for free cooling only when Tout < 24 C (closed above).",
             "Overheating counted on air temperature (Tair) and operative temperature (Top).",
             "",
             "| Building (single family house) | Weather Paris 2090 | Heating [kWh] | Cooling [kWh] | Heating + Cooling [kWh] | h Tair>24 | h Tair>26 | h Tair>28 | h Top>24 | h Top>26 | h Top>28 |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['building']} | {r['weather']} | {r['heating_kWh']:.0f} | "
                     f"{r['cooling_kWh']:.0f} | **{r['heating_kWh'] + r['cooling_kWh']:.0f}** | "
                     f"{r['oh_air24']} | {r['oh_air26']} | {r['oh_air28']} | "
                     f"{r['oh_op24']} | {r['oh_op26']} | {r['oh_op28']} |")
    lines += ["",
              "Notes:",
              "- Heating/cooling are ideal-load (thermal) demands at setpoints 21 C / 24 C.",
              "- Mechanical ventilation fan (0.5 ACH, SFP 0.5 kW/(m3/s)) uses 246 kWh/year in all cases,",
              "  excluded from the Heating + Cooling column.",
              "- Cooling capacity limited to 5 kW (modest residential split system):",
              "  hours above the 24 C setpoint mean the system cannot keep up.",
              "  Operative temperature (Top) also counts warm interior surfaces.",
              "- Peak cooling load: " + ", ".join(
                  f"{r['building']}/{r['weather']}: {r['peak_cool_kw']:.1f} kW" for r in rows),
              "- Cooling operating hours: " + ", ".join(
                  f"{r['building']}/{r['weather']}: {r['cool_run_h']} h" for r in rows)]
    with open(os.path.join(RDIR, "scenarios_summary.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))

    # ---- plot: energy comparison ----
    fig, ax = plt.subplots(figsize=(12.5, 6))
    x = np.arange(len(rows))
    ax.bar(x, [r["heating_kWh"] for r in rows], 0.6, label="Heating", color="#c0392b")
    ax.bar(x, [r["cooling_kWh"] for r in rows], 0.6,
           bottom=[r["heating_kWh"] for r in rows], label="Mech. cooling", color="#2980b9")
    ax.bar(x, [r["fan_kWh"] for r in rows], 0.6,
           bottom=[r["heating_kWh"] + r["cooling_kWh"] for r in rows],
           label="Ventilation fan", color="#7f8c8d")
    for i, r in enumerate(rows):
        ax.text(i, r["total_kWh"] + 200, f"{r['total_kWh']:.0f}", ha="center", fontsize=9)
    labels = [r['building'].replace(' + ', chr(10)+'+ ') + f"\n({r['weather']})"
              for r in rows]
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("kWh / year")
    ax.set_title("Annual energy demand - overhang vs no overhang, Paris 2090")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(RDIR, "scenario_energy.png"), dpi=130)
    plt.close(fig)

    # ---- plot: cooling demand only ----
    fig, ax = plt.subplots(figsize=(9, 5))
    blds = list(buildings.keys())
    width = 0.35
    xb = np.arange(len(blds))
    for k, (wl, color) in enumerate([("typical", "#5dade2"), ("heatwave", "#c0392b")]):
        vals = [next(r["cooling_kWh"] for r in rows
                     if r["building"] == b and r["weather"] == wl) for b in blds]
        ax.bar(xb + (k - 0.5) * width, vals, width, label=f"2050 {wl}", color=color)
        for i, v in enumerate(vals):
            ax.text(xb[i] + (k - 0.5) * width, v + 40, f"{v:.0f}", ha="center", fontsize=8)
    ax.set_xticks(xb)
    ax.set_xticklabels([b.replace(" + ", "\n+ ") for b in blds], fontsize=8)
    ax.set_ylabel("Mechanical cooling (kWh/year)")
    ax.set_title("Cooling demand - effect of the south overhang")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(RDIR, "scenario_cooling.png"), dpi=130)
    plt.close(fig)

    # ---- plot: heat-wave week operative temps, all 4 buildings ----
    r0 = cases[("1980s", "heatwave")]
    pk = int(np.argmax(r0["t_out"]))
    a, b_ = max(0, pk - 96), min(8760, pk + 120)
    t = np.arange(a, b_)
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.plot(t, r0["t_out"][a:b_], color="gray", lw=1, label="Outdoor")
    styles = {"1980s": ("crimson", "-"),
              "retrofit insulation": ("royalblue", "-"),
              "1980s + big windows + no overhang": ("crimson", "--"),
              "retrofit insulation + big windows + no overhang": ("royalblue", "--")}
    for bl, (c, ls) in styles.items():
        ax.plot(t, cases[(bl, "heatwave")]["t_op"][a:b_], color=c, ls=ls, lw=1.4,
                label=bl)
    ax.axhline(26, color="k", ls=":", lw=0.8); ax.axhline(28, color="k", ls=":", lw=0.8)
    ax.set_ylabel("Operative temperature (C)"); ax.set_xlabel("Hour of year")
    ax.set_title("Extreme 2090 heat wave - operative temperature (cooling capped at 5 kW)")
    ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(RDIR, "scenario_heatwave.png"), dpi=130)
    plt.close(fig)
    print(f"\nresults in {RDIR}")

if __name__ == "__main__":
    main()
