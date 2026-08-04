# Paris 2050 (SSP2-4.5) — Summer-comfort simulation results

Building: 100 m2 single-storey dwelling, U-wall 0.25 / roof 0.18 / windows 1.3,
10 m2 south glazing with 0.8 m overhang, night-ventilation control, infiltration 0.15 ACH + wind term.

| Case | Heating kWh/m2 | Cooling kWh/m2 | h >26C | h >28C | h >30C | Peak Top C | Peak Tout C | Vent hours |
|---|---|---|---|---|---|---|---|---|
| typical/cooled | 17.9 | 6.0 | 228 | 0 | 0 | 26.5 | 37.6 | 2367 |
| typical/freefloat | 17.9 | 0.0 | 739 | 189 | 18 | 31.1 | 37.6 | 2567 |
| heatwave/cooled | 17.0 | 14.1 | 706 | 0 | 0 | 26.9 | 42.7 | 2182 |
| heatwave/freefloat | 17.0 | 0.0 | 1217 | 730 | 434 | 39.1 | 42.7 | 2625 |

## Energy bookkeeping

- typical/cooled: total gains (solar+internal+heating) 10767 kWh; mechanical cooling removed 603 kWh; the rest leaves via envelope conduction and (natural) ventilation.
- typical/freefloat: total gains (solar+internal+heating) 10767 kWh; mechanical cooling removed 0 kWh; the rest leaves via envelope conduction and (natural) ventilation.
- heatwave/cooled: total gains (solar+internal+heating) 10701 kWh; mechanical cooling removed 1414 kWh; the rest leaves via envelope conduction and (natural) ventilation.
- heatwave/freefloat: total gains (solar+internal+heating) 10701 kWh; mechanical cooling removed 0 kWh; the rest leaves via envelope conduction and (natural) ventilation.
