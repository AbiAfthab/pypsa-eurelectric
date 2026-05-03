# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
This rule creates load profiles for data centers across Europe by scaling the demand profile provided by UKPN
"""

import logging

import numpy as np
import pandas as pd

import pypsa

from scripts._helpers import configure_logging, get_snapshots, set_scenario_config

logger = logging.getLogger(__name__)

def build_nodal_data_center_demand(country_demand_fn, pop_layout):
    # reset scaling factors against GB 
    demand_per_ct = pd.read_csv(country_demand_fn, index_col=0)
    demand_per_ct = demand_per_ct.assign(
        avg_demand_mw = lambda x: x['DC energy demand [TWh], in 2022'] / 8760 * 1e6
    )

    logger.warn(f"Missing data center demand for countries: {set(demand_per_ct.index) ^ set(pop_layout.ct)}")

    nodal_demand = demand_per_ct.reindex(pop_layout.ct).fillna(0.0)
    nodal_demand.index = pop_layout.index
    nodal_demand['avg_demand_mw'] = pop_layout['fraction'] * nodal_demand['avg_demand_mw']

    return nodal_demand

if __name__ == "__main__":
    # if "snakemake" not in globals():
    if True:
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake("build_data_center_demand", clusters=50)
    configure_logging(snakemake)
    set_scenario_config(snakemake)

    # imagine we can replace the pop layout with a sf of data centers per node eventually.
    pop_layout = pd.read_csv(snakemake.input.clustered_pop_layout, index_col=0)

    nodal_data_center_data = build_nodal_data_center_demand(snakemake.input.data_center_demand, pop_layout)
    nodal_data_center_data.to_csv(snakemake.output.data_center_demand)