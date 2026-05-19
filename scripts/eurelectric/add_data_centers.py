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
    method,
    profile_fn="data/eurelectric_data_centers/archive/v0.1/manual/ukpn-data-centre-demand-profiles.csv",
):
    # get annual utilization-hours (applied to all countries equally)
    demand_profile = pd.read_csv(
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
        .agg(method)
    )
    demand_profile = demand_profile.loc[str(profile_year)]

    # get rid of subhourly data since it isn't used in pypsa
    demand_profile = demand_profile[demand_profile.index.minute == 0]
    return demand_profile


def attach_data_centers(n, load_nodal_distribution_fn, params):
    load = params["load"]
    generation = params["on-site generation"]
    storage = params["on-site storage"]
    grid_connection = params["grid_connection"]
    dsr = params["dsr"]

    # all low voltage/distribution connections
    buses = n.buses[n.buses.index.str.contains("low voltage")].index

    # check for nodes where the reported demand is 0 and filter them out
    # add baseline demand and assign loads
    load_profile = get_load_profile(**load)
    utilization_hours = load_profile.sum()

    # review: particularly check if this logic is acceptable the data for the load profile is missing a few timestamps
    year_delta = int(load["profile_year"] - n.snapshots.year.min())
    load_profile.index -= pd.DateOffset(years=year_delta)
    load_profile = load_profile.resample("h").ffill()
    load_profile = load_profile.loc[n.snapshots]
    nodal_distribution = pd.read_csv(load_nodal_distribution_fn, index_col=["name"])

    load_nom = nodal_distribution / utilization_hours
    load = pd.DataFrame(
        np.outer(load_profile.values, load_nom.values),
        index=load_profile.index,
        columns=load_nom.index,
    )
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
