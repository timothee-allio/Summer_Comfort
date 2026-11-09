"""
building_sim.py - Dynamic single-zone thermal simulation engine (pure Python/numpy).

Physics:
  * RC network: zone air node, internal thermal-mass node, and 2 mass nodes per
    opaque envelope element (3R2C), solved implicitly (backward Euler).
    SurfaceDef.ext_frac places the mass relative to the insulation
    (high ext_frac = insulation outside, heavy layer facing the room).
  * Sol-air temperature on opaque surfaces (solar absorption + LW sky loss).
  * Window solar gains: beam + isotropic diffuse + ground-reflected per
    orientation, incidence-angle SHGC modifier, overhang shading (profile angle),
    and optional temperature-controlled external shades on east/west windows.
  * Infiltration (constant + wind term), constant mechanical ventilation with
    fan energy (SFP), and rule-controlled natural window ventilation:
    windows open at maximum when the zone is warm (near/above the cooling
    setpoint) AND the outdoor temperature is below the cooling setpoint;
    they are closed whenever the outdoor temperature is above it.
  * Ideal heating and cooling with setpoints and capacity limits.
  * Internal gains from people and equipment (weekday/weekend schedules).
  * EPW weather input, hourly output, sub-hourly integration (default 10 min).
"""
import numpy as np
import math, csv, os
from dataclasses import dataclass, field

RHO_CP = 1.2 * 1005.0    # J/m3K air
G = 9.81

# ---------------------------------------------------------------- weather ---
class Weather:
    """Parse an EPW file. Hour h data represent the hour ending at h (EPW spec)."""
    def __init__(self, path, lat=48.72, lon=2.38, tz=1.0):
        self.lat, self.lon, self.tz = lat, lon, tz
        with open(path) as f:
            r = list(csv.reader(f))
        for line in r[:8]:
            if line[0] == "LOCATION":
                self.lat, self.lon, self.tz = float(line[6]), float(line[7]), float(line[8])
            if line[0] == "GROUND TEMPERATURES" and len(line) > 17:
                self.t_ground_month = [float(x) for x in line[6:18]]
        rows = r[8:8 + 8760]
        A = lambda i: np.array([float(x[i]) for x in rows])
        self.month = A(1).astype(int); self.day = A(2).astype(int); self.hour = A(3).astype(int)
        self.t_out, self.t_dew, self.rh = A(6), A(7), A(8)
        self.ghi, self.dni, self.dhi = A(13), A(14), A(15)
        self.wdir, self.wind, self.cloud = A(20), A(21), A(22)
        if not hasattr(self, "t_ground_month"):
            self.t_ground_month = [self.t_out.mean()] * 12
        days = [31,28,31,30,31,30,31,31,30,31,30,31]
        cum = np.cumsum([0] + days)
        self.doy = np.array([cum[self.month[i]-1] + self.day[i] for i in range(8760)])

    def sun_positions(self):
        """Solar altitude and azimuth (deg) for all 8760 hours, vectorised and
        cached. Same formulas as sun_position()."""
        if getattr(self, "_sun_cache", None) is None:
            doy, hf = self.doy.astype(float), self.hour.astype(float) - 0.5
            B = 2 * np.pi * (doy - 1 + hf / 24.0) / 365.0
            decl = 0.006918 - 0.399912*np.cos(B) + 0.070257*np.sin(B) - 0.006758*np.cos(2*B) \
                   + 0.000907*np.sin(2*B) - 0.002697*np.cos(3*B) + 0.00148*np.sin(3*B)
            eot = 229.18 * (0.000075 + 0.001868*np.cos(B) - 0.032077*np.sin(B)
                            - 0.014615*np.cos(2*B) - 0.04089*np.sin(2*B))
            tsol = hf + (4.0 * (self.lon - 15.0 * self.tz) + eot) / 60.0
            ha = np.radians(15.0 * (tsol - 12.0))
            lat = math.radians(self.lat)
            sin_alt = math.sin(lat)*np.sin(decl) + math.cos(lat)*np.cos(decl)*np.cos(ha)
            alt = np.arcsin(np.clip(sin_alt, -1, 1))
            cos_az = (np.sin(decl) - math.sin(lat)*sin_alt) / np.maximum(1e-6, math.cos(lat)*np.cos(alt))
            az = np.arccos(np.clip(cos_az, -1, 1))
            az = np.where(ha > 0, 2*np.pi - az, az)
            self._sun_cache = (np.degrees(alt), np.degrees(az))
        return self._sun_cache

    def sun_position(self, i):
        doy, hf = self.doy[i], self.hour[i] - 0.5
        B = 2 * math.pi * (doy - 1 + hf / 24.0) / 365.0
        decl = 0.006918 - 0.399912*math.cos(B) + 0.070257*math.sin(B) - 0.006758*math.cos(2*B) \
               + 0.000907*math.sin(2*B) - 0.002697*math.cos(3*B) + 0.00148*math.sin(3*B)
        eot = 229.18 * (0.000075 + 0.001868*math.cos(B) - 0.032077*math.sin(B)
                        - 0.014615*math.cos(2*B) - 0.04089*math.sin(2*B))
        tsol = hf + (4.0 * (self.lon - 15.0 * self.tz) + eot) / 60.0
        ha = math.radians(15.0 * (tsol - 12.0))
        lat = math.radians(self.lat)
        sin_alt = math.sin(lat)*math.sin(decl) + math.cos(lat)*math.cos(decl)*math.cos(ha)
        alt = math.asin(max(-1, min(1, sin_alt)))
        cos_az = (math.sin(decl) - math.sin(lat)*sin_alt) / max(1e-6, math.cos(lat)*math.cos(alt))
        az = math.acos(max(-1, min(1, cos_az)))
        if ha > 0: az = 2*math.pi - az
        return math.degrees(alt), math.degrees(az)

