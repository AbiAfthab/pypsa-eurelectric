# SPDX-FileCopyrightText: Contributors to PyPSA-Eurelectric
#
# SPDX-License-Identifier: MIT
"""
Post-process solved grid-study networks into tariff proxies and EC benchmarks.

The headline Grids for Speed claim this script is built to test:

    Network tariffs remain on a similar level because electrification
    grows the billing base (kWh) in line with grid investment.

PyPSA has no regulatory tariff module. Two revenue-requirement proxies:

    dso_tariff     = DSO allowed revenue / electrified LV demand
    network_tariff = (TSO + DSO) allowed revenue / electrified LV demand

where TSO is AC lines + DC links, DSO is "electricity distribution grid"
links, and allowed revenue is sum(optimised capacity × capital_cost) over
sunk brownfield plus newly built assets. By definition a network tariff is
TSO+DSO; the DSO-only series is kept because the inaction cap is DSO-only.

The default billing base is electrified LV demand: electricity loads on
low-voltage buses plus electricity used by heat pumps, resistive heaters
and BEV chargers.

EC comparisons (not vs n.objective):

    Table 20 — electricity *production* cost €/MWh (no TSO/DSO).
    Table 16 — new overnight cash investment (grid / plants / other),
               compared as decade-average €bn/yr, not annualised system cost.

The whole-sector PyPSA objective (~660–700 bn €/yr) is retained as this
model's own total. It has no published EC supply-system equivalent. Do not
subtract EC end-use "energy purchases" from the €2.47 tn S2 figure.

Usage (from the repo root, pixi env):

    python scripts/eurelectric/summarise_distribution_tariffs.py

    python scripts/eurelectric/summarise_distribution_tariffs.py \\
        --results-root results/2026-grid-study \\
        --output results/2026-grid-study/distribution_tariffs
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pypsa

logger = logging.getLogger(__name__)

VOLL_EUR_PER_MWH = 10_000.0
SCENARIO_ORDER = ["Build", "85%", "75%", "65%", "50%"]
MILD_SCENARIOS = ["Build", "85%", "75%", "65%"]

# WACC used in technology-data / process_cost_data (costs fill_values).
DEFAULT_DISCOUNT_RATE = 0.07
# Table 16 figures are annual cash needs over a decade.
INVESTMENT_DECADE_YEARS = 10.0
DEFAULT_LIFETIME_YEARS = 25.0
GRID_LIFETIME_YEARS = 40.0
DEFAULT_FOM_PERCENT = 1.5
GRID_FOM_PERCENT = 2.0

# EC Impact Assessment S2, 2040 / 2031–2040. Production cost is €/MWh.
# Table 16 is bn €2023/yr *cash investment*, not annualised system cost.
EC_TABLE20_EUR_PER_MWH = {"S1": 97.0, "S2": 96.0, "S3": 94.0}
EC_TABLE20_S2_SHARE = {"capital": 0.51, "om": 0.33, "fuel": 0.16}
EC_TABLE16_S2_2031_2040_BN_PER_YR = {
    "grid": 88.0,
    "plants": 128.0,
    "other": 72.0,
}

ELEC_BUS_CARRIERS = frozenset({"AC", "low voltage"})
FOSSIL_COMMODITY_CARRIERS = frozenset(
    {"gas", "oil primary", "coal", "lignite"}
)
# Commodity buses whose withdrawal by power links is a fuel cost.
POWER_FUEL_BUS_CARRIERS = frozenset(
    {"gas", "solid biomass", "coal", "lignite", "oil", "oil primary", "uranium"}
)
POWER_LINK_CARRIER_RE = re.compile(
    r"(OCGT|CCGT|nuclear|^coal$|^lignite$|^oil$|CHP|H2 turbine|H2 Fuel Cell)",
    re.IGNORECASE,
)

# Distinct run.name folders used by the grid-study overlays.
RUN_META: dict[str, dict] = {
    "grid-build-2040": {
        "label": "Build",
        "cap_fraction": 1.00,
    },
    "grid-inaction-2040-mild85": {
        "label": "85%",
        "cap_fraction": 0.85,
    },
    "grid-inaction-2040-mild75": {
        "label": "75%",
        "cap_fraction": 0.75,
    },
    "grid-inaction-2040-mild65": {
        "label": "65%",
        "cap_fraction": 0.65,
    },
    "grid-inaction-2040-moderate": {
        "label": "50%",
        "cap_fraction": 0.50,
    },
}


def _weights(n: pypsa.Network) -> pd.Series:
    return n.snapshot_weightings.generators


def _weighted_sum(df: pd.DataFrame, weights: pd.Series) -> float:
    if df.empty:
        return 0.0
    return float(df.multiply(weights, axis=0).sum().sum())


def distribution_grid_links(n: pypsa.Network) -> pd.Index:
    return n.links.index[n.links.carrier == "electricity distribution grid"]


def _distribution_capacity_mw(
    n: pypsa.Network, extendable_only: bool = False
) -> pd.Series:
    """Optimised MW for extendable links, fixed ``p_nom`` for sunk brownfield."""
    dg = n.links.loc[distribution_grid_links(n)].copy()
    if extendable_only:
        dg = dg[dg.p_nom_extendable]
    if dg.empty:
        return pd.Series(dtype=float)

    capacity = dg["p_nom"].copy()
    extendable = dg["p_nom_extendable"].fillna(False)
    if "p_nom_opt" in dg.columns:
        capacity.loc[extendable] = dg.loc[extendable, "p_nom_opt"].fillna(
            dg.loc[extendable, "p_nom"]
        )
    return capacity


def allowed_revenue_eur(n: pypsa.Network, extendable_only: bool = False) -> float:
    """Modelled annual distribution-grid revenue requirement (EUR/yr).

    Uses optimised capacity for extendable links and fixed ``p_nom`` for sunk
    brownfield links. This is a network-cost proxy, not a full regulated RAB /
    allowed-revenue calculation.
    """
    capacity = _distribution_capacity_mw(n, extendable_only=extendable_only)
    if capacity.empty:
        return 0.0
    capital_cost = n.links.loc[capacity.index, "capital_cost"]
    return float((capacity * capital_cost).sum())


def distribution_capacity_gw(n: pypsa.Network) -> float:
    capacity = _distribution_capacity_mw(n)
    if capacity.empty:
        return 0.0
    return float(capacity.sum()) / 1e3


def _optimised_capacity(df: pd.DataFrame, nom: str, opt: str) -> pd.Series:
    """Optimised MW for extendable assets, installed MW otherwise."""
    capacity = df[nom].copy()
    if "p_nom_extendable" in df.columns:
        extendable = df["p_nom_extendable"].fillna(False)
    elif "s_nom_extendable" in df.columns:
        extendable = df["s_nom_extendable"].fillna(False)
    else:
        extendable = pd.Series(True, index=df.index)
    if opt in df.columns:
        capacity.loc[extendable] = df.loc[extendable, opt].fillna(df.loc[extendable, nom])
    return capacity


def tso_ac_revenue_eur(n: pypsa.Network, extendable_only: bool = False) -> float:
    """Annualised AC transmission (TSO) revenue-requirement proxy (EUR/yr)."""
    if n.lines.empty:
        return 0.0
    lines = n.lines
    if extendable_only:
        lines = lines[lines.s_nom_extendable.fillna(False)]
    if lines.empty:
        return 0.0
    capacity = _optimised_capacity(lines, "s_nom", "s_nom_opt")
    return float((capacity * lines.loc[capacity.index, "capital_cost"]).sum())


def tso_dc_revenue_eur(n: pypsa.Network, extendable_only: bool = False) -> float:
    """Annualised HVDC (TSO) revenue-requirement proxy (EUR/yr)."""
    dc = n.links.loc[n.links.carrier == "DC"]
    if extendable_only:
        dc = dc[dc.p_nom_extendable.fillna(False)]
    if dc.empty:
        return 0.0
    capacity = _optimised_capacity(dc, "p_nom", "p_nom_opt")
    return float((capacity * dc.loc[capacity.index, "capital_cost"]).sum())


def tso_revenue_eur(n: pypsa.Network, extendable_only: bool = False) -> float:
    return tso_ac_revenue_eur(n, extendable_only) + tso_dc_revenue_eur(
        n, extendable_only
    )


def network_revenue_eur(n: pypsa.Network, extendable_only: bool = False) -> float:
    """TSO + DSO annualised revenue-requirement proxy (EUR/yr)."""
    return tso_revenue_eur(n, extendable_only) + allowed_revenue_eur(
        n, extendable_only
    )


def _annuity(lifetime: pd.Series | np.ndarray | float, rate: float) -> pd.Series:
    """Capital-recovery factor; inf/non-positive lifetime → NaN."""
    n = pd.Series(lifetime, dtype=float).replace([np.inf, -np.inf], np.nan)
    out = pd.Series(np.nan, index=n.index, dtype=float)
    valid = n.notna() & (n > 0)
    if rate > 0:
        out.loc[valid] = rate / (1.0 - 1.0 / (1.0 + rate) ** n.loc[valid])
    else:
        out.loc[valid] = 1.0 / n.loc[valid]
    return out


def _lifetime_with_fallback(df: pd.DataFrame, default: float) -> pd.Series:
    life = pd.to_numeric(df["lifetime"], errors="coerce") if "lifetime" in df.columns else pd.Series(np.nan, index=df.index)
    life = life.replace([np.inf, -np.inf], np.nan)
    return life.fillna(default)


def _expanded_mw(df: pd.DataFrame, nom: str, opt: str) -> pd.Series:
    """New capacity this horizon (optimised minus installed)."""
    installed = df[nom]
    if opt not in df.columns:
        return pd.Series(0.0, index=df.index)
    return (df[opt].fillna(installed) - installed).clip(lower=0.0)


def _annualised_and_overnight(
    df: pd.DataFrame,
    nom: str,
    opt: str,
    default_lifetime: float,
    fom_percent: float,
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
) -> tuple[pd.Series, pd.Series]:
    """New-build annualised capex and implied overnight CAPEX (EUR).

    PyPSA ``capital_cost`` is ``(annuity + FOM/100) × overnight``. Component
    ``overnight_cost`` / ``discount_rate`` are empty here, so overnight is
    reversed with the technology-data WACC and a lifetime fallback (grid 40
    years, other 25) when ``lifetime`` is inf.
    """
    added = _expanded_mw(df, nom, opt)
    annualised = added * df["capital_cost"].fillna(0.0)
    life = _lifetime_with_fallback(df, default_lifetime)
    crf = _annuity(life, discount_rate) + fom_percent / 100.0
    overnight = annualised / crf.replace(0.0, np.nan)
    return annualised.fillna(0.0), overnight.fillna(0.0)


def _commodity_prices(n: pypsa.Network) -> dict[str, float]:
    prices: dict[str, float] = {}
    if n.generators.empty:
        return prices
    for carrier, grp in n.generators.groupby(n.generators.carrier):
        prices[str(carrier)] = float(grp.marginal_cost.median())
    if "oil primary" in prices and "oil" not in prices:
        prices["oil"] = prices["oil primary"]
    return prices


def _is_power_link(carrier: object) -> bool:
    return bool(POWER_LINK_CARRIER_RE.search(str(carrier)))


def electricity_generators(n: pypsa.Network) -> pd.Index:
    bus_carrier = n.generators.bus.map(n.buses.carrier)
    loadlike = n.generators.carrier.str.contains("load", case=False, na=False)
    return n.generators.index[bus_carrier.isin(ELEC_BUS_CARRIERS) & ~loadlike]


def power_producing_links(n: pypsa.Network) -> pd.Index:
    return n.links.index[n.links.carrier.map(_is_power_link).fillna(False)]


def _weighted_dispatch(df_t: pd.DataFrame, weights: pd.Series, columns: pd.Index) -> float:
    if columns.empty or df_t.empty:
        return 0.0
    p = df_t.reindex(columns=columns, fill_value=0.0).clip(lower=0.0)
    return _weighted_sum(p, weights)


def electricity_generation_mwh(n: pypsa.Network) -> dict[str, float]:
    """Electricity *production* (MWh), excluding grid throughput and storage cycling.

    Hydro reservoirs are counted as generation (inflow-driven). Batteries and
    PHS discharge are cycling, not primary production, so they are omitted
    from the denominator (their capex still sits in production cost).
    """
    w = _weights(n)
    gens = electricity_generators(n)
    gen_mwh = _weighted_dispatch(n.generators_t.p, w, gens)

    hydro = n.storage_units.index[n.storage_units.carrier.eq("hydro")]
    hydro_mwh = _weighted_dispatch(n.storage_units_t.p, w, hydro)

    thermal = power_producing_links(n)
    if thermal.empty or n.links_t.p1.empty:
        thermal_mwh = 0.0
    else:
        injected = (-n.links_t.p1.reindex(columns=thermal, fill_value=0.0)).clip(
            lower=0.0
        )
        thermal_mwh = _weighted_sum(injected, w)

    return {
        "generators": gen_mwh,
        "hydro": hydro_mwh,
        "thermal_links": thermal_mwh,
        "total": gen_mwh + hydro_mwh + thermal_mwh,
    }


def _asset_annualised_capex(df: pd.DataFrame, nom: str, opt: str) -> float:
    if df.empty:
        return 0.0
    capacity = _optimised_capacity(df, nom, opt)
    return float((capacity * df.loc[capacity.index, "capital_cost"]).sum())


def _asset_opex_eur(df: pd.DataFrame, df_t: pd.DataFrame, weights: pd.Series) -> float:
    """Variable O&M / fuel sitting on the component as marginal_cost × dispatch."""
    if df.empty or df_t.empty or "marginal_cost" not in df.columns:
        return 0.0
    cols = df.index.intersection(df_t.columns)
    if cols.empty:
        return 0.0
    energy = df_t.reindex(columns=cols, fill_value=0.0).clip(lower=0.0).mul(
        weights, axis=0
    ).sum()
    return float((energy * df.loc[cols, "marginal_cost"].fillna(0.0)).sum())


def _power_link_fuel_eur(n: pypsa.Network) -> float:
    """Commodity cost of fuels withdrawn by electricity-producing thermal links.

    H2 / methanol produced inside the model are excluded (that energy is
    already paid for as electricity or synthesis capex). Uranium has no
    commodity generator here; nuclear fuel sits on the nuclear *generator*
    marginal cost instead.
    """
    names = power_producing_links(n)
    if names.empty or n.links_t.p0.empty:
        return 0.0
    prices = _commodity_prices(n)
    w = _weights(n)
    total = 0.0
    bus0_carrier = n.links.loc[names, "bus0"].map(n.buses.carrier)
    for name in names:
        carrier = bus0_carrier.at[name]
        if carrier not in POWER_FUEL_BUS_CARRIERS:
            continue
        price = prices.get(str(carrier), 0.0)
        if not price:
            continue
        if name not in n.links_t.p0.columns:
            continue
        energy = float(n.links_t.p0[name].clip(lower=0.0).mul(w).sum())
        total += energy * price
    return total


def _split_fom(
    annualised: float, lifetime: float, fom_percent: float
) -> tuple[float, float]:
    """Split annualised capex into pure capital recovery vs FOM."""
    if annualised <= 0:
        return 0.0, 0.0
    life = lifetime if np.isfinite(lifetime) and lifetime > 0 else DEFAULT_LIFETIME_YEARS
    crf = float(_annuity(pd.Series([life]), DEFAULT_DISCOUNT_RATE).iloc[0])
    denom = crf + fom_percent / 100.0
    if denom <= 0:
        return annualised, 0.0
    fom = annualised * (fom_percent / 100.0) / denom
    return annualised - fom, fom


def electricity_production_cost(n: pypsa.Network) -> dict[str, float]:
    """Table-20-style electricity production cost (no TSO/DSO).

    C_power = generator + storage + thermal-plant capex + VOM + fuel
    divided by electricity generation. Load-shedding VOLL is excluded.
    PyPSA folds FOM into ``capital_cost``; we also report an estimated
    capital/FOM split so the EC 51/33/16 breakdown is comparable.
    """
    w = _weights(n)
    gens = n.generators.loc[electricity_generators(n)]
    storage = n.storage_units
    plants = n.links.loc[power_producing_links(n)]

    capex_g = _asset_annualised_capex(gens, "p_nom", "p_nom_opt")
    capex_su = _asset_annualised_capex(storage, "p_nom", "p_nom_opt")
    capex_th = _asset_annualised_capex(plants, "p_nom", "p_nom_opt")

    opex_g = _asset_opex_eur(gens, n.generators_t.p, w)
    opex_su = _asset_opex_eur(storage, n.storage_units_t.p, w)
    opex_th = _asset_opex_eur(plants, n.links_t.p0, w)
    fuel_th = _power_link_fuel_eur(n)

    generation = electricity_generation_mwh(n)
    g_mwh = generation["total"]

    capex = capex_g + capex_su + capex_th
    vom = opex_g + opex_su + opex_th
    # Nuclear/VRE "opex" is mostly fuel+VOM already on generators; thermal
    # commodity fuel is additional.
    fuel = fuel_th
    total = capex + vom + fuel

    # FOM estimate using grid-style 1.5% for plants (not the DSO 2%).
    plant_life = DEFAULT_LIFETIME_YEARS
    if not gens.empty:
        plant_life = float(_lifetime_with_fallback(gens, DEFAULT_LIFETIME_YEARS).median())
    capital_only, fom = _split_fom(capex, plant_life, DEFAULT_FOM_PERCENT)

    def per_mwh(value: float) -> float:
        return value / g_mwh if g_mwh > 0 else float("nan")

    return {
        "elec_generation_twh": g_mwh / 1e6,
        "elec_generation_generators_twh": generation["generators"] / 1e6,
        "elec_generation_hydro_twh": generation["hydro"] / 1e6,
        "elec_generation_thermal_twh": generation["thermal_links"] / 1e6,
        "elec_capex_bn_eur_per_yr": capex / 1e9,
        "elec_capex_generators_bn": capex_g / 1e9,
        "elec_capex_storage_bn": capex_su / 1e9,
        "elec_capex_thermal_links_bn": capex_th / 1e9,
        "elec_vom_bn_eur_per_yr": vom / 1e9,
        "elec_fuel_bn_eur_per_yr": fuel / 1e9,
        "elec_production_cost_bn_eur_per_yr": total / 1e9,
        "elec_production_cost_eur_per_mwh": per_mwh(total),
        "elec_capex_eur_per_mwh": per_mwh(capex),
        "elec_vom_eur_per_mwh": per_mwh(vom),
        "elec_fuel_eur_per_mwh": per_mwh(fuel),
        "elec_capital_only_eur_per_mwh": per_mwh(capital_only),
        "elec_fom_in_capex_eur_per_mwh": per_mwh(fom),
        "elec_om_plus_fom_eur_per_mwh": per_mwh(vom + fom),
        "ec_table20_s2_eur_per_mwh": EC_TABLE20_EUR_PER_MWH["S2"],
        "elec_production_cost_vs_ec_s2_eur_per_mwh": (
            per_mwh(total) - EC_TABLE20_EUR_PER_MWH["S2"]
        ),
    }


def _link_investment_bucket(carrier: object) -> str:
    name = str(carrier)
    lowered = name.lower()
    if name in {"DC", "electricity distribution grid"}:
        return "grid"
    if _is_power_link(name):
        return "plants"
    if any(
        token in lowered
        for token in (
            "bev",
            "v2g",
            "dsr",
            "land transport",
            "shipping",
            "aviation",
            "agriculture machinery",
        )
    ):
        return "excluded_enduse"
    if "battery" in lowered:
        return "plants"
    return "other"


def _store_investment_bucket(carrier: object) -> str:
    lowered = str(carrier).lower()
    if "battery" in lowered:
        return "plants"
    if any(token in lowered for token in ("dsr", "ev battery")):
        return "excluded_enduse"
    if lowered in {"co2", "co2 stored"}:
        return "excluded_accounting"
    return "other"


def _generator_investment_bucket(n: pypsa.Network, idx: pd.Index) -> pd.Series:
    bus_carrier = n.generators.loc[idx, "bus"].map(n.buses.carrier)
    loadlike = n.generators.loc[idx, "carrier"].str.contains("load", case=False, na=False)
    bucket = pd.Series("other", index=idx)
    bucket.loc[bus_carrier.isin(ELEC_BUS_CARRIERS)] = "plants"
    bucket.loc[loadlike] = "excluded_enduse"
    return bucket


def new_investment_vs_table16(n: pypsa.Network) -> dict[str, float]:
    """New-build investment this horizon vs EC Table 16 (cash, not objective).

    Returns annualised new capex (model-native) and overnight CAPEX reversed
    from annuity+FOM. Table 16 comparison uses overnight / 10 years.
    """
    annual = {"grid": 0.0, "plants": 0.0, "other": 0.0, "excluded": 0.0}
    overnight = {"grid": 0.0, "plants": 0.0, "other": 0.0, "excluded": 0.0}

    def add(bucket: str, ann: pd.Series, ovn: pd.Series) -> None:
        key = bucket if bucket in annual else "excluded"
        annual[key] += float(ann.sum())
        overnight[key] += float(ovn.sum())

    if not n.lines.empty:
        ann, ovn = _annualised_and_overnight(
            n.lines, "s_nom", "s_nom_opt", GRID_LIFETIME_YEARS, GRID_FOM_PERCENT
        )
        add("grid", ann, ovn)

    if not n.links.empty:
        for carrier, grp in n.links.groupby(n.links.carrier):
            default_life = (
                GRID_LIFETIME_YEARS
                if str(carrier) in {"DC", "electricity distribution grid"}
                else DEFAULT_LIFETIME_YEARS
            )
            fom = (
                GRID_FOM_PERCENT
                if str(carrier) in {"DC", "electricity distribution grid"}
                else DEFAULT_FOM_PERCENT
            )
            ann, ovn = _annualised_and_overnight(
                grp, "p_nom", "p_nom_opt", default_life, fom
            )
            add(_link_investment_bucket(carrier), ann, ovn)

    if not n.generators.empty:
        buckets = _generator_investment_bucket(n, n.generators.index)
        for bucket, idx in buckets.groupby(buckets):
            grp = n.generators.loc[idx.index]
            ann, ovn = _annualised_and_overnight(
                grp, "p_nom", "p_nom_opt", DEFAULT_LIFETIME_YEARS, DEFAULT_FOM_PERCENT
            )
            add(str(bucket), ann, ovn)

    if not n.storage_units.empty:
        ann, ovn = _annualised_and_overnight(
            n.storage_units,
            "p_nom",
            "p_nom_opt",
            DEFAULT_LIFETIME_YEARS,
            DEFAULT_FOM_PERCENT,
        )
        add("plants", ann, ovn)

    if not n.stores.empty:
        for carrier, grp in n.stores.groupby(n.stores.carrier):
            e_nom = "e_nom" if "e_nom" in grp.columns else "p_nom"
            e_opt = "e_nom_opt" if "e_nom_opt" in grp.columns else "p_nom_opt"
            if e_nom not in grp.columns:
                continue
            ann, ovn = _annualised_and_overnight(
                grp, e_nom, e_opt, DEFAULT_LIFETIME_YEARS, DEFAULT_FOM_PERCENT
            )
            add(_store_investment_bucket(carrier), ann, ovn)

    decade = INVESTMENT_DECADE_YEARS
    ec = EC_TABLE16_S2_2031_2040_BN_PER_YR
    out: dict[str, float] = {}
    for bucket in ("grid", "plants", "other"):
        out[f"new_{bucket}_annualised_bn_eur_per_yr"] = annual[bucket] / 1e9
        out[f"new_{bucket}_overnight_bn_eur"] = overnight[bucket] / 1e9
        out[f"new_{bucket}_overnight_bn_per_yr_over_decade"] = (
            overnight[bucket] / 1e9 / decade
        )
        out[f"ec_table16_s2_{bucket}_bn_per_yr"] = ec[bucket]
    out["new_excluded_annualised_bn_eur_per_yr"] = annual["excluded"] / 1e9
    out["new_supply_overnight_bn_per_yr_over_decade"] = (
        (overnight["grid"] + overnight["plants"] + overnight["other"]) / 1e9 / decade
    )
    out["ec_table16_s2_supply_bn_per_yr"] = sum(ec.values())
    return out


def fossil_fuel_expenditure_bn(n: pypsa.Network) -> float:
    """Whole-system fossil commodity spend (bn €/yr). Partial vs an import bill."""
    if n.generators.empty or n.generators_t.p.empty:
        return 0.0
    names = n.generators.index[n.generators.carrier.isin(FOSSIL_COMMODITY_CARRIERS)]
    if names.empty:
        return 0.0
    energy = (
        n.generators_t.p.reindex(columns=names, fill_value=0.0)
        .clip(lower=0.0)
        .mul(_weights(n), axis=0)
        .sum()
    )
    return float((energy * n.generators.loc[names, "marginal_cost"].fillna(0.0)).sum()) / 1e9


METRIC_DEFINITIONS = """# Grid-study metric definitions

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
"""


def energy_delivered_to_lv_mwh(n: pypsa.Network) -> float:
    """Energy arriving at LV buses through the distribution links (MWh).

    PyPSA: p1 > 0 means power leaving bus1 (LV) into the link (backfeed);
    p1 < 0 means power entering LV. Delivered energy is -min(p1, 0).
    """
    names = distribution_grid_links(n)
    if names.empty or n.links_t.p1.empty:
        return 0.0
    p1 = n.links_t.p1.reindex(columns=names, fill_value=0.0)
    delivered = (-p1).clip(lower=0.0)
    return _weighted_sum(delivered, _weights(n))


def peak_delivery_mw(n: pypsa.Network) -> float:
    """Peak instantaneous delivery HV→LV (MW)."""
    names = distribution_grid_links(n)
    if names.empty or n.links_t.p1.empty:
        return 0.0
    p1 = n.links_t.p1.reindex(columns=names, fill_value=0.0)
    delivered = (-p1).clip(lower=0.0)
    return float(delivered.sum(axis=1).max())


def lv_electric_load_mwh(n: pypsa.Network) -> float:
    """Conventional electricity demand on low-voltage buses (MWh)."""
    lv_buses = n.buses.index[n.buses.carrier == "low voltage"]
    loads = n.loads.index[n.loads.bus.isin(lv_buses)]
    if loads.empty:
        return 0.0
    if not n.loads_t.p.empty:
        p = n.loads_t.p.reindex(columns=loads, fill_value=0.0)
    else:
        p = n.loads_t.p_set.reindex(columns=loads, fill_value=0.0)
    return _weighted_sum(p, _weights(n))


def _electricity_used_by_links(n: pypsa.Network, mask: pd.Series) -> float:
    """Electricity withdrawn from the LV (or AC) bus by a set of links (MWh).

    Uses the bus that sits on an electricity carrier. Positive power at that
    bus is a withdrawal from the electricity bus into the link.
    """
    names = n.links.index[mask]
    if names.empty:
        return 0.0
    elec_carriers = {"AC", "low voltage"}
    bus0_elec = n.links.loc[names, "bus0"].map(n.buses.carrier).isin(elec_carriers)
    w = _weights(n)
    total = 0.0
    if bus0_elec.any() and not n.links_t.p0.empty:
        p0 = n.links_t.p0.reindex(columns=names[bus0_elec], fill_value=0.0)
        total += _weighted_sum(p0.clip(lower=0.0), w)
    bus1_elec = n.links.loc[names, "bus1"].map(n.buses.carrier).isin(elec_carriers)
    if bus1_elec.any() and not n.links_t.p1.empty:
        p1 = n.links_t.p1.reindex(columns=names[bus1_elec], fill_value=0.0)
        # Heat pumps: bus1 is LV; electricity input is -p1 when p1 is negative
        # (p0 is on the heat bus). Take the withdrawal magnitude.
        total += _weighted_sum((-p1).clip(lower=0.0), w)
    return total


def heat_pump_electricity_mwh(n: pypsa.Network) -> float:
    return _electricity_used_by_links(
        n, n.links.carrier.str.contains("heat pump", na=False)
    )


def resistive_heater_electricity_mwh(n: pypsa.Network) -> float:
    return _electricity_used_by_links(
        n, n.links.carrier.str.contains("resistive heater", na=False)
    )


def bev_electricity_mwh(n: pypsa.Network) -> float:
    return _electricity_used_by_links(
        n, n.links.carrier.str.contains("BEV charger", na=False)
    )


def electrified_lv_demand_mwh(n: pypsa.Network) -> float:
    """Billing-base kWh that grows with electrification."""
    return (
        lv_electric_load_mwh(n)
        + heat_pump_electricity_mwh(n)
        + resistive_heater_electricity_mwh(n)
        + bev_electricity_mwh(n)
    )


def load_shedding_mwh(
    n: pypsa.Network,
    bus_carrier: str | None = None,
) -> float:
    """Load-shedding energy (MWh), optionally limited to one bus carrier.

    Filtering by bus carrier matters because load shedding is enabled for all
    carriers in the Eurelectric setup. For the tariff denominator we only want
    electricity not served on the low-voltage buses.
    """
    carrier_match = n.generators.carrier.str.contains("load", case=False, na=False)
    name_match = n.generators.index.to_series().str.contains(
        "load shedding", case=False, na=False
    ).to_numpy()
    mask = carrier_match | name_match

    if bus_carrier is not None:
        generator_bus_carrier = n.generators.bus.map(n.buses.carrier)
        mask &= generator_bus_carrier.eq(bus_carrier)

    gens = n.generators.index[mask]
    if gens.empty or n.generators_t.p.empty:
        return 0.0

    p = n.generators_t.p.reindex(columns=gens, fill_value=0.0)
    return _weighted_sum(p.clip(lower=0.0), _weights(n))


def summarise_network(n: pypsa.Network, run: str, year: int) -> dict:
    meta = RUN_META.get(run, {"label": run, "cap_fraction": float("nan")})
    dso_revenue = allowed_revenue_eur(n, extendable_only=False)
    dso_revenue_added = allowed_revenue_eur(n, extendable_only=True)
    tso_ac = tso_ac_revenue_eur(n, extendable_only=False)
    tso_dc = tso_dc_revenue_eur(n, extendable_only=False)
    tso_revenue = tso_ac + tso_dc
    tso_revenue_added = tso_revenue_eur(n, extendable_only=True)
    network_revenue = tso_revenue + dso_revenue
    e_delivered = energy_delivered_to_lv_mwh(n)
    e_lv_load = lv_electric_load_mwh(n)
    e_hp = heat_pump_electricity_mwh(n)
    e_rh = resistive_heater_electricity_mwh(n)
    e_bev = bev_electricity_mwh(n)

    # Gross billing base: all modelled electrified LV demand.
    e_billed_gross = e_lv_load + e_hp + e_rh + e_bev

    # Load shedding is a fictitious generator used to keep the optimisation
    # feasible. Subtract LV electricity shedding from the billing base so the
    # headline tariff is based on electricity actually served.
    shed_total = load_shedding_mwh(n)
    shed_lv = load_shedding_mwh(n, bus_carrier="low voltage")
    e_billed_served = max(e_billed_gross - shed_lv, 0.0)

    peak = peak_delivery_mw(n)

    def per_mwh(cost_eur: float, energy_mwh: float) -> float:
        if energy_mwh <= 0:
            return float("nan")
        return cost_eur / energy_mwh

    row = {
        "run": run,
        "scenario": meta["label"],
        "cap_fraction": meta["cap_fraction"],
        "year": int(year),
        "system_cost_bn_eur_per_yr": n.objective / 1e9,
        # DSO-only (the capped quantity). Kept as grid_revenue_* for compatibility.
        "grid_revenue_bn_eur_per_yr": dso_revenue / 1e9,
        "grid_revenue_added_bn_eur_per_yr": dso_revenue_added / 1e9,
        "dso_revenue_bn_eur_per_yr": dso_revenue / 1e9,
        "dso_revenue_added_bn_eur_per_yr": dso_revenue_added / 1e9,
        "tso_ac_revenue_bn_eur_per_yr": tso_ac / 1e9,
        "tso_dc_revenue_bn_eur_per_yr": tso_dc / 1e9,
        "tso_revenue_bn_eur_per_yr": tso_revenue / 1e9,
        "tso_revenue_added_bn_eur_per_yr": tso_revenue_added / 1e9,
        "network_revenue_bn_eur_per_yr": network_revenue / 1e9,
        "grid_capacity_gw": distribution_capacity_gw(n),
        "energy_delivered_lv_twh": e_delivered / 1e6,
        "lv_electric_load_twh": e_lv_load / 1e6,
        "heat_pump_electricity_twh": e_hp / 1e6,
        "resistive_heater_electricity_twh": e_rh / 1e6,
        "bev_electricity_twh": e_bev / 1e6,
        "electrified_lv_demand_gross_twh": e_billed_gross / 1e6,
        "electrified_lv_demand_twh": e_billed_served / 1e6,
        "lv_load_shedding_twh": shed_lv / 1e6,
        "load_shedding_twh": shed_total / 1e6,
        "load_shedding_cost_bn_eur_per_yr": (shed_total * VOLL_EUR_PER_MWH / 1e9),
        "peak_delivery_gw": peak / 1e3,
        # DSO-only tariff (legacy column name).
        "tariff_vs_electrified_demand_eur_per_mwh": per_mwh(
            dso_revenue, e_billed_served
        ),
        "dso_tariff_eur_per_mwh": per_mwh(dso_revenue, e_billed_served),
        "tso_tariff_eur_per_mwh": per_mwh(tso_revenue, e_billed_served),
        # Headline: TSO+DSO by definition of a network tariff.
        "network_tariff_eur_per_mwh": per_mwh(network_revenue, e_billed_served),
        "tariff_vs_gross_electrified_demand_eur_per_mwh": per_mwh(
            dso_revenue, e_billed_gross
        ),
        "network_tariff_vs_gross_demand_eur_per_mwh": per_mwh(
            network_revenue, e_billed_gross
        ),
        "tariff_vs_throughput_eur_per_mwh": per_mwh(dso_revenue, e_delivered),
        "tariff_vs_lv_load_eur_per_mwh": per_mwh(dso_revenue, e_lv_load),
        "capacity_tariff_eur_per_kw_yr": (
            dso_revenue / (peak * 1e3) if peak > 0 else float("nan")
        ),
        # Whole-system cost per served kWh: scenario index, not a retail price.
        "system_cost_eur_per_mwh_served": per_mwh(n.objective, e_billed_served),
        "non_grid_cost_bn_eur_per_yr": (n.objective - dso_revenue) / 1e9,
        "non_grid_cost_eur_per_mwh_served": per_mwh(
            n.objective - dso_revenue, e_billed_served
        ),
        "non_network_cost_bn_eur_per_yr": (n.objective - network_revenue) / 1e9,
        "non_network_cost_eur_per_mwh_served": per_mwh(
            n.objective - network_revenue, e_billed_served
        ),
        "fossil_fuel_expenditure_bn_eur_per_yr": fossil_fuel_expenditure_bn(n),
    }
    row.update(electricity_production_cost(n))
    row.update(new_investment_vs_table16(n))
    return row


def discover_networks(results_root: Path) -> list[tuple[str, int, Path]]:
    found: list[tuple[str, int, Path]] = []
    for run_dir in sorted(results_root.iterdir()):
        if not run_dir.is_dir():
            continue
        networks = run_dir / "networks"
        if not networks.is_dir():
            continue
        for nc in sorted(networks.glob("base_s_*_*.nc")):
            m = re.search(r"(\d{4})\.nc$", nc.name)
            if not m:
                continue
            found.append((run_dir.name, int(m.group(1)), nc))
    return found


def collect_table(results_root: Path) -> pd.DataFrame:
    rows = []
    for run, year, path in discover_networks(results_root):
        logger.info("Reading %s", path)
        n = pypsa.Network(str(path))
        rows.append(summarise_network(n, run, year))
    if not rows:
        raise FileNotFoundError(f"No solved networks under {results_root}")
    df = pd.DataFrame(rows)
    df = df.sort_values(["year", "cap_fraction"], ascending=[True, False]).reset_index(
        drop=True
    )
    return df


def add_build_relative_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add Build-relative metrics for each planning horizon."""
    out = df.copy()

    for year, grp in df.groupby("year"):
        build = grp[grp["scenario"] == "Build"]
        if build.empty:
            continue

        b = build.iloc[0]
        idx = out["year"] == year

        out.loc[idx, "tariff_index_build_100"] = (
            out.loc[idx, "tariff_vs_electrified_demand_eur_per_mwh"]
            / b["tariff_vs_electrified_demand_eur_per_mwh"]
            * 100.0
        )
        out.loc[idx, "network_tariff_index_build_100"] = (
            out.loc[idx, "network_tariff_eur_per_mwh"]
            / b["network_tariff_eur_per_mwh"]
            * 100.0
        )
        out.loc[idx, "network_revenue_index_build_100"] = (
            out.loc[idx, "network_revenue_bn_eur_per_yr"]
            / b["network_revenue_bn_eur_per_yr"]
            * 100.0
        )
        out.loc[idx, "electrified_demand_index_build_100"] = (
            out.loc[idx, "electrified_lv_demand_twh"]
            / b["electrified_lv_demand_twh"]
            * 100.0
        )
        out.loc[idx, "grid_revenue_index_build_100"] = (
            out.loc[idx, "grid_revenue_bn_eur_per_yr"]
            / b["grid_revenue_bn_eur_per_yr"]
            * 100.0
        )
        out.loc[idx, "delta_system_cost_vs_build_bn"] = (
            out.loc[idx, "system_cost_bn_eur_per_yr"] - b["system_cost_bn_eur_per_yr"]
        )
        out.loc[idx, "grid_revenue_withheld_vs_build_bn"] = (
            b["grid_revenue_bn_eur_per_yr"] - out.loc[idx, "grid_revenue_bn_eur_per_yr"]
        )
        out.loc[idx, "tariff_change_vs_build_eur_per_mwh"] = (
            out.loc[idx, "tariff_vs_electrified_demand_eur_per_mwh"]
            - b["tariff_vs_electrified_demand_eur_per_mwh"]
        )
        out.loc[idx, "tariff_saving_vs_build_eur_per_mwh"] = (
            b["tariff_vs_electrified_demand_eur_per_mwh"]
            - out.loc[idx, "tariff_vs_electrified_demand_eur_per_mwh"]
        )
        out.loc[idx, "network_tariff_change_vs_build_eur_per_mwh"] = (
            out.loc[idx, "network_tariff_eur_per_mwh"]
            - b["network_tariff_eur_per_mwh"]
        )
        out.loc[idx, "network_tariff_saving_vs_build_eur_per_mwh"] = (
            b["network_tariff_eur_per_mwh"]
            - out.loc[idx, "network_tariff_eur_per_mwh"]
        )

        withheld = out.loc[idx, "grid_revenue_withheld_vs_build_bn"]
        delta_cost = out.loc[idx, "delta_system_cost_vs_build_bn"]
        positive = withheld > 0

        # Net whole-system penalty after the lower grid expenditure is already
        # accounted for in the PyPSA objective.
        out.loc[idx & positive, "net_system_cost_penalty_per_eur_grid_withheld"] = (
            delta_cost[positive] / withheld[positive]
        )

        # Gross increase in non-grid system costs. This is useful when comparing
        # against claims phrased as "EUR1 invested in grids saves EURX elsewhere".
        gross_non_grid = delta_cost + withheld
        out.loc[idx, "gross_non_grid_cost_increase_vs_build_bn"] = gross_non_grid
        out.loc[
            idx & positive,
            "gross_non_grid_cost_increase_per_eur_grid_withheld",
        ] = gross_non_grid[positive] / withheld[positive]

        out.loc[idx, "delta_system_cost_eur_per_mwh_vs_build"] = (
            out.loc[idx, "system_cost_eur_per_mwh_served"]
            - b["system_cost_eur_per_mwh_served"]
        )

    return out


