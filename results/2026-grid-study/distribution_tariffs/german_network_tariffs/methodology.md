# German network tariffs: Excel finance + PyPSA physics

## Rule

The original workbook (`german_network_tariff_model_v3.xlsx`) is not modified.
This copy keeps every original sheet. PyPSA absolute grid CAPEX is never used
as German investment.

Excel supplies the realistic financial/regulatory baseline:
opening RAB 186 bn € (2023), WACC 5.04% then 5.50%, depreciation 3%/yr of
opening RAB, OPEX 15→27 bn € (scenario-independent), Inv_base from IMK
(Scenario B).

PyPSA supplies endogenous *German* physical ratios only.

## Excel identities (inspected)

    Tariff_t = (WACC_t × RAB_t + Dep_t + OPEX_t) / Demand_t
    RAB_{t+1} = RAB_t + Inv_t − Dep_t
    Dep_t = 0.03 × opening RAB_t
    Inv_s(t) = Inv_B(t) × Demand_s(t) / Demand_B(t)   # original NEP A/C method

Original Excel A/B/C are NEP 2037/2045 Version 2025 *demand* scenarios
(967 / 1,179 / 1,351 TWh Brutto in 2045). They are not grid-cap scenarios.

Documented TSO/DSO split of the 34 bn peak year: ÜNB 19.8 + VNB 14.4.
Shares used here are 19.8/34.2 and 14.4/34.2.

Band allocation (IG 0.22 … IC 1.30) is a multiplier on the *same* system
average. It is not a voltage-specific cost pool. PyPSA cannot assign
customers to HöS vs NS: industry electricity sits on LV.

## PyPSA geography and assets

Germany = 3 AC nodes (DE2 0/1/2) in the 37-cluster networks.
Costed DSO = carrier 'electricity distribution grid' AND capital_cost > 0.
Reverse twins and data-centre site links are excluded.

The 85/75/65/50% names are a *Europe-wide* cap on new DSO annualised
investment. They are not German capacity findings. German realised DSO
stock vs Build is endogenous (2030: 94.4 / 91.0 / 79.8 / 59.8%;
2040: 83.7 / 75.4 / 65.3 / 52.7%). Peak HV→LV ratios match stock ratios
because utilisation is 97% in every run (DSO is sized to peak).

The DSO-budget dual is not stored in the solved .nc files. The EU cap is
binding (slack ≈ 0) in every inaction run.

Cross-border AC/DC volume is allocated 50% to Germany.

## Denominator

Excel recovers TSO+DSO from total German kWh. The matching PyPSA quantity
is German *end-use electricity*:
conventional LV + industry + agriculture + data centres + heat pumps
+ resistive heaters + BEV chargers.

Not used as the system-average denominator:
- HV→LV DSO flow (excludes rooftop self-consumption; Excel is TSO+DSO)
- Gross including electrolysis (50% 2040 PtX jumps to ~270 TWh and would
  inflate the billing base; NEP Brutto includes PtX, StromNEV bands do not)

## Cases

A  Excel method on PyPSA scenarios: Inv × (end-use_s / end-use_Build).
B  Excel B investment unchanged; only the denominator is PyPSA end-use.
C  All Inv_base × German DSO stock ratio. Over-scales TSO. Not recommended.
D  All Inv_base × German peak HV→LV ratio. Empirically identical to C.
E  Recommended. VNB share × peak DSO; ÜNB share × TSO *stock* GW-km.
   Historical 2023–2025 unscaled.

Sensitivities on the E sheet set: TSO left at NEP (E_dso_only_tso_nep);
TSO scaled by *new* GW-km (E_tso_new_volume; 50% 2030 new TSO is ~7% of
Build and is not a realistic replacement programme).

## What is exogenous vs endogenous

Exogenous: EU DSO budget labels, Excel RAB/WACC/OPEX/Inv_base, OPEX
invariance, band weights, conventional/industry/agri/data-centre TWh.

Endogenous: German realised DSO capacity and peak flow; German TSO
expansion (it *falls* with the DSO cap, it does not substitute);
HP/RH/BEV; rooftop (hits the German cap from 65% 2030); shedding
(50% 2030 only, ~20 TWh LV); electrolysis; Germany's rising share of
the scarce EU DSO pie (16% → ~19–21%).

## Publication recommendation

Use Case E. Peak is the right physical driver for DSO investment; in
these solves it equals capacity. Do not present 85/75/65/50% as German
DSO findings. Do not put PyPSA euros into the German RAB.