# --------------------------------------------------------------- building ---
@dataclass
class WindowDef:
    area: float; azimuth: float; U: float = 1.3; shgc: float = 0.55
    height: float = 1.5
    overhang_depth: float = 0.0
    overhang_gap: float = 0.1

@dataclass
class SurfaceDef:
    name: str; area: float; azimuth: float; tilt: float
    U: float; heat_cap: float
    absorptivity: float = 0.6
    ext_frac: float = 0.5     # fraction of (non-film) R outside the mass nodes

@dataclass
class Building:
    floor_area: float = 100.0
    height: float = 2.7
    surfaces: list = field(default_factory=list)
    windows: list = field(default_factory=list)
    # internal mass
    c_int: float = 25e6
    a_int: float = 250.0
    h_int: float = 3.0
    c_air_mult: float = 5.0
    # infiltration
    ach_infiltration: float = 0.15
    ach_wind_coeff: float = 0.015
    # mechanical ventilation
    mech_vent_ach: float = 0.0
    fan_sfp: float = 500.0            # W per (m3/s)
    # natural window ventilation (rule tied to cooling setpoint)
    vent_open_area: float = 2.0       # m2 effective openable area (maximum opening)
    vent_opening_height: float = 1.2
    vent_max_ach: float = 10.0
    # HVAC
    heat_setpoint: float = 20.0
    cool_setpoint: float = 26.0
    heat_capacity_w: float = 25000.0
    cool_capacity_w: float = 15000.0
    cooling_enabled: bool = True
    gains_wk: list = None
    gains_we: list = None
    solar_to_air_frac: float = 0.3
    gains_to_air_frac: float = 0.6
    # External blinds deploy on east and west windows once the zone air is warm.
    external_shading_enabled: bool = False
    external_shading_setpoint: float = 24.0
    external_shading_reduction: float = 0.80

    def volume(self): return self.floor_area * self.height