def build_electrification_effect(df: pd.DataFrame) -> pd.DataFrame:
    """Quantify how demand growth mitigates the Build tariff increase.

    Counterfactual:
        2040 grid revenue / 2030 Build billing base

    This isolates the denominator effect. It is a post-processing
    counterfactual, not a re-optimised 2040 scenario.
    """
    build = df[df["scenario"] == "Build"].set_index("year")
    if not {2030, 2040}.issubset(set(build.index)):
        return pd.DataFrame()

    b30 = build.loc[2030]
    b40 = build.loc[2040]

    demand_30_mwh = b30["electrified_lv_demand_twh"] * 1e6

    def _effect(
        tariff_30: float,
        tariff_40: float,
        revenue_30: float,
        revenue_40: float,
        prefix: str,
    ) -> dict:
        tariff_40_fixed_demand = revenue_40 / demand_30_mwh
        return {
            f"{prefix}tariff_2030_actual_eur_per_mwh": tariff_30,
            f"{prefix}tariff_2040_actual_eur_per_mwh": tariff_40,
            f"{prefix}tariff_2040_with_2030_demand_eur_per_mwh": (
                tariff_40_fixed_demand
            ),
            f"{prefix}revenue_growth_2030_2040_pct": (revenue_40 / revenue_30 - 1.0)
            * 100.0,
            f"{prefix}actual_tariff_growth_2030_2040_pct": (
                tariff_40 / tariff_30 - 1.0
            )
            * 100.0,
            f"{prefix}tariff_growth_without_demand_growth_pct": (
                tariff_40_fixed_demand / tariff_30 - 1.0
            )
            * 100.0,
            f"{prefix}tariff_increase_mitigated_by_demand_growth_eur_per_mwh": (
                tariff_40_fixed_demand - tariff_40
            ),
            f"{prefix}tariff_increase_mitigated_by_demand_growth_pct": (
                1.0 - tariff_40 / tariff_40_fixed_demand
            )
            * 100.0,
        }

    # Legacy unprefixed keys are the DSO-only series.
    dso = _effect(
        b30["dso_tariff_eur_per_mwh"],
        b40["dso_tariff_eur_per_mwh"],
        b30["dso_revenue_bn_eur_per_yr"] * 1e9,
        b40["dso_revenue_bn_eur_per_yr"] * 1e9,
        prefix="",
    )
    dso["grid_revenue_growth_2030_2040_pct"] = dso["revenue_growth_2030_2040_pct"]
    network = _effect(
        b30["network_tariff_eur_per_mwh"],
        b40["network_tariff_eur_per_mwh"],
        b30["network_revenue_bn_eur_per_yr"] * 1e9,
        b40["network_revenue_bn_eur_per_yr"] * 1e9,
        prefix="network_",
    )
    shared = {
        "electrified_demand_growth_2030_2040_pct": (
            b40["electrified_lv_demand_twh"] / b30["electrified_lv_demand_twh"] - 1.0
        )
        * 100.0,
    }
    return pd.DataFrame([{**dso, **network, **shared}])


