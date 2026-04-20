# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
This rule adds a set of pypsa components representative of a data center with demand side 
flexibility.
"""

ENABLE_DC2G = True

import logging

import numpy as np
import pandas as pd

from scripts._helpers import configure_logging, get_snapshots, set_scenario_config

logger = logging.getLogger(__name__)

def attach_data_centers(n, load_fn):
    
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
        p_min_pu=-1*ENABLE_DC2G, 
        p_max_pu=1
    )
    
    # add onsite storage
    n.add(
        "Store", 
        name=buses, 
        suffix=" data center store", 
        bus=buses
    )
    
    # add onsite generation
    n.add(
        "Link", 
        name=buses, 
        suffix=" data center", 
        bus0=buses, 
        bus1="EU gas"
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

    n.add(
        "Store",
        name=data_center_demand_buses,
        suffix=' (DSR)',
        bus=data_center_demand_buses,
        e_cyclic=True,
        e_nom=load.max() * 0.05 # some arbitrary % of the max demand 
    )

    return n


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake("add_data_centers", clusters=50)

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    n = pypsa.Network("resources/networks/base_s_50___2050.nc")
    n = attach_data_centers(n, "resources/dc_loads.csv")

    n.export_to_netcdf(snakemake.output[0])

