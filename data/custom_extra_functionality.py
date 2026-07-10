# SPDX-FileCopyrightText: : 2023- The PyPSA-Eur Authors
#
# SPDX-License-Identifier: MIT

import logging

import pandas as pd
import pandera.pandas as pa
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
                    checks=pa.Check.isin(
                        ["added capacity", "supplied heat", "used electricity"]
                    ),
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
            matched_links = (
                n.links.loc[matched_links].query("`p_nom_extendable` == True").index
            )

        if matched_links.empty:
            logger.info(
                f"Custom heat pump constraint "
                f"{row_id} has no Links matching the regex '{regex}' "
                f"(planning_horizon={snakemake.wildcards['planning_horizons']}, "
                f"constraint_type={constraint_type})."
            )
            continue

        # Limit the additional capacity added in the model run
        if constraint_type == "added capacity":
            lhs = n.model["Link-p_nom"].loc[matched_links].sum()

            if pd.notna(lower_bound):
                n.model.add_constraints(
                    lhs >= float(lower_bound),
                    name=f"heat_pump_additional_capacity_lower_{row_id}",
                )
            if pd.notna(upper_bound):
                n.model.add_constraints(
                    lhs <= float(upper_bound),
                    name=f"heat_pump_additional_capacity_upper_{row_id}",
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
                    lhs >= float(lower_bound),
                    name=f"heat_pump_supplied_heat_lower_{row_id}",
                )
            if pd.notna(upper_bound):
                n.model.add_constraints(
                    lhs <= float(upper_bound),
                    name=f"heat_pump_supplied_heat_upper_{row_id}",
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
                    lhs >= float(lower_bound),
                    name=f"heat_pump_used_electricity_lower_{row_id}",
                )
            if pd.notna(upper_bound):
                n.model.add_constraints(
                    lhs <= float(upper_bound),
                    name=f"heat_pump_used_electricity_upper_{row_id}",
                )

        logger.info(
            f"Added custom heat pump constraint on links for {row['constraint_type']} with regex '{row['name_regex']}' over {len(matched_links)} links for planning_horizon={snakemake.wildcards['planning_horizons']}",
        )


def custom_extra_functionality(n, snapshots, snakemake):
    """
    Add custom extra functionality constraints.
    """

    # Restrict the capacity expansion of heat pump groups
    # as well as the annual generation from heat pumps
    restrict_heat_pumps(n, snapshots, snakemake)
