# PyPSA → DSO allowable-revenue model

## Excel model (inspected, not modified)

File: `AllowableRevenue_MiniModelEurope.xlsx`, sheet **Sheet1**
(Sheet1 (2) is a depreciation variant; Sheet1 is the working model).

| Item | Cell | Kind | Value / formula | Units |
|---|---|---|---|---|
| WACC | B8 | assumption | 0.054 | fraction |
| Average asset lifetime | B9 | assumption | 42 | years |
| Depreciation rate | B10 | formula | `=1/B9` | 1/year |
| CAPEX share of allowable revenue | B11 | assumption | 0.5 | fraction |
| OPEX growth | B12 | assumption | 0.01 | 1/year |
| Starting RAB Europe | B13 | assumption | 700 | billion EUR |
| Opening RAB | row 16 | formula | 2020=`B13`; later=`previous New RAB` | billion EUR |
| CAPEX addition | row 17 | assumption | 29…60 then 72 (2026-2040) then 60 | billion EUR/yr |
| Depreciation | row 18 | formula | `Opening RAB × dep rate` through 2030; **frozen at 2030 from 2031** (`M18=L18`) | billion EUR/yr |
| New RAB | row 19 | formula | `Opening + CAPEX − Depreciation` | billion EUR |
| Max allowable revenue (CAPEX part) | row 20 | formula | `(Opening+CAPEX)×WACC + Depreciation` | billion EUR/yr |
| OPEX | row 21 | formula | 2020: `MAR_capex×(1/share−1)`; later: 2020 OPEX grown at 1%/yr | billion EUR/yr |
| Max allowable revenue | row 22 | formula | CAPEX-part + OPEX | billion EUR/yr |
| Today's DSO tariff | B29 | assumption | 53 | EUR/MWh |
| 2020 electricity consumption | B30 / F29 | assumption | 2590 / 2589.57 | TWh |
| DSO share of consumption | B31 | assumption | 0.8 | fraction |
| TWh DSO | row 30 | formula | `TWh × 0.8` | TWh |
| Estimated 2020 DSO revenue | B32 | formula | `2590×0.8×53 / 1000` = 109.816 | billion EUR |
| Distribution charges | F34:I34 | formula | scaled 2020 revenue × MAR index / TWh DSO | EUR/MWh |

No price year is stated in the workbook. Cached original tariffs: 2020 ≈ 53.0, 2030 ≈ 48.0, 2040 ≈ 52.0 EUR/MWh.

## PyPSA DSO investment (inspected)

Assets used: links with `carrier == "electricity distribution grid"` **and**
`capital_cost > 0`.

Excluded (same carrier, not DSO investment):

- Data-centre site/demand links (`capital_cost = 0`, not extendable).
- Reverse-direction twins (`"reversed"` in the name, `capital_cost = 0`).

New capacity this horizon:

    ΔP_MW = max(p_nom_opt − p_nom, 0)   on costed links only

| Horizon | What the networks show |
|---|---|
| 2030 | Costed links are new (`p_nom=0`, `p_nom_min=0`, `build_year=2030`, extendable). PyPSA has **no existing DSO RAB**. ΔP is the entire modelled 2030 DSO overlay. |
| 2040 | 2030 cohort is brownfield (`p_nom = 2030 p_nom_opt`, not extendable). 2040 cohort is new. ΔP is **only the 2040 additions**. |

Overnight CAPEX (cash, used **only as a ratio vs Build**):

    overnight EUR = ΔP_MW × 667 901.6 EUR/MW
    ratio_s,y = overnight_{s,y} / overnight_{Build,y}

667 901.6 EUR/MW comes from processed technology-data (`investment` after kW→MW).
Raw value: 667.9016 EUR/kW, **currency_year 2015**, lifetime 40 years, FOM 2%/year,
discount rate 7%. `capital_cost` in PyPSA **includes FOM**. Absolute overnight is
**not** written into the Excel CAPEX row.

### CAPEX written into Excel (ratio method)

