# SPDX-FileCopyrightText: Contributors to PyPSA-Eurelectric
#
# SPDX-License-Identifier: MIT
"""
Scenario dashboard for the grid-study runs (Build / 85 / 75 / 65 / 50%).

Writes two CSVs:

1. One row per scenario-year with system cost (EU ``n.objective``) plus
   German physical metrics.
2. Decomposition of Δ system cost vs Build by asset/cost category.

System cost in the objective is ``expanded_capex + opex`` (installed /
sunk annuity is *not* in ``n.objective``). Categories are grouped from
``n.statistics.expanded_capex()`` and ``n.statistics.opex()``.

Usage (repo root, pixi env):

    python scripts/eurelectric/grid_study_scenario_dashboard.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa

sys.path.insert(0, str(Path(__file__).resolve().parent))
from feed_german_network_tariffs import (  # noqa: E402
    RUN_META,
    _weights,
    extract_germany,
)

logger = logging.getLogger(__name__)

VRE_CARRIERS = {
    "solar",
    "solar rooftop",
    "solar-hsat",
    "onwind",
    "offwind-ac",
    "offwind-dc",
    "offwind-float",
}

DSO_INVESTMENT_EUR_PER_MW = 667901.6  # processed technology-data, both horizons


def _bucket(component: str, carrier: str) -> str:
    c = str(carrier)
    cl = c.lower()
    if component == "Line":
        return "TSO_AC"
    if cl == "dc":
        return "TSO_DC"
    if "electricity distribution grid" in cl:
        return "DSO"
    if "solar rooftop" in cl:
        return "solar_rooftop"
    if "home battery" in cl:
        return "home_battery"
    if cl == "load":
        return "load_shedding"
    if component == "Store" and cl == "co2":
        return "carbon_price"
    if "heat pump" in cl:
        return "heat_pumps"
    if "boiler" in cl or "resistive heater" in cl:
        return "boilers"
    if "solar thermal" in cl:
        return "solar_thermal"
    if "water pit" in cl or "water tank" in cl:
        return "heat_storage"
    if "fischer-tropsch" in cl or cl in {"methanolisation", "methanol"}:
        return "synthetic_fuels"
    if "import oil" in cl or cl in {"oil", "oil primary"}:
        return "oil"
    if "unsustainable" in cl:
        return "fossil_and_unsustainable_fuel"
    if any(
        tok in cl
        for tok in (
            "biomass",
            "biogas",
            "waste chp",
            "biogas to gas",
        )
    ):
        return "biomass"
    if any(
        tok in cl
        for tok in (
            "open-cycle gas",
            "combined-cycle gas",
            "gas chp",
            "ocgt",
            "ccgt",
        )
    ):
        return "gas_power"
    if "co2 sequestered" in cl or "process emissions" in cl or cl.endswith(" cc"):
        return "ccs"
    if cl in {"uranium", "lignite", "coal"}:
        return "fuel_stores"
    if cl in {"solar", "solar-hsat"} or "onshore wind" in cl or "offshore wind" in cl:
        return "utility_vre"
    if cl in {"onwind", "offwind-ac", "offwind-dc", "offwind-float"}:
        return "utility_vre"
    if component == "Generator" and cl in {
        "oil primary",
        "gas",
        "coal",
        "lignite",
        "unsustainable bioliquids",
        "unsustainable solid biomass",
        "unsustainable biogas",
    }:
        return "fossil_and_unsustainable_fuel"
    if component == "Store" and cl == "gas":
        return "gas_storage"
    if any(
        tok in cl
        for tok in ("h2", "electrolysis", "smr", "fuel cell", "hydrogen", "sabatier")
    ):
        return "hydrogen"
    if "battery" in cl:
        return "grid_battery"
    if any(
        tok in cl
        for tok in ("nuclear", "run of river", "hydro", "reservoir", "phs", "dam")
    ):
        return "firm_power"
    return "other"


def series_to_buckets(s: pd.Series) -> pd.Series:
    if s is None or s.empty:
        return pd.Series(dtype=float)
    out: dict[str, float] = {}
    for idx, val in s.items():
        if isinstance(idx, tuple) and len(idx) >= 2:
            component, carrier = idx[0], idx[1]
        else:
            component, carrier = "", str(idx)
        b = _bucket(str(component), str(carrier))
        out[b] = out.get(b, 0.0) + float(val)
    return pd.Series(out)


def vre_curtailment_twh(n: pypsa.Network, country: str | None = None) -> float:
    """Unused VRE potential (p_max_pu × p_nom − p), not dispatchable headroom."""
    gens = n.generators[n.generators.carrier.isin(VRE_CARRIERS)].copy()
    if country is not None:
        ctry = n.buses.reindex(gens.bus)["country"]
        gens = gens.loc[ctry.fillna("").values == country]
    if gens.empty or n.generators_t.p.empty:
        return 0.0
    nom = gens["p_nom"].fillna(0.0)
    if "p_nom_opt" in gens.columns:
        ext = gens["p_nom_extendable"].fillna(False) if "p_nom_extendable" in gens.columns else pd.Series(True, index=gens.index)
        nom = nom.copy()
        nom.loc[ext] = gens.loc[ext, "p_nom_opt"].fillna(gens.loc[ext, "p_nom"])
    w = _weights(n)
    p = n.generators_t.p.reindex(columns=gens.index, fill_value=0.0)
    if n.generators_t.p_max_pu.empty:
        return 0.0
    pmax = n.generators_t.p_max_pu.reindex(columns=gens.index, fill_value=1.0)
    potential = pmax.mul(nom, axis=1).clip(lower=0.0)
    unused = (potential - p.clip(lower=0.0)).clip(lower=0.0)
    return float(unused.multiply(w, axis=0).sum().sum()) / 1e6


def shedding_hours(n: pypsa.Network, country: str | None = None, bus_carrier: str | None = "low voltage") -> float:
    """Snapshot-weighted hours with positive load-shedding (native VOLL gens)."""
    gens = n.generators
    mask = gens.carrier.str.contains("load", case=False, na=False) | gens.index.str.contains(
        "load shedding", case=False
    )
    if bus_carrier is not None:
        mask = mask & gens.bus.map(n.buses.carrier).eq(bus_carrier)
    if country is not None:
        mask = mask & gens.bus.map(n.buses.country).eq(country)
    idx = gens.index[mask]
    if idx.empty or n.generators_t.p.empty:
        return 0.0
    p = n.generators_t.p.reindex(columns=idx, fill_value=0.0).clip(lower=0.0).sum(axis=1)
    w = _weights(n)
    # 1 MW: ignore solver crumbs. 1 kW would flag every snapshot.
    return float(w.loc[p > 1.0].sum())

def shedding_twh(n: pypsa.Network, country: str | None = None, bus_carrier: str | None = None) -> float:
    gens = n.generators
    mask = gens.carrier.str.contains("load", case=False, na=False)
    if bus_carrier is not None:
        mask = mask & gens.bus.map(n.buses.carrier).eq(bus_carrier)
    if country is not None:
        mask = mask & gens.bus.map(n.buses.country).eq(country)
    idx = gens.index[mask]
    if idx.empty or n.generators_t.p.empty:
        return 0.0
    p = n.generators_t.p.reindex(columns=idx, fill_value=0.0).clip(lower=0.0)
    return float(p.multiply(_weights(n), axis=0).sum().sum()) / 1e6


def co2_atmosphere_mt(n: pypsa.Network) -> float:
    """Net CO₂ added to the atmosphere store over the year (Mt)."""
    atmo = n.stores.index[n.stores.carrier.eq("co2")]
    if atmo.empty or n.stores_t.e.empty:
        return float("nan")
    e = n.stores_t.e.reindex(columns=atmo, fill_value=0.0).sum(axis=1)
    return float(e.iloc[-1] - e.iloc[0]) / 1e6


def electricity_generation_twh(n: pypsa.Network) -> float:
    """Electricity produced (VRE, hydro reservoirs, thermal links). Not throughput."""
    w = _weights(n)
    elec = {"AC", "low voltage"}
    gen_bus = n.generators.bus.map(n.buses.carrier)
    loadlike = n.generators.carrier.str.contains("load", case=False, na=False)
    gens = n.generators.index[gen_bus.isin(elec) & ~loadlike]
    g = 0.0
    if len(gens) and not n.generators_t.p.empty:
        g += float(
            n.generators_t.p.reindex(columns=gens, fill_value=0.0)
            .clip(lower=0.0)
            .multiply(w, axis=0)
            .sum()
            .sum()
        )
    if not n.storage_units.empty and not n.storage_units_t.p.empty:
        hydro = n.storage_units.index[
            n.storage_units.carrier.str.contains("hydro|reservoir|PHS|dam", case=False, na=False)
        ]
        if len(hydro):
            g += float(
                n.storage_units_t.p.reindex(columns=hydro, fill_value=0.0)
                .clip(lower=0.0)
                .multiply(w, axis=0)
                .sum()
                .sum()
            )
    # thermal electricity: links with bus1 on AC
    if not n.links.empty and not n.links_t.p1.empty:
        thermal = n.links.index[
            n.links.carrier.str.contains(
                r"OCGT|CCGT|nuclear|coal|lignite|CHP|fuel cell|H2 turbine",
                case=False,
                na=False,
            )
        ]
        if len(thermal):
            # electricity injection is -p1 or -p0 depending on topology
            bus1_elec = n.links.loc[thermal, "bus1"].map(n.buses.carrier).isin(elec)
            p1 = n.links_t.p1.reindex(columns=thermal[bus1_elec], fill_value=0.0)
            g += float((-p1).clip(lower=0.0).multiply(w, axis=0).sum().sum())
            bus0_elec = n.links.loc[thermal, "bus0"].map(n.buses.carrier).isin(elec)
            p0 = n.links_t.p0.reindex(columns=thermal[bus0_elec], fill_value=0.0)
            g += float((-p0).clip(lower=0.0).multiply(w, axis=0).sum().sum())
    return g / 1e6


def cost_decomposition(n: pypsa.Network) -> pd.Series:
    """Objective-relevant cost by bucket (expanded capex + opex), bn €/yr."""
    cap = n.statistics.expanded_capex().fillna(0.0)
    opex = n.statistics.opex().fillna(0.0)
    cap_b = series_to_buckets(cap) / 1e9
    opex_b = series_to_buckets(opex) / 1e9
    keys = sorted(set(cap_b.index) | set(opex_b.index))
    total = pd.Series(
        {k: float(cap_b.get(k, 0.0) + opex_b.get(k, 0.0)) for k in keys}
    )
    total["__expanded_capex_sum"] = float(cap.sum()) / 1e9
    total["__opex_sum"] = float(opex.sum()) / 1e9
    total["__recon_objective"] = float(cap.sum() + opex.sum()) / 1e9
    return total


def collect(results_root: Path, extract_csv: Path | None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if extract_csv is not None:
        de = pd.read_csv(extract_csv)
        logger.info("Reused German extract %s", extract_csv)
        need_de_fn = False
    else:
        de = None
        need_de_fn = True

    dash_rows = []
    decomp_rows = []
    de_rows = [] if need_de_fn else None

    for run, meta in RUN_META.items():
        for year in (2030, 2040):
            path = results_root / run / "networks" / f"base_s_37___{year}.nc"
            if not path.exists():
                logger.warning("Missing %s", path)
                continue
            logger.info("Reading %s", path)
            n = pypsa.Network(str(path))
            if need_de_fn:
                de_rows.append(extract_germany(n, run, year))

            cap = n.statistics.expanded_capex().fillna(0.0)
            opex = n.statistics.opex().fillna(0.0)
            recon = float(cap.sum() + opex.sum()) / 1e9
            obj = float(n.objective) / 1e9
            buckets = series_to_buckets(cap) / 1e9
            opex_b = series_to_buckets(opex) / 1e9
            all_keys = sorted(set(buckets.index) | set(opex_b.index))
            for k in all_keys:
                decomp_rows.append(
                    {
                        "run": run,
                        "scenario": meta["label"],
                        "year": year,
                        "category": k,
                        "expanded_capex_bn_eur_per_yr": float(buckets.get(k, 0.0)),
                        "opex_bn_eur_per_yr": float(opex_b.get(k, 0.0)),
                        "cost_in_objective_bn_eur_per_yr": float(
                            buckets.get(k, 0.0) + opex_b.get(k, 0.0)
                        ),
                    }
                )
            residual = obj - recon
            decomp_rows.append(
                {
                    "run": run,
                    "scenario": meta["label"],
                    "year": year,
                    "category": "residual_vs_objective",
                    "expanded_capex_bn_eur_per_yr": 0.0,
                    "opex_bn_eur_per_yr": residual,
                    "cost_in_objective_bn_eur_per_yr": residual,
                }
            )

            gen_twh = electricity_generation_twh(n)
            dash_rows.append(
                {
                    "run": run,
                    "scenario": meta["label"],
                    "year": year,
                    "system_cost_bn_eur_per_yr": obj,
                    "system_cost_recon_bn_eur_per_yr": recon,
                    "elec_generation_twh": gen_twh,
                    "system_cost_eur_per_mwh": obj * 1e3 / gen_twh if gen_twh else float("nan"),
                    "eu_load_shedding_twh": shedding_twh(n),
                    "eu_lv_shedding_twh": shedding_twh(n, bus_carrier="low voltage"),
                    "eu_shedding_hours": shedding_hours(n, country=None, bus_carrier=None),
                    "de_shedding_hours": shedding_hours(n, country="DE", bus_carrier="low voltage"),
                    "co2_emissions_mt": co2_atmosphere_mt(n),
                    "eu_vre_curtailment_twh": vre_curtailment_twh(n),
                    "de_vre_curtailment_twh": vre_curtailment_twh(n, country="DE"),
                    "eu_dso_new_ann_bn": float(
                        cap.xs("electricity distribution grid", level="carrier", drop_level=False).sum()
                    )
                    / 1e9
                    if "electricity distribution grid" in cap.index.get_level_values("carrier")
                    else 0.0,
                    "eu_tso_ac_new_ann_bn": float(cap.xs("Line", level="component", drop_level=False).sum()) / 1e9
                    if "Line" in cap.index.get_level_values("component")
                    else 0.0,
                    "eu_tso_dc_new_ann_bn": float(cap.xs("DC", level="carrier", drop_level=False).sum()) / 1e9
                    if "DC" in cap.index.get_level_values("carrier")
                    else 0.0,
                }
            )
            del n

    dash = pd.DataFrame(dash_rows)
    decomp = pd.DataFrame(decomp_rows)
    if need_de_fn:
        de = pd.DataFrame(de_rows)
    return dash, decomp, de


def assemble_dashboard(dash: pd.DataFrame, de: pd.DataFrame) -> pd.DataFrame:
    de_s = de.copy()
    merged = dash.merge(
        de_s,
        on=["scenario", "year"],
        how="left",
        suffixes=("", "_de"),
    )

    def vs_build(col: str) -> pd.Series:
        out = []
        for _, r in merged.iterrows():
            b = merged[
                (merged["scenario"] == "Build") & (merged["year"] == r["year"])
            ]
            if b.empty:
                out.append(float("nan"))
            else:
                out.append(float(r[col]) - float(b.iloc[0][col]))
        return pd.Series(out, index=merged.index)

    merged["delta_system_cost_vs_build_bn"] = vs_build("system_cost_bn_eur_per_yr")
    merged["de_dso_new_overnight_bn"] = merged["dso_new_gw"] * DSO_INVESTMENT_EUR_PER_MW / 1e6
    merged["dso_investment_vs_build_bn"] = vs_build("de_dso_new_overnight_bn")
    merged["dso_annualised_cost_vs_build_bn"] = vs_build("dso_stock_ann_bn_context_only")
    merged["tso_investment_vs_build_bn"] = vs_build("tso_new_ann_bn_context_only")
    merged["tso_annualised_cost_vs_build_bn"] = vs_build("tso_ann_bn_context_only")
    merged["eu_dso_investment_vs_build_bn"] = vs_build("eu_dso_new_ann_bn")
    merged["eu_tso_investment_vs_build_bn"] = vs_build("eu_tso_ac_new_ann_bn") + vs_build(
        "eu_tso_dc_new_ann_bn"
    )

    cols = [
        "scenario",
        "year",
        "system_cost_bn_eur_per_yr",
        "system_cost_eur_per_mwh",
        "delta_system_cost_vs_build_bn",
        "dso_investment_vs_build_bn",
        "dso_annualised_cost_vs_build_bn",
        "tso_investment_vs_build_bn",
        "tso_annualised_cost_vs_build_bn",
        "eu_dso_investment_vs_build_bn",
        "eu_tso_investment_vs_build_bn",
        "enduse_twh",
        "dso_hv_lv_twh",
        "peak_dso_gw",
        "dso_stock_gw",
        "heat_pump_twh",
        "resistive_heater_twh",
        "bev_twh",
        "industry_twh",
        "rooftop_twh",
        "lv_shed_twh",
        "ev_shed_twh",
        "de_shedding_hours",
        "eu_load_shedding_twh",
        "co2_emissions_mt",
        "de_vre_curtailment_twh",
        "eu_vre_curtailment_twh",
        "elec_generation_twh",
        "dso_peak_util_pct",
        "dso_new_gw",
        "de_dso_new_overnight_bn",
    ]
    out = merged[cols].rename(
        columns={
            "enduse_twh": "de_enduse_twh",
            "dso_hv_lv_twh": "de_dso_throughput_twh",
            "peak_dso_gw": "de_peak_dso_gw",
            "dso_stock_gw": "de_dso_capacity_gw",
            "heat_pump_twh": "de_hp_twh",
            "resistive_heater_twh": "de_resistive_heating_twh",
            "bev_twh": "de_bev_twh",
            "industry_twh": "de_industrial_electricity_twh",
            "rooftop_twh": "de_rooftop_generation_twh",
            "lv_shed_twh": "de_lv_load_shedding_twh",
            "ev_shed_twh": "de_ev_shedding_twh",
            "dso_peak_util_pct": "de_dso_peak_util_pct",
            "dso_new_gw": "de_dso_new_gw",
            "de_dso_new_overnight_bn": "de_dso_new_overnight_bn",
        }
    )
    order = [m["label"] for m in RUN_META.values()]
    out["scenario"] = pd.Categorical(out["scenario"], categories=order, ordered=True)
    return out.sort_values(["year", "scenario"]).reset_index(drop=True)


def assemble_decomp(decomp: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year in (2030, 2040):
        build = decomp[(decomp["scenario"] == "Build") & (decomp["year"] == year)]
        build_map = build.set_index("category")["cost_in_objective_bn_eur_per_yr"]
        for scenario in [m["label"] for m in RUN_META.values()]:
            sub = decomp[(decomp["scenario"] == scenario) & (decomp["year"] == year)]
            delta_total = 0.0
            tmp = []
            for _, r in sub.iterrows():
                cat = r["category"]
                cost = float(r["cost_in_objective_bn_eur_per_yr"])
                base = float(build_map.get(cat, 0.0))
                delta = cost - base
                tmp.append(
                    {
                        "scenario": scenario,
                        "year": year,
                        "category": cat,
                        "expanded_capex_bn_eur_per_yr": float(r["expanded_capex_bn_eur_per_yr"]),
                        "opex_bn_eur_per_yr": float(r["opex_bn_eur_per_yr"]),
                        "cost_in_objective_bn_eur_per_yr": cost,
                        "delta_vs_build_bn_eur_per_yr": delta,
                    }
                )
                if cat != "residual_vs_objective":
                    delta_total += delta
            for rec in tmp:
                rec["share_of_delta_vs_build_pct"] = (
                    100.0 * rec["delta_vs_build_bn_eur_per_yr"] / delta_total
                    if abs(delta_total) > 1e-9
                    else 0.0
                )
                rows.append(rec)
    out = pd.DataFrame(rows)
    order = [m["label"] for m in RUN_META.values()]
    out["scenario"] = pd.Categorical(out["scenario"], categories=order, ordered=True)
    return out.sort_values(
        ["year", "scenario", "delta_vs_build_bn_eur_per_yr"],
        ascending=[True, True, False],
    ).reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--results-root", type=Path, default=Path("results/2026-grid-study"))
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "results/2026-grid-study/distribution_tariffs/german_network_tariffs"
        ),
    )
    p.add_argument(
        "--extract-csv",
        type=Path,
        default=Path(
            "results/2026-grid-study/distribution_tariffs/german_network_tariffs/pypsa_germany_extract.csv"
        ),
    )
    return p.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    extract_csv = args.extract_csv if args.extract_csv and args.extract_csv.exists() else None

    dash_raw, decomp_raw, de = collect(args.results_root, extract_csv)
    dash = assemble_dashboard(dash_raw, de)
    decomp = assemble_decomp(decomp_raw)

    p1 = args.output_dir / "scenario_dashboard.csv"
    p2 = args.output_dir / "system_cost_decomposition_vs_build.csv"
    dash.to_csv(p1, index=False, float_format="%.4f")
    decomp.to_csv(p2, index=False, float_format="%.4f")
    logger.info("Wrote %s", p1)
    logger.info("Wrote %s", p2)

    show = [
        "scenario",
        "year",
        "system_cost_bn_eur_per_yr",
        "system_cost_eur_per_mwh",
        "delta_system_cost_vs_build_bn",
        "dso_investment_vs_build_bn",
        "tso_investment_vs_build_bn",
        "de_enduse_twh",
        "de_dso_throughput_twh",
        "de_peak_dso_gw",
        "de_dso_capacity_gw",
        "de_hp_twh",
        "de_resistive_heating_twh",
        "de_bev_twh",
        "de_industrial_electricity_twh",
        "de_rooftop_generation_twh",
        "de_lv_load_shedding_twh",
        "de_shedding_hours",
        "co2_emissions_mt",
        "de_vre_curtailment_twh",
    ]
    print("\nDashboard:")
    print(dash[show].to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

    print("\nCost delta vs Build (bn €/yr), categories |delta| > 0.5:")
    big = decomp[
        (decomp["scenario"] != "Build")
        & (decomp["category"] != "residual_vs_objective")
        & (decomp["delta_vs_build_bn_eur_per_yr"].abs() > 0.5)
    ]
    print(
        big[
            [
                "scenario",
                "year",
                "category",
                "expanded_capex_bn_eur_per_yr",
                "opex_bn_eur_per_yr",
                "delta_vs_build_bn_eur_per_yr",
                "share_of_delta_vs_build_pct",
            ]
        ].to_string(index=False, float_format=lambda x: f"{x:,.2f}")
    )


if __name__ == "__main__":
    main()