def example_house():
    """100 m2 well-insulated single-storey dwelling (original demo building)."""
    w, l, h = 8.0, 12.5, 2.7
    walls = dict(S=w*h, N=w*h, E=l*h, W=l*h)
    win = dict(S=10.0, W=4.0, E=3.0, N=2.0)
    az = dict(N=0.0, E=90.0, S=180.0, W=270.0)
    surfaces, windows = [], []
    for o in "SNEW":
        surfaces.append(SurfaceDef(f"wall_{o}", walls[o] - win[o], az[o], 90.0,
                                   U=0.25, heat_cap=180e3, absorptivity=0.6))
    surfaces.append(SurfaceDef("roof", w*l, 0.0, 0.0, U=0.18, heat_cap=120e3, absorptivity=0.8))
    surfaces.append(SurfaceDef("floor", w*l, 0.0, 180.0, U=0.30, heat_cap=300e3))
    for o in "SNEW":
        windows.append(WindowDef(win[o], az[o], U=1.3, shgc=0.55, height=1.5,
                                 overhang_depth=0.8 if o == "S" else 0.0))
    people = [80,80,80,80,80,80,160,160,80,40,40,40,40,40,40,40,120,240,320,320,320,240,160,80]
    equip  = [120,120,120,120,120,120,200,300,200,150,150,150,150,150,150,150,250,450,500,500,450,350,250,150]
    people_we = [80,80,80,80,80,80,120,240,320,320,240,240,240,240,240,240,240,320,320,320,320,240,160,80]
    equip_we  = [120,120,120,120,120,120,150,300,400,350,300,300,300,300,250,250,300,450,500,500,450,350,250,150]
    return Building(floor_area=w*l, height=h, surfaces=surfaces, windows=windows,
                    heat_capacity_w=6000.0, cool_capacity_w=5000.0,
                    gains_wk=[(p, e) for p, e in zip(people, equip)],
                    gains_we=[(p, e) for p, e in zip(people_we, equip_we)])

# ------------------------------------------------------- app parameters ---
WEATHER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weather")
WEATHER_CASES = ("Paris_2050_typical", "Paris_2050_heatwave",
                 "Paris_2090_typical", "Paris_2090_heatwave")

def weather_path(case):
    """Absolute path of the EPW file for one of WEATHER_CASES."""
    if case not in WEATHER_CASES:
        raise ValueError(f"unknown weather case {case!r}, expected one of {WEATHER_CASES}")
    return os.path.join(WEATHER_DIR, f"FRA_{case}.epw")

def vent_area_for_ach(ach, volume, opening_height=1.2, dT_ref=3.0, t_avg_k=297.0):
    """Effective openable area (m2) whose stack-driven flow, with no wind and an
    indoor-outdoor difference of dT_ref, gives `ach` air changes per hour.
    Uses the same stack formula as simulate()."""
    if ach <= 0:
        return 0.0
    q_per_m2 = (1.0 / 3.0) * math.sqrt(G * opening_height * dT_ref / t_avg_k)
    return ach * volume / 3600.0 / q_per_m2

def build_case(wall_r, window_area, overhang_depth, vent_max_ach, external_shading):
    """Building used by the web app and by generate_database.py.

    Starts from example_house() and applies the five app parameters:
      wall_r            wall thermal resistance (m2K/W), U = 1/R
      window_area       total glazing (m2), split equally over the four facades;
                        each wall's opaque area is reduced accordingly so the
                        gross facade area stays constant
      overhang_depth    overhang (m) above the south window only
      vent_max_ach      night ventilation (ACH): sets both the cap and the
                        openable area, so the value is actually reachable
      external_shading  temperature-controlled blinds on east/west windows
    """
    bld = example_house()
    bld.vent_max_ach = vent_max_ach
    bld.vent_open_area = vent_area_for_ach(vent_max_ach, bld.volume(),
                                           bld.vent_opening_height)
    bld.external_shading_enabled = bool(external_shading)

    u_wall = 1.0 / wall_r if wall_r > 0 else 5.0
    walls = {s.azimuth: s for s in bld.surfaces if s.name.startswith("wall")}
    for s in walls.values():
        s.U = u_wall

    per_window = window_area / len(bld.windows)
    for w in bld.windows:
        wall = walls[w.azimuth]
        gross = wall.area + w.area
        if per_window >= gross:
            raise ValueError(f"window area {per_window:.1f} m2 does not fit in the "
                             f"{gross:.1f} m2 facade facing {w.azimuth:.0f} deg")
        wall.area = gross - per_window
        w.area = per_window
        w.overhang_depth = overhang_depth if abs(w.azimuth - 180.0) < 1e-6 else 0.0
    return bld

