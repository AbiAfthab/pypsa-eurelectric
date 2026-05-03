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

    # check for nodes where the reported demand is 0
    # add baseline demand and assign loads
    profile = pd.read_csv(load_profile_fn)
    profile.set_index('utc_timestamp', inplace=True)
    nodal_distribution = pd.read_csv(load_nodal_distribution_fn).set_index('name')
    
    load_profile = pd.DataFrame(index=n.snapshots, data={node: np.ones(len(n.snapshots)) for node in nodal_distribution.index})
    load = nodal_distribution['avg_demand_mw'] * load_profile
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
    
    n.add(
        "Link", 
        name=data_center_sites, 
        suffix=' site link', 
        bus0=buses, 
        bus1=data_center_sites, 
        p_nom=1e8,
        p_min_pu=-1*dc_to_grid, 
        p_max_pu=1
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
        p_set=load.values,
    )

    if dsr['enable']:
        n.add(
            "Store",
            name=data_center_demand_buses,
            suffix=' (DSR)',
            bus=data_center_demand_buses,
            e_cyclic=True,
            e_nom=load.max(axis=0).values * dsr['flexibility_fraction'] * dsr['shift_hours'] # some arbitrary % of the max demand 
        )

    # factor of 5 assumes the rated cap of the data center is 5x the max (max utilization ~20%)
    if storage['enable']:
        # add onsite storage
        n.add(
            "Store", 
            name=buses, 
            suffix=" data center store", 
            bus=buses,
            e_nom=load.max(axis=0).values * storage['e_nom_pu'] * 5,
            p_nom=load.max(axis=0).values * storage['p_nom_pu'] * 5,
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
            p_nom=load.max(axis=0).values * storage['p_nom_pu'] * 5, #TODO fix
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
    n = attach_data_centers(n, snakemake.input['data_center_nodal_demand'], snakemake.input['data_center_demand_profile'], **snakemake.params.data_center)
    n.links.reversed=False
    n.export_to_netcdf(snakemake.output[0])

