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

def attach_data_centers(
        n, 
        load_nodal_distribution_fn,
        load_profile_fn,
        generation, 
        storage, 
        dc_to_grid, 
        dsr
    ):
    
    # all low voltage/distribution connections
    buses = n.buses[n.buses.index.str.contains('low voltage')].index

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
    
    n.add(
        "Link", 
        name=data_center_sites, 
        suffix=' inverter', #TODO change name 
        bus0=buses, 
        bus1=data_center_sites, 
        p_nom=1e8,
        p_min_pu=-1*dc_to_grid, 
        p_max_pu=1
    )

    if storage['enable']:
        # add onsite storage
        n.add(
            "Store", 
            name=buses, 
            suffix=" data center store", 
            bus=buses,
            e_nom=['e_nom_pu'] * 100,
            p_nom=['p_nom_pu'] * 100,
        )
    
    if generation['enable']:
        # add onsite generation
        n.add(
            "Link", 
            name=buses, 
            suffix=" data center", 
            bus0="EU gas", 
            bus1=buses, 
            # bus2 co2 atmosphere
            p_nom=generation['p_nom_pu'] * 100, #TODO fix
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
        p_min_pu=-1, # TODO change to 0
        p_max_pu=1,
        p_nom=np.inf
    )


    load_profile_fn = "data/eurelectric_data_centers/low-voltage-data-center-profile.csv"
    load_nodal_distribution_fn = "resources/eurelectric_data_centers/data_center_demand_s_50.csv"
    # add baseline demand and assign loads
    profile = pd.read_csv(load_profile_fn)
    profile.set_index('utc_timestamp', inplace=True)
    nodal_distribution = pd.read_csv(load_nodal_distribution_fn)
    
    nodal_distribution.set_index('name', inplace=True)
    nodal_distribution = nodal_distribution.T
    nodal_distribution.index = ['0']
    load = profile.dot(nodal_distribution)
    load.index =  pd.to_datetime(load.index) - pd.offsets.DateOffset(years=10)
    load = load.loc[n.snapshots]
    gb_assumed_capacity = 2.2e3 # 2.2GW estimated
    n.add(
        "Load", 
        name=data_center_demand_buses, 
        bus=data_center_demand_buses, 
        p_set=load.values * gb_assumed_capacity
    )

    if dsr['enable']:
        # breakpoint()
        n.add(
            "Store",
            name=data_center_demand_buses,
            suffix=' (DSR)',
            bus=data_center_demand_buses,
            e_cyclic=True,
            e_nom=load.max(axis=0).values * dsr['flexibility_fraction'] * dsr['shift_hours'] # some arbitrary % of the max demand 
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
    n = attach_data_centers(n, snakemake.input['data_center_nodal_demand'], snakemake.input['data_center_demand_profile'], **snakemake.params.data_center)
    n.links.reversed=False
    n.export_to_netcdf(snakemake.output[0])