# ------------------------------------------------------------------ solar ---
def incident_and_transmitted(bld, wx):
    """Hourly sol-air terms per surface and transmitted solar gains per window.
    Vectorised over the 8760 hours (same equations as the original loop)."""
    n = 8760
    ns = len(bld.surfaces)
    q_solair_extra = np.zeros((ns, n))
    # Keep each window separate: temperature-controlled external shades are
    # applied during the sub-hourly zone solve, after the current indoor
    # temperature is known.
    q_win = np.zeros((len(bld.windows), n))
    HO = 25.0
    albedo = 0.2
    ghi, dni, dhi = wx.ghi[:n], wx.dni[:n], wx.dhi[:n]
    alt, az_sun = wx.sun_positions()
    sun_up = (alt > 0.5) & (ghi > 1)
    for s_idx, s in enumerate(bld.surfaces):
        if s.name == "floor":
            continue
        tilt = math.radians(s.tilt)
        cosi = _cos_incidence(alt, az_sun, s.tilt, s.azimuth)
        itot = dni * np.maximum(0.0, cosi) + dhi * (1 + math.cos(tilt)) / 2 \
               + ghi * albedo * (1 - math.cos(tilt)) / 2
        itot = np.where(sun_up, itot, 0.0)
        lw = 3.9 if s.tilt < 45 else 0.5
        q_solair_extra[s_idx] = s.absorptivity * itot / HO - lw
    nsh = np.zeros(n); fsh = np.zeros(n)
    for w_idx, wdef in enumerate(bld.windows):
        cosi = _cos_incidence(alt, az_sun, 90.0, wdef.azimuth)
        f_beam = np.ones(n)
        if wdef.overhang_depth > 0:
            lit = cosi > 0
            gamma = np.radians(np.abs(np.mod((az_sun - wdef.azimuth) + 180, 360) - 180))
            front = lit & (gamma < np.pi / 2)
            tan_prof = np.tan(np.radians(alt)) / np.maximum(np.cos(gamma), 1e-3)
            shadow = wdef.overhang_depth * tan_prof - wdef.overhang_gap
            f_beam = np.where(front, np.clip(1.0 - shadow / wdef.height, 0.0, 1.0), 1.0)
            nsh += lit; fsh += np.where(lit, 1 - f_beam, 0.0)
        ib = dni * np.maximum(0.0, cosi) * f_beam
        idf = dhi * 0.5 * (0.85 if wdef.overhang_depth > 0 else 1.0)
        ig = ghi * albedo * 0.5
        iam = np.where(cosi > 0,
                       np.maximum(0.0, 1 - 0.25 * (1 / np.maximum(cosi, 0.35) - 1)), 0.9)
        transmitted = wdef.area * wdef.shgc * (ib * iam + 0.9 * (idf + ig))
        q_win[w_idx] = np.where(sun_up, transmitted, 0.0)
    shade_frac_log = np.where(sun_up & (nsh > 0), fsh / np.maximum(nsh, 1), 0.0)
    return q_solair_extra, q_win, shade_frac_log