def _save_figure(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _annotate_bars(ax: plt.Axes, fmt: str = "{:.1f}") -> None:
    for patch in ax.patches:
        value = patch.get_height()
        if pd.isna(value):
            continue
        ax.annotate(
            fmt.format(value),
            (patch.get_x() + patch.get_width() / 2.0, value),
            ha="center",
            va="bottom",
            xytext=(0, 4),
            textcoords="offset points",
            fontsize=9,
        )


def _scenarios_present(df: pd.DataFrame, order: list[str] | None = None) -> list[str]:
    order = order or SCENARIO_ORDER
    present = set(df["scenario"])
    return [s for s in order if s in present]


def _pivot_by_scenario(
    df: pd.DataFrame, value: str, scenarios: list[str] | None = None
) -> pd.DataFrame:
    scenarios = _scenarios_present(df, scenarios)
    pivot = df.pivot(index="scenario", columns="year", values=value)
    return pivot.reindex(scenarios)


def _plot_grouped_bars(
    ax: plt.Axes,
    pivot: pd.DataFrame,
    ylabel: str,
    title: str,
    fmt: str = "{:.1f}",
) -> None:
    pivot.plot(kind="bar", ax=ax, rot=0, width=0.75)
    ax.set_xlabel("")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(title="Horizon")
    _annotate_bars(ax, fmt=fmt)


def _waterfall_electrification(
    row: pd.Series, ax: plt.Axes, prefix: str = ""
) -> None:
    t30 = float(row[f"{prefix}tariff_2030_actual_eur_per_mwh"])
    t40 = float(row[f"{prefix}tariff_2040_actual_eur_per_mwh"])
    t40_fixed = float(row[f"{prefix}tariff_2040_with_2030_demand_eur_per_mwh"])
    grid_step = t40_fixed - t30
    demand_step = t40 - t40_fixed

    labels = [
        "2030\nBuild",
        "Grid expansion\nwithout extra demand",
        "Electrification\n(extra kWh)",
        "2040\nBuild",
    ]
    starts = [0.0, t30, t40_fixed, 0.0]
    heights = [t30, grid_step, demand_step, t40]
    colors = ["C0", "C3", "C2", "C0"]

    for i, (start, height, color) in enumerate(zip(starts, heights, colors)):
        ax.bar(i, height, bottom=start, color=color, width=0.6)
        y_text = start + height if height >= 0 else start
        ax.annotate(
            f"{height:+.1f}" if i in (1, 2) else f"{height:.1f}",
            (i, y_text),
            ha="center",
            va="bottom",
            xytext=(0, 4),
            textcoords="offset points",
            fontsize=9,
        )
        if i in (1, 2):
            ax.plot(
                [i - 0.3, i + 1.3],
                [start + height, start + height],
                color="0.4",
                linewidth=0.8,
            )

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ylabel = (
        "Network tariff proxy, TSO+DSO (EUR/MWh)"
        if prefix == "network_"
        else "DSO tariff proxy (EUR/MWh)"
    )
    title = (
        "TSO+DSO: expansion raises the tariff; electrification offsets most of it"
        if prefix == "network_"
        else "DSO only: expansion raises the tariff; electrification offsets most of it"
    )
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.25)


