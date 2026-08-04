# Scenario results - Paris 2050 (SSP2-4.5), 150 m2 single-family house

Setpoints 21 C / 24 C, ideal heating & cooling, mech. ventilation 0.5 ACH,
windows open at maximum for free cooling only when Tout < 24 C (closed above).
Overheating counted on air temperature (Tair) and operative temperature (Top).

| Building | Weather year | Heating kWh | Cooling kWh | Fan kWh | TOTAL kWh | kWh/m2 | h Tair>26 | h Tair>28 | h Top>26 | h Top>28 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1980s | typical | 22701 | 2915 | 246 | **25863** | 172.4 | 0 | 0 | 0 | 0 |
| 1980s | heatwave | 21984 | 5481 | 246 | **27712** | 184.7 | 0 | 0 | 0 | 0 |
| 1980s_no_overhang | typical | 22255 | 3332 | 246 | **25834** | 172.2 | 0 | 0 | 0 | 0 |
| 1980s_no_overhang | heatwave | 21568 | 5988 | 246 | **27802** | 185.3 | 0 | 0 | 0 | 0 |
| retrofit_40cm | typical | 4553 | 2969 | 246 | **7767** | 51.8 | 0 | 0 | 0 | 0 |
| retrofit_40cm | heatwave | 4397 | 4253 | 246 | **8897** | 59.3 | 0 | 0 | 0 | 0 |
| retrofit_40cm_no_overhang | typical | 4357 | 3452 | 246 | **8055** | 53.7 | 0 | 0 | 0 | 0 |
| retrofit_40cm_no_overhang | heatwave | 4211 | 4828 | 246 | **9286** | 61.9 | 0 | 0 | 0 | 0 |

Notes:
- Heating/cooling are ideal-load (thermal) demands; fan is electricity (SFP 0.5 kW/(m3/s)).
- Ideal cooling holds Tair at 24 C, so air-based overheating stays ~0;
  operative temperature also counts warm interior surfaces.
- Cooling operating hours: 1980s/typical: 1116 h, 1980s/heatwave: 1473 h, 1980s_no_overhang/typical: 1179 h, 1980s_no_overhang/heatwave: 1532 h, retrofit_40cm/typical: 1328 h, retrofit_40cm/heatwave: 1685 h, retrofit_40cm_no_overhang/typical: 1390 h, retrofit_40cm_no_overhang/heatwave: 1731 h