def _is_east_or_west(azimuth):
    """True for a vertical window facing east or west, i.e. within 45 deg of
    due east (90) or due west (270). South- and north-facing windows
    (within 45 deg of 180 or 0) are excluded."""
    direction = azimuth % 360.0
    return abs(direction - 90.0) < 45.0 or abs(direction - 270.0) < 45.0

def _cos_incidence(alt_deg, az_sun_deg, tilt_deg, az_surf_deg):
    """Cosine of the incidence angle; accepts scalars or numpy arrays."""
    alt, azs = np.radians(alt_deg), np.radians(az_sun_deg)
    t, a = math.radians(tilt_deg), math.radians(az_surf_deg)
    return (np.cos(alt) * np.sin(azs) * math.sin(t) * math.sin(a)
            + np.cos(alt) * np.cos(azs) * math.sin(t) * math.cos(a)
            + np.sin(alt) * math.cos(t))

# -------------------------------------------------------------- simulator ---
def simulate(bld: Building, wx: Weather, dt=600.0, t_init=20.0):
    ns = len(bld.surfaces)
    nn = 2 + 2 * ns
    AIR, IM = 0, 1
    HO, HI = 25.0, 7.7

    C = np.zeros(nn)
    C[AIR] = RHO_CP * bld.volume() * bld.c_air_mult
    C[IM] = bld.c_int
    K_in, K_out_amb, K_out_gnd = [], np.zeros(nn), np.zeros(nn)
    for k, s in enumerate(bld.surfaces):
        n1, n2 = 2 + 2*k, 3 + 2*k
        C[n1] = C[n2] = 0.5 * s.heat_cap * s.area
        r_tot = 1.0 / s.U
        r_nf = max(r_tot - 1/HO - 1/HI, 0.05)
        f = min(max(s.ext_frac, 0.05), 0.92)
        r_out, r_half = f * r_nf, 0.5 * (1 - f) * r_nf
        k_mid = s.area / max(r_half, 1e-3)
        k_in = s.area / (r_half + 1/HI)
        K_in.append((n1, n2, k_mid)); K_in.append((n2, AIR, k_in))
        if s.name == "floor":
            K_out_gnd[n1] = s.area / (1/HO + r_out + 0.8)
        else:
            K_out_amb[n1] = s.area / (1/HO + r_out)
    UA_win = sum(w.area * w.U for w in bld.windows)
    K_in.append((IM, AIR, bld.a_int * bld.h_int))

    q_solair_extra, q_win_solar, shade_log = incident_and_transmitted(bld, wx)
    east_west_window_indices = [
        i for i, wdef in enumerate(bld.windows) if _is_east_or_west(wdef.azimuth)
    ]

    K0 = np.zeros((nn, nn))
    for i, j, kk in K_in:
        K0[i, i] += kk; K0[j, j] += kk; K0[i, j] -= kk; K0[j, i] -= kk
    K0[AIR, AIR] += UA_win
    for nidx in range(nn):
        K0[nidx, nidx] += K_out_amb[nidx] + K_out_gnd[nidx]

    fan_w = bld.fan_sfp * bld.mech_vent_ach * bld.volume() / 3600.0
    # Buildings created without occupancy profiles have no internal gains.
    no_gains = [(0.0, 0.0)] * 24
    gains_wk = bld.gains_wk if bld.gains_wk is not None else no_gains
    gains_we = bld.gains_we if bld.gains_we is not None else no_gains

    T = np.full(nn, t_init, float)
    win_open = False
    nsub = max(1, int(round(3600.0 / dt)))
    out = {k: np.zeros(8760) for k in
           ["t_air", "t_op", "t_out", "q_heat", "q_cool", "q_fan", "ach_vent",
            "ach_inf", "ach_mech", "win_open", "q_sol_win", "q_int", "shade_frac",
            "external_shade_active"]}
    balance_in, balance_out = 0.0, 0.0
    cs = bld.cool_setpoint

    # The system matrix only changes through H_ve on the (AIR, AIR) entry:
    #   A = A0 + H_ve * e_air e_air^T,  A0 = diag(C/dt) + K0  (constant).
    # Invert A0 once and handle H_ve with the Sherman-Morrison formula.
    # HVAC is a heat input q at the air node, so T(q) = T(0) + q * A^-1 e_air,
    # which gives the load needed to hold a setpoint in closed form. This is
    # algebraically identical to solving the full system at every sub-step.
    C_dt = C / dt
    A0inv = np.linalg.inv(np.diag(C_dt) + K0)
    u = A0inv[:, AIR].copy()
    u_a = u[AIR]

    # Envelope boundary terms for every hour (constant within the hour).
    floor_mask = np.array([s.name == "floor" for s in bld.surfaces])
    t_gnd_h = np.array(wx.t_ground_month)[wx.month - 1]
    b_env = np.zeros((8760, nn))
    for k, s in enumerate(bld.surfaces):
        n1 = 2 + 2*k
        if floor_mask[k]:
            b_env[:, n1] = K_out_gnd[n1] * t_gnd_h
        else:
            b_env[:, n1] = K_out_amb[n1] * (wx.t_out[:8760] + q_solair_extra[k])
    q_sol_all = q_win_solar.sum(axis=0)
    q_sol_ew = (q_win_solar[east_west_window_indices].sum(axis=0)
                if east_west_window_indices else np.zeros(8760))
    f_sol, f_int = bld.solar_to_air_frac, bld.gains_to_air_frac
    vol = bld.volume()
    H_fixed_ach = bld.mech_vent_ach
    shade_on = bld.external_shading_enabled and bool(east_west_window_indices)

    for h in range(8760):
        t_out = wx.t_out[h]
        wind = wx.wind[h]
        dow = ((wx.doy[h] - 1) % 7)
        weekend = dow in (0, 6)
        p_gain, e_gain = (gains_we if weekend else gains_wk)[wx.hour[h] - 1]
        q_int = p_gain + e_gain
        ach_inf = bld.ach_infiltration + bld.ach_wind_coeff * wind
        b_h = b_env[h]

        qh_h = qc_h = 0.0; ach_v_h = qsol_h = shade_active_h = 0.0
        for sub in range(nsub):
            t_air = T[AIR]
            q_sol = q_sol_all[h]
            external_shade_active = shade_on and t_air > bld.external_shading_setpoint
            if external_shade_active:
                q_sol -= bld.external_shading_reduction * q_sol_ew[h]
            # --- window rule: free cooling with max opening; closed if Tout >= cs
            if win_open:
                if t_air < cs - 1.5 or t_out > cs - 0.2:
                    win_open = False
            else:
                if t_air > cs - 0.3 and t_out < cs - 0.5:
                    win_open = True
            ach_v = 0.0
            if win_open:
                dT = max(t_air - t_out, 0.1)
                t_avg = 0.5 * (t_air + t_out) + 273.15
                q_stack = (bld.vent_open_area / 3.0) * math.sqrt(
                    G * bld.vent_opening_height * dT / t_avg)
                q_wind = 0.025 * bld.vent_open_area * wind
                q_v = math.sqrt(q_stack**2 + q_wind**2)
                ach_v = min(q_v * 3600.0 / vol, bld.vent_max_ach)

            H_ve = RHO_CP * (ach_inf + ach_v + H_fixed_ach) * vol / 3600.0

            rhs = C_dt * T + b_h
            rhs[AIR] += (UA_win + H_ve) * t_out + f_sol * q_sol + f_int * q_int
            rhs[IM] += (1 - f_sol) * q_sol + (1 - f_int) * q_int

            y = A0inv @ rhs
            denom = 1.0 + H_ve * u_a
            col = u / denom                       # A^-1 e_air
            T_new = y - (H_ve * y[AIR] / denom) * u   # A^-1 rhs

            q_hvac = 0.0
            if T_new[AIR] < bld.heat_setpoint:
                q_hvac = (bld.heat_setpoint - T_new[AIR]) / col[AIR]
                q_hvac = min(q_hvac, bld.heat_capacity_w)
            elif bld.cooling_enabled and T_new[AIR] > cs:
                q_hvac = (cs - T_new[AIR]) / col[AIR]
                q_hvac = max(q_hvac, -bld.cool_capacity_w)
            if q_hvac != 0.0:
                T_new = T_new + q_hvac * col

            T = T_new
            qh_h += max(q_hvac, 0) * dt; qc_h += max(-q_hvac, 0) * dt
            ach_v_h += ach_v
            qsol_h += q_sol
            shade_active_h += 1.0 if external_shade_active else 0.0
            balance_in += (max(q_hvac, 0) + q_sol + q_int) * dt
            balance_out += max(-q_hvac, 0) * dt

        surf_inner = [T[3 + 2*k] for k in range(ns)]
        t_mr = (sum(si * s.area for si, s in zip(surf_inner, bld.surfaces)) + T[IM] * bld.a_int) \
               / (sum(s.area for s in bld.surfaces) + bld.a_int)
        out["t_air"][h] = T[AIR]
        out["t_op"][h] = 0.5 * (T[AIR] + t_mr)
        out["t_out"][h] = t_out
        out["q_heat"][h] = qh_h / 3600.0
        out["q_cool"][h] = qc_h / 3600.0
        out["q_fan"][h] = fan_w
        out["ach_vent"][h] = ach_v_h / nsub
        out["ach_inf"][h] = ach_inf
        out["ach_mech"][h] = bld.mech_vent_ach
        out["win_open"][h] = 1.0 if out["ach_vent"][h] > 0.01 else 0.0
        out["q_sol_win"][h] = qsol_h / nsub
        out["q_int"][h] = q_int
        out["shade_frac"][h] = shade_log[h]
        out["external_shade_active"][h] = shade_active_h / nsub

    out["month"] = wx.month; out["day"] = wx.day; out["hour"] = wx.hour
    out["_balance"] = (balance_in, balance_out)
    return out

