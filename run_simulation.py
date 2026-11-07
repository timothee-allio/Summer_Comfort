"""
run_simulation.py — Run the Paris 2050 building simulations and produce results.

Cases: {2050 typical, 2050 heat-wave year} x {with cooling, free-floating}.
Outputs in ./results/: hourly CSVs, summary.md, comparison plots.
"""
import os, csv, copy
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from backend.building_sim import Weather, example_house, simulate, summarize

HERE = os.path.dirname(os.path.abspath(__file__))
WDIR, RDIR = os.path.join(HERE, "backend", "weather"), os.path.join(HERE, "results")

def ensure_weather():
    files = ["FRA_Paris_2050_typical.epw", "FRA_Paris_2050_heatwave.epw"]
    if not all(os.path.exists(os.path.join(WDIR, f)) for f in files):
        import backend.weather_gen as weather_gen
        weather_gen.main()
    return [os.path.join(WDIR, f) for f in files]

def write_csv(res, path):
    keys = ["month", "day", "hour", "t_out", "t_air", "t_op", "q_heat", "q_cool",
            "q_sol_win", "q_int", "ach_vent", "ach_inf", "win_open", "shade_frac"]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(keys)
        for i in range(8760):
            w.writerow([round(float(res[k][i]), 3) for k in keys])

def monthly(arr, months, agg="sum"):
    return [arr[months == m].sum() / 1000.0 if agg == "sum" else arr[months == m].mean()
            for m in range(1, 13)]

def main():
    os.makedirs(RDIR, exist_ok=True)
    epw_typ, epw_hw = ensure_weather()
    bld = example_house()

    cases = {}
    for wlabel, epw in [("typical", epw_typ), ("heatwave", epw_hw)]:
        wx = Weather(epw)
        for clabel, cooling in [("cooled", True), ("freefloat", False)]:
            b = copy.deepcopy(bld); b.cooling_enabled = cooling
            print(f"running {wlabel}/{clabel} ...")
            res = simulate(b, wx)
            cases[(wlabel, clabel)] = (res, wx)
            write_csv(res, os.path.join(RDIR, f"hourly_{wlabel}_{clabel}.csv"))

    # ---------------- summary ----------------
    lines = ["# Paris 2050 (SSP2-4.5) — Summer-comfort simulation results",
             "", "Building: 100 m2 single-storey dwelling, U-wall 0.25 / roof 0.18 / windows 1.3,",
             "10 m2 south glazing with 0.8 m overhang, night-ventilation control, "
             "infiltration 0.15 ACH + wind term.", ""]
    lines.append("| Case | Heating kWh/m2 | Cooling kWh/m2 | h >26C | h >28C | h >30C | Peak Top C | Peak Tout C | Vent hours |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for (wl, cl), (res, _) in cases.items():
        s = summarize(res, f"{wl}/{cl}", bld.floor_area)
        lines.append(f"| {s['label']} | {s['heating_kWh_m2']} | {s['cooling_kWh_m2']} | "
                     f"{s['hours_above_26']} | {s['hours_above_28']} | {s['hours_above_30']} | "
                     f"{s['peak_t_op']} | {s['peak_t_out']} | {s['vent_hours']} |")
    # energy bookkeeping
    lines += ["", "## Energy bookkeeping", ""]
    for (wl, cl), (res, _) in cases.items():
        bi, bo = res["_balance"]
        lines.append(f"- {wl}/{cl}: total gains (solar+internal+heating) {bi/3.6e6:.0f} kWh; "
                     f"mechanical cooling removed {bo/3.6e6:.0f} kWh; "
                     f"the rest leaves via envelope conduction and (natural) ventilation.")
    with open(os.path.join(RDIR, "summary.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))

    # ---------------- plots ----------------
    # 1. Heat-wave week time series (extreme year, free-float vs cooled)
    res_ff, wx_hw = cases[("heatwave", "freefloat")]
    res_cl, _ = cases[("heatwave", "cooled")]
    pk = int(np.argmax(res_ff["t_out"]))
    a, b_ = max(0, pk - 96), min(8760, pk + 120)
    t = np.arange(a, b_)
    fig, ax = plt.subplots(2, 1, figsize=(11, 7), sharex=True,
                           gridspec_kw={"height_ratios": [3, 1]})
    ax[0].plot(t, res_ff["t_out"][a:b_], color="gray", lw=1, label="Outdoor")
    ax[0].plot(t, res_ff["t_op"][a:b_], color="crimson", lw=1.5, label="Indoor operative — free-floating")
    ax[0].plot(t, res_cl["t_op"][a:b_], color="royalblue", lw=1.5, label="Indoor operative — cooled (26 C)")
    ax[0].axhline(28, color="k", ls=":", lw=0.8); ax[0].axhline(26, color="k", ls=":", lw=0.8)
    ax[0].set_ylabel("Temperature (C)"); ax[0].legend(); ax[0].set_title(
        "2050 extreme heat-wave episode — Paris (SSP2-4.5)")
    ax[1].fill_between(t, res_ff["ach_vent"][a:b_], color="seagreen", alpha=0.6, step="mid")
    ax[1].set_ylabel("Nat. vent ACH"); ax[1].set_xlabel("Hour of year")
    fig.tight_layout(); fig.savefig(os.path.join(RDIR, "heatwave_week.png"), dpi=130); plt.close(fig)

    # 2. Monthly heating/cooling — typical vs heat-wave year (cooled cases)
    fig, ax = plt.subplots(figsize=(10, 5))
    m = np.arange(1, 13); wdt = 0.2
    for k, (wl, color_h, color_c) in enumerate([("typical", "#b03a2e", "#2874a6"),
                                                ("heatwave", "#e6b0aa", "#aed6f1")]):
        res, wx = cases[(wl, "cooled")]
        hh = monthly(res["q_heat"], wx.month); cc = monthly(res["q_cool"], wx.month)
        ax.bar(m + (k - 0.5) * 2 * wdt - wdt/1, hh, wdt, color=color_h,
               label=f"Heating {wl}")
        ax.bar(m + (k - 0.5) * 2 * wdt + wdt/1, cc, wdt, color=color_c,
               label=f"Cooling {wl}")
    ax.set_xticks(m); ax.set_xlabel("Month"); ax.set_ylabel("kWh")
    ax.set_title("Monthly heating & cooling — 2050 typical vs extreme heat-wave year")
    ax.legend(); fig.tight_layout()
    fig.savefig(os.path.join(RDIR, "monthly_energy.png"), dpi=130); plt.close(fig)

    # 3. Operative-temperature duration curves (free-float, summer months)
    fig, ax = plt.subplots(figsize=(9, 5))
    for wl, color in [("typical", "royalblue"), ("heatwave", "crimson")]:
        res, wx = cases[(wl, "freefloat")]
        sel = np.isin(wx.month, [5, 6, 7, 8, 9])
        srt = np.sort(res["t_op"][sel])[::-1]
        ax.plot(np.arange(srt.size), srt, color=color, label=f"{wl} year")
    ax.axhline(28, color="k", ls=":", lw=0.8, label="28 C threshold")
    ax.set_xlabel("Hours (May-Sep, sorted)"); ax.set_ylabel("Operative temperature (C)")
    ax.set_title("Free-floating summer temperature duration curve"); ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(RDIR, "duration_curve.png"), dpi=130); plt.close(fig)


    print(f"\nresults in {RDIR}")

if __name__ == "__main__":
    main()