def _row(df: pd.DataFrame, year: int, scenario: str) -> pd.Series | None:
    match = df[(df["year"] == year) & (df["scenario"] == scenario)]
    if match.empty:
        return None
    return match.iloc[0]


def _plot_tariff_vs_total_bill(df: pd.DataFrame, outdir: Path) -> None:
    """Industry metric (network tariff) vs affordability (total system cost / kWh)."""
    cases = [
        (2030, "Build", "2030 Build"),
        (2040, "Build", "2040 Build\nexpand + electrify"),
        (2040, "65%", "2040 65%\nunder-invest"),
    ]
    rows = []
    labels = []
    for year, scenario, label in cases:
        row = _row(df, year, scenario)
        if row is None:
            continue
        rows.append(row)
        labels.append(label)
    if len(rows) < 2:
        return

    tariff = [r["network_tariff_eur_per_mwh"] for r in rows]
    total = [r["system_cost_eur_per_mwh_served"] for r in rows]
    x = list(range(len(labels)))

    fig, axes = plt.subplots(1, 2, figsize=(11.8, 5.0))

    axes[0].bar(x, tariff, color=["C0", "C0", "C3", "C3"][: len(x)])
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels)
    axes[0].set_ylabel("EUR/MWh")
    axes[0].set_title("Network tariff TSO+DSO\n(industry's line)")
    axes[0].grid(axis="y", alpha=0.25)
    _annotate_bars(axes[0], fmt="{:.1f}")

    axes[1].bar(x, total, color=["C0", "C0", "C3", "C3"][: len(x)])
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels)
    axes[1].set_ylabel("EUR/MWh served")
    axes[1].set_title("Total electricity cost\n(what affordability actually is)")
    axes[1].grid(axis="y", alpha=0.25)
    _annotate_bars(axes[1], fmt="{:.0f}")

    fig.suptitle(
        "Expanding the grid with electrification: network tariff up a little, total cost down.\n"
        "Not expanding: network tariff down, total cost up."
    )
    _save_figure(fig, outdir / "tariff_vs_total_bill.png")

    # Indexed to 2030 Build so both metrics share a scale.
    t0, c0 = tariff[0], total[0]
    if t0 > 0 and c0 > 0:
        fig, ax = plt.subplots(figsize=(8.4, 5.0))
        width = 0.38
        t_idx = [100.0 * v / t0 for v in tariff]
        c_idx = [100.0 * v / c0 for v in total]
        ax.bar(
            [i - width / 2 for i in x],
            t_idx,
            width=width,
            label="Network tariff (TSO+DSO)",
            color="C0",
        )
        ax.bar([i + width / 2 for i in x], c_idx, width=width, label="Total electricity cost", color="C3")
        ax.axhline(100.0, color="0.4", linewidth=0.8, linestyle="--")
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_ylabel("Index (2030 Build = 100)")
        ax.set_title("The network line can rise while the electricity bill falls")
        ax.grid(axis="y", alpha=0.25)
        ax.legend()
        for i, (ti, ci) in enumerate(zip(t_idx, c_idx)):
            ax.annotate(f"{ti:.0f}", (i - width / 2, ti), ha="center", va="bottom", fontsize=8)
            ax.annotate(f"{ci:.0f}", (i + width / 2, ci), ha="center", va="bottom", fontsize=8)
        _save_figure(fig, outdir / "tariff_vs_total_bill_index.png")