def _pinned_load(A, rhs, node, t_set):
    nn = A.shape[0]
    idx = [i for i in range(nn) if i != node]
    Ar = A[np.ix_(idx, idx)]
    br = rhs[idx] - A[np.ix_(idx, [node])].flatten() * t_set
    T_others = np.linalg.solve(Ar, br)
    Tfull = np.zeros(nn); Tfull[node] = t_set
    for k, i in enumerate(idx): Tfull[i] = T_others[k]
    return float(A[node] @ Tfull - rhs[node])

# ------------------------------------------------------------------ stats ---
def summarize(res, label, floor_area):
    heat_kwh = res["q_heat"].sum() / 1000.0
    cool_kwh = res["q_cool"].sum() / 1000.0
    fan_kwh = res["q_fan"].sum() / 1000.0
    top, tair = res["t_op"], res["t_air"]
    return dict(label=label,
                heating_kWh=round(heat_kwh, 0), heating_kWh_m2=round(heat_kwh / floor_area, 1),
                cooling_kWh=round(cool_kwh, 0), cooling_kWh_m2=round(cool_kwh / floor_area, 1),
                fan_kWh=round(fan_kwh, 0),
                total_kWh=round(heat_kwh + cool_kwh + fan_kwh, 0),
                total_kWh_m2=round((heat_kwh + cool_kwh + fan_kwh) / floor_area, 1),
                hours_above_26=int((top > 26).sum()), hours_above_28=int((top > 28).sum()),
                hours_air_above_28=int((tair > 28).sum()),
                hours_above_30=int((top > 30).sum()),
                peak_t_op=round(top.max(), 1), peak_t_out=round(res["t_out"].max(), 1),
                vent_hours=int(res["win_open"].sum()))
