"""
weather_gen.py - Generate 2050 Paris EPW weather files (SSP2-4.5).

Two modes:
  1. Default: synthesize a physically consistent hourly year calibrated to
     Paris-Orly 1991-2020 climate normals, then apply 2050 monthly deltas.
  2. --from-epw <path>: morph a real present-day TMY EPW instead
     (Belcher et al. 2005 shift method).

Outputs (in ./weather/):
  FRA_Paris_2050_typical.epw   - 2050 typical year with moderate heat waves
  FRA_Paris_2050_heatwave.epw  - 2050 extreme heat-wave year (2003-type event)
"""
import numpy as np
import os, sys, math

LAT, LON, TZ, ELEV = 48.72, 2.38, 1.0, 89.0
SIGMA = 5.670e-8

# --- Paris-Orly climatology (1991-2020 normals, approx.) -------------------
T_MONTH   = [5.0, 5.6, 8.8, 11.7, 15.2, 18.7, 20.9, 20.8, 17.2, 13.2, 8.6, 5.4]
DR_MONTH  = [5.5, 6.5, 8.0, 9.5, 10.0, 10.5, 10.8, 10.5, 9.5, 7.5, 5.5, 5.0]
GHI_MONTH = [25, 45, 85, 130, 160, 175, 175, 150, 110, 65, 30, 20]
WIND_MEAN = 4.0

# --- 2050 SSP2-4.5 monthly warming deltas vs ~2010 (CMIP6 ensemble, IdF) ---
DT_2050 = [1.4, 1.4, 1.3, 1.4, 1.5, 1.8, 2.1, 2.2, 1.9, 1.6, 1.4, 1.4]
# --- 2090 SSP2-4.5 monthly warming deltas vs ~2010 (CMIP6 ensemble, IdF) ---
DT_2090 = [2.2, 2.2, 2.1, 2.2, 2.4, 2.9, 3.3, 3.4, 3.0, 2.5, 2.3, 2.2]

DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
MONTH_OF_DAY = np.repeat(np.arange(12), DAYS)
DOY_MID = np.cumsum([0] + DAYS[:-1]) + np.array(DAYS) / 2.0

def seasonal_interp(monthly, doy):
    m = np.asarray(monthly, float)
    xs = np.concatenate([DOY_MID - 365, DOY_MID, DOY_MID + 365])
    ys = np.tile(m, 3)
    return np.interp(doy, xs, ys)

def solar_geometry(doy, hour_frac):
    B = 2 * math.pi * (doy - 1 + hour_frac / 24.0) / 365.0
    decl = 0.006918 - 0.399912*np.cos(B) + 0.070257*np.sin(B) - 0.006758*np.cos(2*B) \
           + 0.000907*np.sin(2*B) - 0.002697*np.cos(3*B) + 0.00148*np.sin(3*B)
    eot = 229.18 * (0.000075 + 0.001868*np.cos(B) - 0.032077*np.sin(B)
                    - 0.014615*np.cos(2*B) - 0.04089*np.sin(2*B))
    tsol = hour_frac + (4.0 * (LON - 15.0 * TZ) + eot) / 60.0
    ha = np.radians(15.0 * (tsol - 12.0))
    lat = math.radians(LAT)
    cosz = np.sin(lat)*np.sin(decl) + np.cos(lat)*np.cos(decl)*np.cos(ha)
    I0 = 1367.0 * (1 + 0.033 * np.cos(2 * math.pi * doy / 365.0))
    return np.maximum(cosz, 0.0), I0

def clearsky_ghi(cosz):
    return np.where(cosz > 0.01, 1098.0 * cosz * np.exp(-0.059 / np.maximum(cosz, 0.01)), 0.0)

