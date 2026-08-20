# SPDX-FileCopyrightText: : 2023- The PyPSA-Eur Authors
#
# SPDX-License-Identifier: MIT

import logging
import os
from pathlib import Path

import pandera.pandas as pa
import pandas as pd
import xarray as xr

logger = logging.getLogger(__name__)

def restrict_heat_pumps(n, snapshots, snakemake):
    """
    Add custom Link constraints from a CSV file.

    CSV columns:
    - planning_horizon: e.g. 2030, 2040
    - name_regex: regex applied to Link component names
    - constraint_type: p_nom or energy
    - lower: lower bound (MW for p_nom, MWh for energy)
    - upper: upper bound (MW for p_nom, MWh for energy)

    Notes:
    - For 'added capacity' constraints, links are filtered to extendable only.
    - For 'supplied heat' constraints, extendability is ignored.
    - For 'used electricity' constraints, extendability is ignored.
    - If no links match a rule, a hard error is raised.
    """

    def _read_heat_pump_bounds(path: str, planning_horizon: int):
        """
        Read heat pump bounds from a CSV file and validate the schema.

        Parameters
        ----------
        path : str
            Path to the CSV file containing heat pump bounds.
        planning_horizon : int
            The planning horizon year to filter the bounds.
        """

        # Read input file with specific constraints
        df = pd.read_csv(path, dtype=str, comment="#", skip_blank_lines=True)

        schema = pa.DataFrameSchema(
            {
                "planning_horizon": pa.Column(int, nullable=False, regex=r"^\d{4}$"),
                "name_regex": pa.Column(str, nullable=False, regex=r".+"),
                "constraint_type": pa.Column(
                    str,
                    nullable=False,
                    checks=pa.Check.isin(["added capacity", "supplied heat", "used electricity"]),
                ),
                "lower": pa.Column(float, nullable=True),
                "upper": pa.Column(float, nullable=True),
            },
            checks=[
                pa.Check(
                    lambda df: df[["lower", "upper"]].notna().any(axis=1),
                    name="lower_or_upper_required",
                    error="At least one of 'lower' or 'upper' must be non-NaN.",
                )
            ],
            coerce=True,
        )

        df = schema.validate(df)

        df = df[df["planning_horizon"] == planning_horizon]

        return df

    bounds = _read_heat_pump_bounds(
        path=snakemake.input["heat_pump_bounds"],
        planning_horizon=int(snakemake.wildcards["planning_horizons"]),
    )

    # Fast return: No constraints to apply
    if bounds.empty:
        logger.info(
            f"Custom heat pump constraints activated, but no constraints defined in "
            f"{snakemake.input['heat_pump_bounds']} for planning_horizon={snakemake.wildcards['planning_horizons']}. "
            f"Skipping adding of additional constraints."
        )
        return

    # Each row can correspond to one lower and one upper constraint
    for row_id, row in bounds.iterrows():

        constraint_type = row["constraint_type"]

        lower_bound = row["lower"]
        upper_bound = row["upper"]
        
        # Find the affected links using regex on the name
        regex = row["name_regex"]
        matched_links = n.links.filter(regex=regex, axis="index").index

        # Apply this constraint only to extendable links
        # non-extendable links are not covered, because they do not have corresponding linopy variables
        if constraint_type == "added capacity":
            matched_links = n.links.loc[matched_links].query("`p_nom_extendable` == True").index

        if matched_links.empty:
            logger.debug(f"Custom heat pump constraint "
                         f"{row_id} has no Links matching the regex '{regex}' "
                         f"(planning_horizon={snakemake.wildcards['planning_horizons']}, "
                         f"constraint_type={constraint_type}).")


        # Limit the additional capacity added in the model run
        if constraint_type == "added capacity":

            lhs = n.model["Link-p_nom"].loc[matched_links].sum()

            if pd.notna(lower_bound):
                n.model.add_constraints(
                    lhs >= float(lower_bound), name=f"heat_pump_additional_capacity_lower_{row_id}"
                )
            if pd.notna(upper_bound):
                n.model.add_constraints(
                    lhs <= float(upper_bound), name=f"heat_pump_additional_capacity_upper_{row_id}"
                )

        elif constraint_type == "supplied heat":

            links_p = n.model["Link-p"].sel(name=matched_links)
            weightings = xr.DataArray(
                n.snapshot_weightings.loc[snapshots, "generators"],
                dims=["snapshot"],
                coords={"snapshot": snapshots},
            )

            # Use -p0 convention for delivered energy accounting.
            lhs = (-links_p * weightings).sum(["snapshot", "name"])

            if pd.notna(lower_bound):
                n.model.add_constraints(
                    lhs >= float(lower_bound), name=f"heat_pump_supplied_heat_lower_{row_id}"
                )
            if pd.notna(upper_bound):
                n.model.add_constraints(
                    lhs <= float(upper_bound), name=f"heat_pump_supplied_heat_upper_{row_id}"
                )
        elif constraint_type == "used electricity":
            
            # Link-p is p0, which is negative and heat provided in the model, so account for efficiency as well to get the electricity used
            links_p = n.model["Link-p"].sel(name=matched_links)
            weightings = xr.DataArray(
                n.snapshot_weightings.loc[snapshots, "generators"],
                dims=["snapshot"],
                coords={"snapshot": snapshots},
            )
            efficiency = n.get_switchable_as_dense("Link", "efficiency")[matched_links]

            # Use p0 convention for electricity used accounting.
            lhs = (-links_p * weightings * efficiency).sum(["snapshot", "name"])

            if pd.notna(lower_bound):
                n.model.add_constraints(
                    lhs >= float(lower_bound), name=f"heat_pump_used_electricity_lower_{row_id}"
                )
            if pd.notna(upper_bound):
                n.model.add_constraints(
                    lhs <= float(upper_bound), name=f"heat_pump_used_electricity_upper_{row_id}"
                )

        logger.info(
            f"Added custom heat pump constraint on links for {row['constraint_type']} with regex '{row['name_regex']}' over {len(matched_links)} links for planning_horizon={snakemake.wildcards['planning_horizons']}",
        )