A previous trial injected PyPSA absolute overnight into row 17. That workbook is
archived as `AllowableRevenue_MiniModelEurope_PyPSA_TRIAL_absolute_capex.xlsx`.

Current method:

- **Original Excel / Build:** the Excel CAPEX trajectory is the absolute baseline
  (29→60 then 72 bn €/yr in 2026–2040, then 60). Build does not replace those
  numbers with PyPSA euros.
- **85% / 75% / 65% / 50%:**
  - 2020–2025: original Excel CAPEX (same for every scenario)
  - 2026–2030: Excel CAPEX × ratio_2030
  - 2031–2040: Excel CAPEX × ratio_2040
  - 2041+: original Excel 60 bn/yr
- **TWh DSO (G30/H30):** scenario-specific PyPSA HV→LV delivery for *all*
  PyPSA sheets, including Build. Original Excel keeps its own 80%-of-consumption volumes.

This avoids mixing PyPSA's thin HV–LV overlay (EUR2015) with the Excel's 700 bn
European DSO RAB. PyPSA only answers *how much less* is built under inaction.

## Electricity denominator (inspected)

`insert_electricity_distribution_grid` puts regular electricity, industry
electricity, agriculture, BEV chargers, heat pumps and resistive heaters on
**low-voltage** buses. The costed DSO link is the HV (AC) → LV connection.

Chosen billing volume for the Excel (G30/H30):

    DSO delivered TWh = snapshot-weighted sum of max(−p1, 0) on costed DSO links

That is energy that crossed the DSO asset (HV→LV). It is the quantity that
matches "electricity distributed through the DSO grid".

It is **not** total generation. It does **not** apply Excel's 80% DSO share
(industry is already behind the DSO link in PyPSA). Rooftop PV serving local
load does not cross the link and is excluded.

### Sanity check vs the old 3,175 / 4,082 TWh

Those figures were `LV loads + resistive heaters + BEV chargers − LV shedding`.
Heat-pump electricity was **omitted** (the old script took `−p1` on bus1=LV, but
heat pumps have `p1 > 0`). Independently:

| | 2030 Build | 2040 Build |
|---|---:|---:|
| Old incomplete LV demand | ~3,175 TWh | ~4,082 TWh |
| Heat-pump electricity (p1>0) | ~631 TWh | computed in CSV |
| DSO HV→LV (this study) | ~3,082 TWh | ~3,927 TWh |
| Rooftop generation | ~722 TWh | ~1,026 TWh |

DSO flow + rooftop ≈ LV demand including heat pumps. That closes the energy
balance and is why the DSO volume is below 3,175+HP.

## What is written into Excel

See sheet `Mapping` in the copied workbook. Formulas for RAB, depreciation,
OPEX and allowable revenue are **not** overwritten. Build CAPEX is the original
Excel trajectory. Constrained sheets only scale 2026–2040 CAPEX by the PyPSA
overnight ratio. 2030/2040 TWh DSO are PyPSA HV→LV volumes.

Direct tariff added in G35/H35:

    EUR/MWh = allowable revenue (bn EUR) × 1000 / TWh DSO

## Why the old PyPSA proxy is smaller

Old proxy ≈ annualised *modelled* DSO stock / LV kWh ≈ 9.7–11 EUR/MWh.
It only recovers the HV–LV overlay that PyPSA represents (~31–45 bn €/yr
annualised), not the 700 bn existing RAB, not Excel OPEX, not 5.4% WACC on
the full RAB.

The regulatory tariff recovers `RAB×WACC + depreciation + OPEX` on the Excel
RAB, with inaction represented as a *fraction* of the Excel CAPEX path.

## Needs confirmation

1. **2041+ CAPEX** left at original 60 bn/yr for every scenario.
2. **Sheet1 depreciation freeze** after 2030 was kept.
3. **Excel 80% DSO share** is *not* applied to PyPSA volumes (industry is on LV).
4. Geography: PyPSA is EU27+UK+NO+CH; Excel says "Europe".
5. Build vs Original Excel now differ only in the TWh denominator (PyPSA HV→LV
   vs Excel consumption×0.8), not in CAPEX.
