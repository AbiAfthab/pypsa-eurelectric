# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
This rule adds a set of pypsa components representative of a data center with demand side
flexibility.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def get_load_profile(
    profile,
    profile_year,
    profile_fn,
):
    # get annual utilization-hours (applied to all countries equally)
    df = pd.read_csv(
        profile_fn,
        parse_dates=["utc_timestamp"],
        index_col=[
            "utc_timestamp",
            "cleansed_voltage_level",
            "anonymised_data_centre_name",
        ],
    )
    demand_profile = (
        demand_profile.xs(profile, level="cleansed_voltage_level")[
            "hh_utilisation_ratio"
        ]
        .groupby(level="utc_timestamp")
        .agg("mean")
    )
    demand_profile = demand_profile.loc[str(profile_year)]

    # Get rid of subhourly data by resampling to hourly with averaging
    demand_profile = demand_profile.resample("h").mean()
    
    return demand_profile


def attach_data_centers(n, load_nodal_distribution_fn, profile_fn, params):
    load = params["load"]
    generation = params["on-site generation"]
    storage = params["on-site storage"]
    grid_connection = params["grid_connection"]
    dsr = params["dsr"]

    # all low voltage/distribution connections
    buses = n.buses[n.buses.index.str.contains("low voltage")].index

    # add baseline demand and assign loads
    load_profile = get_load_profile(profile_fn=profile_fn, **load)
    utilization_hours = load_profile.sum().sum()

    # review: particularly check if this logic is acceptable the data for 
    # the load profile is missing a few timestamps
    year_delta = int(load["profile_year"] - n.snapshots.year.min())
    # Drop leap day if it exists in the load profile but not in the target snapshots
    # TODO should better use the config entry here for full consistency
    if load_profile.index.is_leap_year.any() and not n.snapshots.is_leap_year.any():
        load_profile = load_profile.loc[~((load_profile.index.month == 2) & (load_profile.index.day == 29))]
    load_profile.index -= pd.DateOffset(years=year_delta)
    load_profile = load_profile.reindex(n.snapshots, method="nearest")
    nodal_distribution = pd.read_csv(load_nodal_distribution_fn, index_col=["name"])

    load_nom = nodal_distribution / utilization_hours
    load = pd.DataFrame(
        np.outer(load_profile.values, load_nom.values),
        index=load_profile.index,
        columns=load_nom.index,
    )

    # remove assest where the data center demand is zero
    zero_cols = load.columns[(load == 0).all()]
    load = load.drop(zero_cols, axis=1)
    load_nom = load_nom.drop(zero_cols, axis=0)
    buses = buses[~buses.str.startswith(tuple(zero_cols))]

    # add main bus to contain data center demand
    n.add(
        "Bus",
        name=buses,
        suffix=" data center site",
        carrier="low voltage",
        location=buses,
        unit="MWh_el",
    )
    data_center_sites = n.buses[n.buses.index.str.contains("data center site")].index

    dc_to_grid = True
    grid_to_dc = True
    if grid_connection.lower() == "grid to data center":
        dc_to_grid = False
    elif grid_connection.lower() == "data center to grid":
        grid_to_dc = False

    n.add(
        "Link",
        name=data_center_sites,
        suffix=" site link",
        bus0=buses,
        bus1=data_center_sites,
        p_nom=1e8,
        p_min_pu=-1 * dc_to_grid,
        p_max_pu=1 * grid_to_dc,
    )

    # add second bus to constrain the demand (including any feedback from DSR) to be positive
    n.add(
        "Bus",
        name=buses,
        suffix=" data center demand",
        carrier="low voltage",
        location=buses,
        unit="MWh_el",
    )
    data_center_demand_buses = n.buses[
        n.buses.index.str.contains("data center demand")
    ].index

    n.add(
        "Link",
        name=data_center_sites,
        suffix=" demand link",
        bus0=data_center_sites,
        bus1=data_center_demand_buses,
        p_min_pu=0,
        p_max_pu=1,
        p_nom=np.inf,
    )

    n.add(
        "Load",
        name=data_center_demand_buses,
        bus=data_center_demand_buses,
        # p_nom=load_nom.values,
        p_set=load.values,
    )

    if dsr["enable"]:
        n.add(
            "Store",
            name=data_center_demand_buses,
            suffix=" (DSR)",
            bus=data_center_demand_buses,
            e_cyclic=True,
            e_nom=load_nom.values.flatten() * dsr["p_pct_nom"] * dsr["shift_hours"],
            capital_cost=dsr["capital_cost"],
            marginal_cost=dsr["marginal_cost"],
        )

    # add onsite storage
    if storage["enable"]:
        ref_stores = n.stores[n.stores.carrier == storage["reference_technology"]]

        n.add(
            "Store",
            name=buses,
            suffix=" data center store",
            bus=buses,
            e_nom=load_nom.values.flatten()
            * storage["p_pct_nom"]
            * storage["shift_hours"],
            p_nom=load_nom.values.flatten() * storage["p_pct_nom"],
            marginal_cost=ref_stores["marginal_cost"],
            capital_cost=ref_stores["capital_cost"],
            carrier=storage["reference_technology"],
        )

    # add onsite generation
    if generation["enable"]:
        ref_generators = n.links[n.links.carrier == generation["reference_technology"]]

        n.add(
            "Link",
            name=buses,
            suffix=" data center OCGT",
            bus0="EU gas",
            bus1=buses,
            efficiency=ref_generators["efficiency"].mean(),
            bus2="co2 atmosphere",
            efficiency2=ref_generators["efficiency2"].mean(),
            p_nom=load_nom.values.flatten() * generation["p_pct_nom"],
            marginal_cost=ref_generators["marginal_cost"].mean(),
            capital_cost=ref_generators["capital_cost"],
            carrier=generation["reference_technology"],
        )

    return