def erbs_split(ghi, cosz, I0):
    ext = I0 * cosz
    kt = np.clip(np.where(ext > 1, ghi / np.maximum(ext, 1), 0.0), 0, 1.0)
    fd = np.where(kt <= 0.22, 1 - 0.09*kt,
         np.where(kt <= 0.80,
                  0.9511 - 0.1604*kt + 4.388*kt**2 - 16.638*kt**3 + 12.336*kt**4,
                  0.165))
    dhi = fd * ghi
    dni = np.where(cosz > 0.05, (ghi - dhi) / np.maximum(cosz, 0.05), 0.0)
    return np.clip(dni, 0, 950.0), dhi

def dewpoint_to_rh(t, td):
    es = lambda x: 6.112 * np.exp(17.62 * x / (243.12 + x))
    return np.clip(100.0 * es(td) / es(t), 3, 100)

# ---------------------------------------------------------------------------
def generate_base_year(seed=42):
    rng = np.random.default_rng(seed)
    ndays, nh = 365, 8760
    doy_d = np.arange(ndays)

    t_seas = seasonal_interp(T_MONTH, doy_d)
    anom = np.zeros(ndays)
    for d in range(1, ndays):
        anom[d] = 0.72 * anom[d - 1] + rng.normal(0, 1.85)
    t_day = t_seas + anom

    kt_day = np.zeros(ndays)
    cosz_h = np.zeros(nh); I0_h = np.zeros(nh)
    hrs = np.arange(24) + 0.5
    for d in range(ndays):
        cz, i0 = solar_geometry(d + 1, hrs)
        cosz_h[d*24:(d+1)*24] = cz; I0_h[d*24:(d+1)*24] = i0
    ghics_h = clearsky_ghi(cosz_h)
    ghics_day_month = np.zeros(12)
    for m in range(12):
        mask = np.repeat(MONTH_OF_DAY == m, 24)
        ghics_day_month[m] = ghics_h[mask].sum() / 1000.0
    kt_target = np.array(GHI_MONTH) / np.maximum(ghics_day_month, 1e-6)
    for d in range(ndays):
        kt_day[d] = np.clip(rng.normal(kt_target[MONTH_OF_DAY[d]], 0.17), 0.12, 0.85)
    for m in range(12):
        sel = MONTH_OF_DAY == m
        kt_day[sel] *= kt_target[m] / kt_day[sel].mean()
    kt_day = np.clip(kt_day, 0.10, 0.88)

    dr_seas = seasonal_interp(DR_MONTH, doy_d) * (0.55 + 0.75 * kt_day)
    t_h = np.zeros(nh)
    h24 = np.arange(24)
    shape = np.cos(2 * math.pi * (h24 - 15.0) / 24.0)
    for d in range(ndays):
        t_h[d*24:(d+1)*24] = t_day[d] + 0.5 * dr_seas[d] * shape
    t_h = np.convolve(t_h, np.ones(3)/3.0, mode="same")

    ghi = ghics_h * np.repeat(kt_day, 24)
    dni, dhi = erbs_split(ghi, cosz_h, I0_h)

    dep_day = 2.0 + 7.0 * kt_day + np.clip(0.35 * (t_day - 14), 0, 6) + rng.normal(0, 0.8, ndays)
    dep_h = np.repeat(np.clip(dep_day, 1.0, 16.0), 24) * (0.6 + 0.4 * np.tile((shape + 1) / 2, ndays))
    td_h = t_h - np.maximum(dep_h, 0.5)

    w = np.zeros(nh)
    for i in range(1, nh):
        w[i] = 0.92 * w[i - 1] + rng.normal(0, 0.55)
    wind = np.clip(WIND_MEAN + w, 0.3, 18.0)
    wdir = (200 + 60 * np.sin(np.arange(nh) / 200.0) + rng.normal(0, 40, nh)) % 360

    cloud = np.clip(10.0 * (1.0 - np.repeat(kt_day, 24) / 0.85), 0, 10)
    press = 101325.0 + rng.normal(0, 400, nh) - ELEV * 12.0
    return dict(t=t_h, td=td_h, ghi=ghi, dni=dni, dhi=dhi, wind=wind, wdir=wdir,
                cloud=cloud, press=press, cosz=cosz_h, I0=I0_h, kt_day=kt_day, anom=anom)

