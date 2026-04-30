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

def build_nodal_data_center_demand(scalar_fn, pop_layout):
    # reset scaling factors against GB 
    demand_per_ct = pd.read_csv(scalar_fn, index_col=[1])
    demand_per_ct = demand_per_ct.assign(
        demand_norm_via_gb = lambda x: x['annual_data_center_e'] / demand_per_ct.loc['GB', 'annual_data_center_e']
    )

    nodal_demand = demand_per_ct.loc[pop_layout.ct].fillna(0.0)
    nodal_demand.index = pop_layout.index
    nodal_demand['annual_data_center_e'] = pop_layout['fraction'] * nodal_demand['annual_data_center_e']

    return nodal_demand[['annual_data_center_e']]

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