def plot_tariffs(
    df: pd.DataFrame,
    electrification_effect: pd.DataFrame,
    outdir: Path,
) -> None:
    """Create presentation-ready figures for the grid-study narrative."""
    outdir.mkdir(parents=True, exist_ok=True)

    # 1) Direct test of the headline electrification claim.
    if not electrification_effect.empty:
        row = electrification_effect.iloc[0]
        labels = [
            "2030 actual",
            "2040 actual",
            "2040 with\n2030 demand",
        ]
        values = [
            row["network_tariff_2030_actual_eur_per_mwh"],
            row["network_tariff_2040_actual_eur_per_mwh"],
            row["network_tariff_2040_with_2030_demand_eur_per_mwh"],
        ]
        fig, ax = plt.subplots(figsize=(7.2, 4.8))
        ax.bar(labels, values)
        ax.set_ylabel("Network tariff proxy, TSO+DSO (EUR/MWh)")
        ax.set_title("Electrification mitigates the tariff impact of TSO+DSO expansion")
        ax.grid(axis="y", alpha=0.25)
        _annotate_bars(ax)
        _save_figure(
            fig,
            outdir / "build_tariff_electrification_counterfactual.png",
        )

        fig, ax = plt.subplots(figsize=(8.0, 5.0))
        _waterfall_electrification(row, ax, prefix="network_")
        _save_figure(fig, outdir / "build_tariff_waterfall.png")

        fig, ax = plt.subplots(figsize=(8.0, 5.0))
        _waterfall_electrification(row, ax, prefix="")
        _save_figure(fig, outdir / "build_dso_tariff_waterfall.png")

        # Hero slide: industry looks at the network line; affordability is the total bill.
        _plot_tariff_vs_total_bill(df, outdir)

        # 2) Indexed decomposition: grid revenue, demand, tariff (2030 = 100).
        build = df[df["scenario"] == "Build"].set_index("year").sort_index()
        if {2030, 2040}.issubset(set(build.index)):
            years = [2030, 2040]
            revenue_index = (
                build.loc[years, "network_revenue_bn_eur_per_yr"]
                / build.loc[2030, "network_revenue_bn_eur_per_yr"]
                * 100.0
            )
            demand_index = (
                build.loc[years, "electrified_lv_demand_twh"]
                / build.loc[2030, "electrified_lv_demand_twh"]
                * 100.0
            )
            tariff_index = (
                build.loc[years, "network_tariff_eur_per_mwh"]
                / build.loc[2030, "network_tariff_eur_per_mwh"]
                * 100.0
            )

            fig, ax = plt.subplots(figsize=(7.2, 4.8))
            ax.plot(years, revenue_index.values, marker="o", label="TSO+DSO revenue")
            ax.plot(years, demand_index.values, marker="o", label="Electrified demand")
            ax.plot(years, tariff_index.values, marker="o", label="Network tariff")
            ax.set_xticks(years)
            ax.set_ylabel("Index (2030 = 100)")
            ax.set_xlabel("Planning horizon")
            ax.set_title("Why the TSO+DSO tariff rises less than grid expenditure")
            ax.grid(alpha=0.25)
            ax.legend()
            _save_figure(
                fig,
                outdir / "build_revenue_demand_tariff_indices.png",
            )

    # 3) Tariff proxy versus permitted grid investment.
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    for year, grp in df.groupby("year"):
        g = grp.dropna(subset=["cap_fraction"]).sort_values(
            "cap_fraction", ascending=False
        )
        ax.plot(
            100.0 * g["cap_fraction"],
            g["network_tariff_eur_per_mwh"],
            marker="o",
            label=str(year),
        )
    ax.set_xlabel("Permitted distribution-grid investment (% of Build)")
    ax.set_ylabel("Network tariff proxy, TSO+DSO (EUR/MWh)")
    ax.set_title("TSO+DSO tariff under DSO under-investment")
    ax.grid(alpha=0.25)
    ax.legend(title="Horizon")
    ax.invert_xaxis()
    _save_figure(fig, outdir / "tariff_vs_cap.png")

    # 3b) Same tariff comparison as bars — easier to read across cases.
    fig, ax = plt.subplots(figsize=(8.2, 5.0))
    _plot_grouped_bars(
        ax,
        _pivot_by_scenario(df, "network_tariff_eur_per_mwh"),
        ylabel="Network tariff proxy, TSO+DSO (EUR/MWh)",
        title="Network tariff (TSO+DSO) — not the electricity bill",
        fmt="{:.1f}",
    )
    _save_figure(fig, outdir / "tariff_by_scenario_bars.png")

    fig, ax = plt.subplots(figsize=(8.2, 5.0))
    _plot_grouped_bars(
        ax,
        _pivot_by_scenario(df, "dso_tariff_eur_per_mwh"),
        ylabel="DSO tariff proxy (EUR/MWh)",
        title="DSO-only tariff (the capped line-item)",
        fmt="{:.1f}",
    )
    _save_figure(fig, outdir / "dso_tariff_by_scenario_bars.png")

    # 4) Cost of inaction rather than absolute system cost.
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    for year, grp in df.groupby("year"):
        g = grp.dropna(subset=["cap_fraction"]).sort_values(
            "cap_fraction", ascending=False
        )
        ax.plot(
            100.0 * g["cap_fraction"],
            g["delta_system_cost_vs_build_bn"],
            marker="o",
            label=str(year),
        )
    ax.axhline(0.0, linewidth=0.8)
    ax.set_xlabel("Permitted distribution-grid investment (% of Build)")
    ax.set_ylabel("Additional system cost vs Build (bn EUR/yr)")
    ax.set_title("Cost of distribution-grid under-investment")
    ax.grid(alpha=0.25)
    ax.legend(title="Horizon")
    ax.invert_xaxis()
    _save_figure(fig, outdir / "cost_of_inaction_vs_cap.png")

    # 4b) Cost of inaction as bars. Split mild vs extreme so 50% does not hide the rest.
    inaction = df[df["scenario"] != "Build"]
    mild_caps = ["85%", "75%", "65%"]
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8))
    mild = inaction[inaction["scenario"].isin(mild_caps)]
    _plot_grouped_bars(
        axes[0],
        _pivot_by_scenario(mild, "delta_system_cost_vs_build_bn", mild_caps),
        ylabel="Additional system cost vs Build (bn EUR/yr)",
        title="Cost of inaction (mild under-investment)",
        fmt="{:.1f}",
    )
    _plot_grouped_bars(
        axes[1],
        _pivot_by_scenario(inaction, "delta_system_cost_vs_build_bn"),
        ylabel="Additional system cost vs Build (bn EUR/yr)",
        title="Cost of inaction (all cases, incl. 50%)",
        fmt="{:.0f}",
    )
    fig.suptitle("Doing nothing is more expensive than building the grid")
    _save_figure(fig, outdir / "cost_of_inaction_bars.png")

    # 4c) Same cost in EUR/MWh served — comparable to the tariff.
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8))
    _plot_grouped_bars(
        axes[0],
        _pivot_by_scenario(mild, "delta_system_cost_eur_per_mwh_vs_build", mild_caps),
        ylabel="Extra system cost vs Build (EUR/MWh served)",
        title="Cost of inaction per served kWh (mild)",
        fmt="{:.1f}",
    )
    _plot_grouped_bars(
        axes[1],
        _pivot_by_scenario(inaction, "delta_system_cost_eur_per_mwh_vs_build"),
        ylabel="Extra system cost vs Build (EUR/MWh served)",
        title="Cost of inaction per served kWh (all cases)",
        fmt="{:.0f}",
    )
    fig.suptitle("Inaction raises the total bill by more than it cuts the network tariff")
    _save_figure(fig, outdir / "cost_of_inaction_eur_per_mwh_bars.png")

    # 4d) Bill composition: network tariff vs the rest of system cost, same units.
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.2), sharey=True)
    for ax, year in zip(axes, sorted(df["year"].unique())):
        g = (
            df[df["year"] == year]
            .set_index("scenario")
            .reindex(_scenarios_present(df, MILD_SCENARIOS))
            .dropna(how="all")
        )
        if g.empty:
            continue
        dso = g["dso_tariff_eur_per_mwh"]
        tso = g["tso_tariff_eur_per_mwh"]
        rest = g["non_network_cost_eur_per_mwh_served"]
        x = range(len(g))
        ax.bar(x, dso, label="DSO", color="C0")
        ax.bar(x, tso, bottom=dso, label="TSO", color="C1")
        ax.bar(x, rest, bottom=dso + tso, label="Rest of system cost", color="0.75")
        ax.set_xticks(list(x))
        ax.set_xticklabels(g.index.tolist())
        ax.set_title(str(year))
        ax.set_ylabel("EUR/MWh served")
        ax.grid(axis="y", alpha=0.25)
        for i, (d_val, t_val, r_val) in enumerate(zip(dso, tso, rest)):
            ax.annotate(
                f"{d_val + t_val:.1f}",
                (i, (d_val + t_val) / 2),
                ha="center",
                va="center",
                color="white",
                fontsize=8,
            )
            ax.annotate(
                f"{d_val + t_val + r_val:.0f}",
                (i, d_val + t_val + r_val),
                ha="center",
                va="bottom",
                fontsize=8,
            )
        if ax is axes[0]:
            ax.legend(loc="upper left")
    fig.suptitle(
        "TSO+DSO network line vs total system cost per served kWh (Build and mild inaction)"
    )
    _save_figure(fig, outdir / "bill_composition_eur_per_mwh.png")

    # 4e) The political slide: 2040 tariff vs extra system cost, side by side.
    y2040 = df[df["year"] == 2040]
    if not y2040.empty:
        fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8))
        scenarios = _scenarios_present(y2040)
        g = y2040.set_index("scenario").reindex(scenarios)
        axes[0].bar(g.index, g["network_tariff_eur_per_mwh"], color="C0")
        axes[0].set_ylabel("EUR/MWh")
        axes[0].set_title("Network tariff TSO+DSO, 2040")
        axes[0].grid(axis="y", alpha=0.25)
        _annotate_bars(axes[0], fmt="{:.1f}")

        g_inaction = g.drop(index="Build", errors="ignore")
        axes[1].bar(
            g_inaction.index,
            g_inaction["delta_system_cost_vs_build_bn"],
            color="C3",
        )
        axes[1].set_ylabel("bn EUR/yr")
        axes[1].set_title("Cost of inaction vs Build, 2040")
        axes[1].grid(axis="y", alpha=0.25)
        _annotate_bars(axes[1], fmt="{:.0f}")
        fig.suptitle(
            "Capping grid spend can cut the network line; it raises the total bill"
        )
        _save_figure(fig, outdir / "tariff_and_inaction_cost_2040.png")

    # 5) Reliability / knee diagnostic.
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    for year, grp in df.groupby("year"):
        g = grp.dropna(subset=["cap_fraction"]).sort_values(
            "cap_fraction", ascending=False
        )
        ax.plot(
            100.0 * g["cap_fraction"],
            g["lv_load_shedding_twh"],
            marker="o",
            label=str(year),
        )
    ax.set_xlabel("Permitted distribution-grid investment (% of Build)")
    ax.set_ylabel("LV electricity not served (TWh)")
    ax.set_title("Reliability cliff under grid under-investment")
    ax.grid(alpha=0.25)
    ax.legend(title="Horizon")
    ax.invert_xaxis()
    _save_figure(fig, outdir / "lv_load_shedding_vs_cap.png")

    # 6) Full cost curve against the actual annual grid expenditure withheld.
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    for year, grp in df.groupby("year"):
        g = grp[
            grp["grid_revenue_withheld_vs_build_bn"].notna()
            & grp["delta_system_cost_vs_build_bn"].notna()
        ].sort_values("grid_revenue_withheld_vs_build_bn")
        ax.plot(
            g["grid_revenue_withheld_vs_build_bn"],
            g["delta_system_cost_vs_build_bn"],
            marker="o",
            label=str(year),
        )
    ax.set_xlabel("Annual grid expenditure withheld vs Build (bn EUR/yr)")
    ax.set_ylabel("Additional system cost vs Build (bn EUR/yr)")
    ax.set_title("System-cost penalty versus grid-investment gap")
    ax.grid(alpha=0.25)
    ax.legend(title="Horizon")
    _save_figure(fig, outdir / "system_cost_vs_grid_investment_gap.png")

    # 7) Political trade-off: network-line saving versus whole-system penalty.
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    for year, grp in df.groupby("year"):
        g = grp[
            grp["network_tariff_saving_vs_build_eur_per_mwh"].notna()
            & grp["delta_system_cost_vs_build_bn"].notna()
        ].sort_values("network_tariff_saving_vs_build_eur_per_mwh")
        ax.plot(
            g["network_tariff_saving_vs_build_eur_per_mwh"],
            g["delta_system_cost_vs_build_bn"],
            marker="o",
            label=str(year),
        )
    ax.set_xlabel("Network tariff saving vs Build (EUR/MWh)")
    ax.set_ylabel("Additional system cost vs Build (bn EUR/yr)")
    ax.set_title("Lower TSO+DSO line-item versus higher system cost")
    ax.grid(alpha=0.25)
    ax.legend(title="Horizon")
    _save_figure(fig, outdir / "tariff_saving_vs_system_cost_penalty.png")

    _plot_tso_dso_decomposition(df, outdir)
    _plot_ec_benchmarks(df, outdir)