def apply_morphing(wx, dt_month):
    dtm = np.repeat(seasonal_interp(dt_month, np.arange(365)), 24)
    wx["t"] = wx["t"] + dtm
    wx["td"] = wx["td"] + 0.6 * dtm
    return wx

def inject_heatwave(wx, start_doy, ndays_hw, peak_bump, rng=None):
    ramp = np.sin(np.linspace(0.05, math.pi - 0.05, ndays_hw)) ** 0.7
    for k in range(ndays_hw):
        d = start_doy - 1 + k
        if d >= 365: break
        s, e = d * 24, (d + 1) * 24
        bump = peak_bump * ramp[k]
        if "anom" in wx:  # neutralize random anomaly so peaks are controlled
            bump = max(bump - 0.8 * wx["anom"][d], 0.35 * peak_bump * ramp[k])
        wx["t"][s:e] += bump
        wx["td"][s:e] += 0.25 * bump
        cz = wx["cosz"][s:e]; i0 = wx["I0"][s:e]
        ghi = clearsky_ghi(cz) * 0.78
        dni, dhi = erbs_split(ghi, cz, i0)
        wx["ghi"][s:e], wx["dni"][s:e], wx["dhi"][s:e] = ghi, dni, dhi
        wx["cloud"][s:e] = 1.0
        wx["wind"][s:e] = np.clip(wx["wind"][s:e] * 0.55, 0.5, None)
    return wx

def horizontal_ir(t, td, cloud):
    e_clr = 0.711 + 0.56 * (td / 100.0) + 0.73 * (td / 100.0) ** 2
    cc = cloud / 10.0
    e_sky = np.clip(e_clr * (1 - cc**2) + 0.96 * cc**2, 0.5, 1.0)
    return e_sky * SIGMA * (t + 273.15) ** 4

def ground_temps(t_h):
    tm = np.array([t_h[np.repeat(MONTH_OF_DAY == m, 24)].mean() for m in range(12)])
    tann = tm.mean()
    return tann + 0.75 * (np.roll(tm, 1) - tann)

def write_epw(path, wx, title, year=2050):
    rh = dewpoint_to_rh(wx["t"], wx["td"])
    ir = horizontal_ir(wx["t"], wx["td"], wx["cloud"])
    gt = ground_temps(wx["t"])
    lines = []
    lines.append(f"LOCATION,Paris Orly {title},IDF,FRA,Synthetic-future,071490,{LAT},{LON},{TZ:.1f},{ELEV}")
    lines.append("DESIGN CONDITIONS,0")
    lines.append("TYPICAL/EXTREME PERIODS,0")
    lines.append("GROUND TEMPERATURES,1,0.5,,,," + ",".join(f"{v:.2f}" for v in gt))
    lines.append("HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0")
    lines.append(f"COMMENTS 1,Synthetic Paris weather calibrated to 1991-2020 normals; morphed to 2050 SSP2-4.5; {title}")
    lines.append("COMMENTS 2,Generated by weather_gen.py (RC building simulation project)")
    lines.append("DATA PERIODS,1,1,Data,Sunday,1/1,12/31")
    i = 0
    for m in range(12):
        for d in range(DAYS[m]):
            for h in range(24):
                lines.append(
                    f"{year},{m+1},{d+1},{h+1},0,_,"
                    f"{wx['t'][i]:.1f},{wx['td'][i]:.1f},{rh[i]:.0f},{wx['press'][i]:.0f},"
                    f"9999,9999,{ir[i]:.0f},"
                    f"{wx['ghi'][i]:.0f},{wx['dni'][i]:.0f},{wx['dhi'][i]:.0f},"
                    f"999999,999999,999999,9999,"
                    f"{wx['wdir'][i]:.0f},{wx['wind'][i]:.1f},"
                    f"{wx['cloud'][i]:.0f},{wx['cloud'][i]:.0f},"
                    f"9999,99999,9,999999999,0,0.0,0,88,0.2,0.0,0.0")
                i += 1
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {path}")

