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
        load_fn, 
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
        carrier="DC"
    )
    data_center_sites = n.buses[n.buses.index.str.contains('data center site')].index
    
    n.add(
        "Link", 
        name=data_center_sites, 
        suffix=' inverter', 
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
            bus0=buses, 
            bus1="EU gas",
            p_nom=generation['p_nom_pu'] * 100, #TODO fix
        )

    # add second bus to constrain the demand (including any feedback from DSR) to be positive
    n.add(
        "Bus", 
        name=buses, 
        suffix=" data center demand", 
        carrier="DC"
    )
    data_center_demand_buses = n.buses[n.buses.index.str.contains('data center demand')].index

    n.add(
        "Link",
        name=data_center_sites,
        suffix=' demand link',
        bus0=data_center_sites,
        bus1=data_center_demand_buses,
        p_min_pu=0,
        p_max_pu=1
    )

    # add baseline demand and assign loads
    load = pd.read_csv(load_fn)
    load = load.drop(load.filter(regex='Unnamed').columns, axis=1)
    load.set_index('snapshot', inplace=True)
    n.add(
        "Load", 
        name=data_center_demand_buses, 
        bus=data_center_demand_buses, 
        p_set=load.values
    )

    if dsr['enable']:
        n.add(
            "Store",
            name=data_center_demand_buses,
            suffix=' (DSR)',
            bus=data_center_demand_buses,
            e_cyclic=True,
            e_nom=load.max(axis=1) * dsr['flexibility_fraction'] * dsr['shift_hours'] # some arbitrary % of the max demand 
        )

    return n


if __name__ == "__main__":
    # if "snakemake" not in globals():
    if True:
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake("add_data_centers", clusters=50)

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    n = pypsa.Network("resources/networks/base_s_50___2050.nc")
    n = attach_data_centers(n, "resources/eurelectric_data_centers/dc_loads.csv", **snakemake.params.data_center)

    n.export_to_netcdf(snakemake.output[0])