def _plot_tso_dso_decomposition(df: pd.DataFrame, outdir: Path) -> None:
    """Stacked TSO vs DSO tariff so the two line-items stay distinct."""
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.0), sharey=True)
    for ax, year in zip(axes, sorted(df["year"].unique())):
        g = (
            df[df["year"] == year]
            .set_index("scenario")
            .reindex(_scenarios_present(df, MILD_SCENARIOS))
            .dropna(how="all")
        )
        if g.empty:
            continue
        dso = g["dso_tariff_eur_per_mwh"]
        tso = g["tso_tariff_eur_per_mwh"]
        x = range(len(g))
        ax.bar(x, dso, label="DSO", color="C0")
        ax.bar(x, tso, bottom=dso, label="TSO (AC+DC)", color="C1")
        ax.set_xticks(list(x))
        ax.set_xticklabels(g.index.tolist())
        ax.set_title(str(year))
        ax.set_ylabel("EUR/MWh served")
        ax.grid(axis="y", alpha=0.25)
        for i, (d_val, t_val) in enumerate(zip(dso, tso)):
            ax.annotate(
                f"{d_val + t_val:.1f}",
                (i, d_val + t_val),
                ha="center",
                va="bottom",
                fontsize=8,
            )
        if ax is axes[0]:
            ax.legend(loc="upper left")
    fig.suptitle("Network tariff by definition = TSO + DSO (inaction caps DSO only)")
    _save_figure(fig, outdir / "tso_dso_tariff_stack.png")