def load_epw_for_morphing(path):
    import csv
    t, td, ghi, dni, dhi, wind, wdir, cloud, press = ([] for _ in range(9))
    with open(path) as f:
        rows = list(csv.reader(f))[8:]
    for r in rows[:8760]:
        t.append(float(r[6])); td.append(float(r[7])); press.append(float(r[9]))
        ghi.append(float(r[13])); dni.append(float(r[14])); dhi.append(float(r[15]))
        wdir.append(float(r[20])); wind.append(float(r[21])); cloud.append(float(r[22]))
    cz, i0 = np.zeros(8760), np.zeros(8760)
    for d in range(365):
        c, ii = solar_geometry(d + 1, np.arange(24) + 0.5)
        cz[d*24:(d+1)*24] = c; i0[d*24:(d+1)*24] = ii
    return dict(t=np.array(t), td=np.array(td), ghi=np.array(ghi), dni=np.array(dni),
                dhi=np.array(dhi), wind=np.array(wind), wdir=np.array(wdir),
                cloud=np.array(cloud), press=np.array(press), cosz=cz, I0=i0)

def main():
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weather")
    os.makedirs(outdir, exist_ok=True)
    src = None
    if "--from-epw" in sys.argv:
        src = sys.argv[sys.argv.index("--from-epw") + 1]
    year = 2050 if "--year" in sys.argv and sys.argv[sys.argv.index("--year") + 1] == "2050" else 2090

    def fresh():
        return load_epw_for_morphing(src) if src else generate_base_year(seed=42)

    if year == 2050:
        wx = apply_morphing(fresh(), DT_2050)
        wx = inject_heatwave(wx, start_doy=176, ndays_hw=5, peak_bump=7.0)
        wx = inject_heatwave(wx, start_doy=228, ndays_hw=4, peak_bump=5.5)
        write_epw(os.path.join(outdir, "FRA_Paris_2050_typical.epw"), wx,
                  "2050 Typical SSP2-4.5", 2050)
        wx = apply_morphing(fresh(), [d + (1.0 if 5 <= m <= 8 else 0.2)
                                      for m, d in enumerate(DT_2050)])
        wx = inject_heatwave(wx, start_doy=176, ndays_hw=6, peak_bump=9.0)
        wx = inject_heatwave(wx, start_doy=193, ndays_hw=13, peak_bump=13.0)
        wx = inject_heatwave(wx, start_doy=228, ndays_hw=5, peak_bump=9.0)
        write_epw(os.path.join(outdir, "FRA_Paris_2050_heatwave.epw"), wx,
                  "2050 Extreme Heatwave SSP2-4.5", 2050)
    else:
        # --- 2090 typical year: morph + two moderate-to-strong heat waves ---
        wx = apply_morphing(fresh(), DT_2090)
        wx = inject_heatwave(wx, start_doy=176, ndays_hw=6, peak_bump=8.0)
        wx = inject_heatwave(wx, start_doy=228, ndays_hw=5, peak_bump=6.5)
        write_epw(os.path.join(outdir, "FRA_Paris_2090_typical.epw"), wx,
                  "2090 Typical SSP2-4.5", 2090)
        # --- 2090 extreme heat-wave year: hotter summer + 16-day mega event ---
        wx = apply_morphing(fresh(), [d + (1.2 if 5 <= m <= 8 else 0.3)
                                      for m, d in enumerate(DT_2090)])
        wx = inject_heatwave(wx, start_doy=175, ndays_hw=8, peak_bump=10.5)
        wx = inject_heatwave(wx, start_doy=191, ndays_hw=16, peak_bump=15.0)
        wx = inject_heatwave(wx, start_doy=227, ndays_hw=7, peak_bump=10.5)
        write_epw(os.path.join(outdir, "FRA_Paris_2090_heatwave.epw"), wx,
                  "2090 Extreme Heatwave SSP2-4.5", 2090)

if __name__ == "__main__":
    main()
