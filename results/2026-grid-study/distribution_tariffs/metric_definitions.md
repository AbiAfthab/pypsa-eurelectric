# Grid-study metric definitions

## What is in the PyPSA objective

`n.objective` is the whole sector-coupled annualised cost (power, heat, H2,
industry, fuels, CO2, VOLL). For these runs it is about 660–700 bn €/yr.
The EC does **not** publish a matching supply-system subtotal. The S2
€2,472 bn/yr figure is energy-service / end-user expenditure (buildings,
end-use equipment, transport, energy purchases) and must not be compared
to `n.objective`. Do not subtract residential + transport from that total:
energy purchases already embed upstream costs.

## Network tariff proxies

A network tariff is TSO+DSO by definition.

- **DSO revenue** = Σ p_nom × capital_cost on `electricity distribution grid` links
  (sunk + new). This is the quantity the inaction cap binds on (new only).
- **TSO revenue** = AC lines (s_nom × capital_cost) + DC links (p_nom × capital_cost).
  Transmission stays extendable in every scenario (`v1.5` volume cap, not a € cap).
- **Network tariff** = (TSO + DSO revenue) / served electrified LV demand.
- **DSO tariff** = DSO revenue / the same billing base.

These are annualised cost-recovery proxies, not a regulated RAB, and they
omit most real LV/MV RAB, metering and taxes. They will sit well below a
~60 €/MWh 2025 household network charge. Use them for *direction and ratios*,
not as a predicted retail network tariff.

## EC Table 20 — electricity production cost

PyPSA extract (grids excluded):

    C_power = C_generators + C_storage + C_thermal_plants + C_VOM + C_fuel
    €/MWh   = C_power / electricity generation

Generation is electricity produced (VRE, nuclear, hydro reservoirs, thermal
links), not grid throughput and not battery/PHS cycling. Load-shedding VOLL
is excluded. CHP plants are included at full plant capex with only their
electricity output in the denominator (a known overstatement of €/MWh).

PyPSA folds FOM into `capital_cost`. The CSV also reports an estimated
capital/FOM split (7% WACC) so it can be lined up against the EC S2 2040
mix of ~51% capital / 33% O&M / 16% fuel on €96/MWh.

EC 2040 average electricity production cost: S1 €97, S2 €96, S3 €94 /MWh.

## EC Table 16 — investment (cash, not system cost)

S2 2031–2040 (bn €2023/yr): power grid 88, power plants 128, other supply 72.

PyPSA comparison uses **new overnight CAPEX this horizon**, reversed from
annualised capex via annuity(lifetime, 7%) + FOM, then divided by 10 years.
That is comparable in *kind* to Table 16. It is not `n.objective`.

Caveats: aggregated DSO (no full LV/MV replacement programme), geography
is EU27+UK+NO+CH, cost year may differ from €2023, myopic 2030 is catch-up
from today while 2040 additions are the closer analogue to 2031–2040.