def _plot_ec_benchmarks(df: pd.DataFrame, outdir: Path) -> None:
    """Table 20 production cost and Table 16 new investment vs the EC."""
    build = df[df["scenario"] == "Build"]
    if build.empty:
        return

    # Table 20: production €/MWh vs EC S2 96 (and S1/S3 band).
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    pivot = _pivot_by_scenario(df[df["scenario"].isin(MILD_SCENARIOS)], "elec_production_cost_eur_per_mwh", MILD_SCENARIOS)
    if not pivot.empty:
        _plot_grouped_bars(
            ax,
            pivot,
            ylabel="EUR/MWh generated",
            title="Electricity production cost (no TSO/DSO) vs EC Table 20",
            fmt="{:.0f}",
        )
        ax.axhline(
            EC_TABLE20_EUR_PER_MWH["S2"],
            color="0.2",
            linestyle="--",
            linewidth=1.2,
            label="EC S2 2040 (€96/MWh)",
        )
        ax.axhspan(
            EC_TABLE20_EUR_PER_MWH["S3"],
            EC_TABLE20_EUR_PER_MWH["S1"],
            color="0.5",
            alpha=0.15,
            label="EC S1–S3 2040 (€94–97)",
        )
        ax.legend(title="Horizon")
        _save_figure(fig, outdir / "ec_table20_production_cost.png")
    else:
        plt.close(fig)

    y2040_build = build[build["year"] == 2040]
    if y2040_build.empty:
        return
    row = y2040_build.iloc[0]

    # Production-cost composition vs EC 51/33/16.
    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    labels = ["PyPSA 2040 Build\n(FOM still in capex)", "PyPSA 2040 Build\n(FOM moved to O&M)", "EC S2 2040"]
    cap_raw = row["elec_capex_eur_per_mwh"]
    vom = row["elec_vom_eur_per_mwh"]
    fuel = row["elec_fuel_eur_per_mwh"]
    cap_only = row["elec_capital_only_eur_per_mwh"]
    fom = row["elec_fom_in_capex_eur_per_mwh"]
    ec = EC_TABLE20_EUR_PER_MWH["S2"]
    ec_cap = ec * EC_TABLE20_S2_SHARE["capital"]
    ec_om = ec * EC_TABLE20_S2_SHARE["om"]
    ec_fuel = ec * EC_TABLE20_S2_SHARE["fuel"]
    capital = [cap_raw, cap_only, ec_cap]
    om = [vom, vom + fom, ec_om]
    fuels = [fuel, fuel, ec_fuel]
    x = range(3)
    ax.bar(x, capital, label="Capital", color="C0")
    ax.bar(x, om, bottom=capital, label="O&M / FOM", color="C1")
    ax.bar(
        x,
        fuels,
        bottom=[c + o for c, o in zip(capital, om)],
        label="Fuel",
        color="C2",
    )
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("EUR/MWh generated")
    ax.set_title("Table 20 decomposition: PyPSA still capital-heavy (existing fleet annualised)")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    for i, (c, o, f) in enumerate(zip(capital, om, fuels)):
        ax.annotate(f"{c + o + f:.0f}", (i, c + o + f), ha="center", va="bottom", fontsize=9)
    _save_figure(fig, outdir / "ec_table20_cost_decomposition.png")

    # Table 16: 2040 new overnight / 10 years vs S2 2031–2040 cash investment.
    fig, ax = plt.subplots(figsize=(8.0, 5.2))
    buckets = ["grid", "plants", "other"]
    pypsa_vals = [row[f"new_{b}_overnight_bn_per_yr_over_decade"] for b in buckets]
    ec_vals = [row[f"ec_table16_s2_{b}_bn_per_yr"] for b in buckets]
    x = np.arange(len(buckets))
    width = 0.36
    ax.bar(x - width / 2, pypsa_vals, width, label="PyPSA 2040 new overnight / 10y", color="C0")
    ax.bar(x + width / 2, ec_vals, width, label="EC S2 2031–2040 (Table 16)", color="0.55")
    ax.set_xticks(x)
    ax.set_xticklabels(["Power grid", "Power plants", "Other supply"])
    ax.set_ylabel("bn € / year (cash investment)")
    ax.set_title("Table 16: new investment, not n.objective")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    for i, (p, e) in enumerate(zip(pypsa_vals, ec_vals)):
        ax.annotate(f"{p:.0f}", (i - width / 2, p), ha="center", va="bottom", fontsize=8)
        ax.annotate(f"{e:.0f}", (i + width / 2, e), ha="center", va="bottom", fontsize=8)
    _save_figure(fig, outdir / "ec_table16_investment.png")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument(
        "--results-root",
        type=Path,
        default=Path("results/2026-grid-study"),
        help="Folder containing per-run result trees (run.name / networks / *.nc).",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("results/2026-grid-study/distribution_tariffs"),
        help="Output directory for CSV and figures.",
    )
    return p.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()

    df = collect_table(args.results_root)
    df = add_build_relative_columns(df)
    electrification_effect = build_electrification_effect(df)

    args.output.mkdir(parents=True, exist_ok=True)

    definitions_path = args.output / "metric_definitions.md"
    definitions_path.write_text(METRIC_DEFINITIONS)
    logger.info("Wrote %s", definitions_path)

    csv_path = args.output / "distribution_tariffs.csv"
    df.to_csv(csv_path, index=False, float_format="%.4f")
    logger.info("Wrote %s", csv_path)

    bench_cols = [
        "year",
        "scenario",
        "system_cost_bn_eur_per_yr",
        "dso_tariff_eur_per_mwh",
        "tso_tariff_eur_per_mwh",
        "network_tariff_eur_per_mwh",
        "elec_generation_twh",
        "elec_production_cost_eur_per_mwh",
        "elec_capex_eur_per_mwh",
        "elec_vom_eur_per_mwh",
        "elec_fuel_eur_per_mwh",
        "elec_capital_only_eur_per_mwh",
        "elec_om_plus_fom_eur_per_mwh",
        "ec_table20_s2_eur_per_mwh",
        "new_grid_overnight_bn_per_yr_over_decade",
        "new_plants_overnight_bn_per_yr_over_decade",
        "new_other_overnight_bn_per_yr_over_decade",
        "ec_table16_s2_grid_bn_per_yr",
        "ec_table16_s2_plants_bn_per_yr",
        "ec_table16_s2_other_bn_per_yr",
        "fossil_fuel_expenditure_bn_eur_per_yr",
    ]
    bench = df[[c for c in bench_cols if c in df.columns]]
    bench_path = args.output / "ec_benchmarks.csv"
    bench.to_csv(bench_path, index=False, float_format="%.4f")
    logger.info("Wrote %s", bench_path)

    if not electrification_effect.empty:
        effect_path = args.output / "build_electrification_effect.csv"
        electrification_effect.to_csv(
            effect_path,
            index=False,
            float_format="%.4f",
        )
        logger.info("Wrote %s", effect_path)

        e = electrification_effect.iloc[0]
        logger.info(
            "Build electrification effect (TSO+DSO): tariff %.2f EUR/MWh (2030) -> "
            "%.2f EUR/MWh (2040 actual), versus %.2f EUR/MWh if the 2040 "
            "network revenue were recovered from the 2030 billing base. "
            "DSO-only: %.2f -> %.2f (counterfactual %.2f).",
            e["network_tariff_2030_actual_eur_per_mwh"],
            e["network_tariff_2040_actual_eur_per_mwh"],
            e["network_tariff_2040_with_2030_demand_eur_per_mwh"],
            e["tariff_2030_actual_eur_per_mwh"],
            e["tariff_2040_actual_eur_per_mwh"],
            e["tariff_2040_with_2030_demand_eur_per_mwh"],
        )

    plot_tariffs(df, electrification_effect, args.output)
    logger.info("Wrote figures under %s", args.output)

    cols = [
        "year",
        "scenario",
        "dso_revenue_bn_eur_per_yr",
        "tso_revenue_bn_eur_per_yr",
        "network_revenue_bn_eur_per_yr",
        "electrified_lv_demand_twh",
        "dso_tariff_eur_per_mwh",
        "tso_tariff_eur_per_mwh",
        "network_tariff_eur_per_mwh",
        "elec_production_cost_eur_per_mwh",
        "new_grid_overnight_bn_per_yr_over_decade",
        "new_plants_overnight_bn_per_yr_over_decade",
        "new_other_overnight_bn_per_yr_over_decade",
        "grid_revenue_withheld_vs_build_bn",
        "delta_system_cost_vs_build_bn",
        "lv_load_shedding_twh",
        "system_cost_eur_per_mwh_served",
        "system_cost_bn_eur_per_yr",
    ]
    existing_cols = [c for c in cols if c in df.columns]
    print(
        df[existing_cols].to_string(
            index=False,
            float_format=lambda x: f"{x:,.2f}",
        )
    )


if __name__ == "__main__":
    main()
