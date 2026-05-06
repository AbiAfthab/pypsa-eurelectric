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

import pypsa

from scripts._helpers import configure_logging, get_snapshots, set_scenario_config

logger = logging.getLogger(__name__)

def get_load_profile(
        profile='High Voltage Import',
        year='2024',
        method='max',
        profile_fn="data/eurelectric_data_centers/ukpn-data-centre-demand-profiles.csv" 
    ):
    # get annual utilization-hours (applied to all countries equally)
    demand_profile = pd.read_csv(profile_fn, parse_dates=['utc_timestamp'], index_col=['utc_timestamp', 'cleansed_voltage_level', 'anonymised_data_centre_name'])
    demand_profile = demand_profile.xs(profile, level='cleansed_voltage_level').groupby(level='utc_timestamp').agg(method)
    demand_profile = demand_profile.loc[str(year)]
    
    # get rid of subhourly data since it isn't used in pypsa 
    demand_profile = demand_profile[demand_profile.index.minute == 0]
    return demand_profile['hh_utilisation_ratio']

def attach_data_centers(
        n, 
        load_nodal_distribution_fn,
        generation, 
        storage,
        load_params,
        grid_connection, 
        dsr
    ):
    
    # all low voltage/distribution connections
    buses = n.buses[n.buses.index.str.contains('low voltage')].index

    # check for nodes where the reported demand is 0 and filter them out
    # add baseline demand and assign loads
    load_profile = get_load_profile(**load_params)
    utilization_hours = load_profile.sum()
    
    # review: particularly check if this logic is acceptable the data for the load profile is missing a few timestamps
    year_delta = int(load_params['year'] - n.snapshots.year.min())
    load_profile = load_profile.groupby(level=0).mean()
    load_profile.index += pd.DateOffset(years=year_delta)
    load_profile = load_profile.loc[n.snapshots]
    load_profile = load_profile.ffill()
    nodal_distribution = pd.read_csv(load_nodal_distribution_fn, index_col=['name'])
    
    load_nom = nodal_distribution['total_demand_mwh'] / utilization_hours
    load = load_nom * load_profile
    zero_cols = load.columns[(load == 0).all()]
    load = load.drop(zero_cols, axis=1)
    buses = buses[~buses.str.startswith(tuple(zero_cols))]
    
    # add main bus to contain data center demand
    n.add(
        "Bus", 
        name=buses, 
        suffix=" data center site", 
        carrier="low voltage",
        location=buses,
        unit='MWh_el'
    )
    data_center_sites = n.buses[n.buses.index.str.contains('data center site')].index
    
    dc_to_grid = True
    grid_to_dc = True 
    if grid_connection.lower() == 'grid to data center':
        dc_to_grid = False 
    elif grid_connection.lower() == 'data center to grid':
        grid_to_dc = False

    n.add(
        "Link", 
        name=data_center_sites, 
        suffix=' site link', 
        bus0=buses, 
        bus1=data_center_sites, 
        p_nom=1e8,
        p_min_pu=-1*dc_to_grid, 
        p_max_pu=1*grid_to_dc
    )

    # add second bus to constrain the demand (including any feedback from DSR) to be positive
    n.add(
        "Bus", 
        name=buses, 
        suffix=" data center demand", 
        carrier="low voltage",
        location=buses,
        unit='MWh_el'
    )
    data_center_demand_buses = n.buses[n.buses.index.str.contains('data center demand')].index

    n.add(
        "Link",
        name=data_center_sites,
        suffix=' demand link',
        bus0=data_center_sites,
        bus1=data_center_demand_buses,
        p_min_pu=0,
        p_max_pu=1,
        p_nom=np.inf
    )
    
    n.add(
        "Load", 
        name=data_center_demand_buses, 
        bus=data_center_demand_buses, 
        p_nom=load_nom.values,
        p_set=load.values,
    )

    if dsr['enable']:
        n.add(
            "Store",
            name=data_center_demand_buses,
            suffix=' (DSR)',
            bus=data_center_demand_buses,
            e_cyclic=True,
            e_nom=load_nom.values * dsr['p_pct_nom'] * dsr['shift_hours'] 
        )

    if storage['enable']:
        # add onsite storage
        n.add(
            "Store", 
            name=buses, 
            suffix=" data center store", 
            bus=buses,
            e_nom=load_nom.values * storage['p_pct_nom'] * storage['shift_hours'],
            p_nom=load_nom.values * storage['p_pct_nom'],
        )
    
    if generation['enable']:
        # add onsite generation
        n.add(
            "Link", 
            name=buses, 
            suffix=" data center OCGT", 
            bus0="EU gas", 
            bus1=buses, 
            efficiency=0.43,
            bus2='co2 atmosphere',
            efficiency2=0.198,
            p_nom=load.max(axis=0).values * storage['p_pct_nom'], #TODO fix
            marginal_cost=2.584773,
            carrier="OCGT"
        )

    return n

if __name__ == "__main__":
    # if "snakemake" not in globals():
    if True:
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake("add_data_centers", clusters=50)

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    n = pypsa.Network(snakemake.input['network'])
    n = attach_data_centers(
            n, 
            load_nodal_distribution_fn=snakemake.input['data_center_nodal_demand'], 
            generation=snakemake.params.data_center['on-site generation'],
            storage=snakemake.params.data_center['on-site storage'],
            dsr=snakemake.params.data_center['dsr'],
            load_params=snakemake.params.data_center['load'],
            grid_connection=snakemake.params.data_center['grid_connection']
        )
    n.links.reversed=False
    n.export_to_netcdf(snakemake.output[0])