def restrict_distribution_grid_investment(n, snapshots, snakemake):
    """
    Cap annualised distribution-grid investment for grid-study scenarios.

    Reads the annual investment budget (in bn EUR/year) from
    ``config["grid_study"]["distribution_grid_budget_bn_per_year"]``. The value
    may take three forms:

    * ``None`` (or unset): no constraint is added and the distribution grid
      expands freely (the "Build" scenario).
    * a scalar (int/float): the same cap is applied in every planning horizon.
    * a mapping ``{year: budget}``: a per-horizon trajectory. This is the usual
      form for myopic runs, where the cost-optimal investment differs strongly
      between horizons (e.g. 2030 vs. the incremental 2040 build). Years absent
      from the mapping - or explicitly set to ``null`` - are left uncapped.

    When a cap applies, total annualised capital expenditure on extendable
    ``electricity distribution grid`` links is limited to the budget:

        sum_over_links(Link-p_nom [MW] * capital_cost [EUR/MW/yr]) <= budget [EUR/yr]

    In myopic runs the previously-built grid is carried forward as fixed
    (non-extendable) capacity, so the cap bites only on the capacity ADDED in
    the horizon being solved.

    Both scenarios keep identical (normal) technology costs, so the resulting
    objective difference is a genuine system consequence of the investment
    restriction rather than an artefact of a cost multiplier.
    """

    budget_cfg = snakemake.config.get("grid_study", {}).get(
        "distribution_grid_budget_bn_per_year"
    )

    if budget_cfg is None:
        logger.info("grid_study: no distribution-grid investment budget applied.")
        return

    # Resolve the budget for the horizon currently being solved.
    if isinstance(budget_cfg, dict):
        year = snakemake.wildcards["planning_horizons"]
        # YAML parses bare years as ints; the wildcard is a string - try both.
        budget_bn = budget_cfg.get(int(year), budget_cfg.get(str(year)))
        if budget_bn is None:
            logger.info(
                "grid_study: no distribution-grid investment budget for "
                "planning_horizon=%s; leaving grid uncapped this horizon.",
                year,
            )
            return
    else:
        budget_bn = budget_cfg

    grid_links = n.links.index[
        (n.links.carrier == "electricity distribution grid") & n.links.p_nom_extendable
    ]

    if grid_links.empty:
        raise ValueError(
            "grid_study: no extendable 'electricity distribution grid' links found."
        )

    p_nom = n.model["Link-p_nom"].loc[grid_links]

    if len(p_nom.dims) != 1:
        raise ValueError(
            "grid_study: expected Link-p_nom selection to be one-dimensional, "
            f"but found dimensions {p_nom.dims}."
        )

    link_dim = p_nom.dims[0]

    capital_cost = xr.DataArray(
        n.links.loc[grid_links, "capital_cost"].to_numpy(),
        dims=[link_dim],
        coords={link_dim: p_nom.coords[link_dim]},
    )

    annual_investment = (p_nom * capital_cost).sum()

    n.model.add_constraints(
        annual_investment <= float(budget_bn) * 1e9,
        name="distribution_grid_investment_budget",
    )

    logger.info(
        "grid_study: distribution-grid annualised investment capped at %.3f bn EUR/yr.",
        float(budget_bn),
    )


def custom_extra_functionality(n, snapshots, snakemake):
    """
    Add custom extra functionality constraints.
    """

    # Restrict the capacity expansion of heat pump groups
    # as well as the annual generation from heat pumps
    restrict_heat_pumps(n, snapshots, snakemake)

    # Cap annualised distribution-grid investment (grid-study scenarios only;
    # no-op unless config["grid_study"]["distribution_grid_budget_bn_per_year"] is set)
    restrict_distribution_grid_investment(n, snapshots, snakemake)
