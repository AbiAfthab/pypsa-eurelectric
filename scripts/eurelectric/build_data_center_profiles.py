# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
This rule creates load profiles for data centers across Europe by scaling the demand profile provided by UKPN
"""

import logging

import pandas as pd

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)


def build_nodal_data_center_demand(country_demand_fn, pop_layout, demand_year):
    demand_year = str(demand_year[0])
    
    # get annual energy consumption per country/node
    demand_per_ct = pd.read_csv(country_demand_fn, index_col=0, skiprows=1)
    demand_per_ct *= 1e6

    logger.warn(
        f"Missing data center demand for countries: {set(demand_per_ct.index) ^ set(pop_layout.ct)}, setting to zero."
    )

    per_node_demand = demand_per_ct[demand_year].reindex(pop_layout.ct).fillna(0.0)
    per_node_demand.index = pop_layout.index
    per_node_demand = pop_layout["fraction"] * per_node_demand
    return per_node_demand


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake("build_data_center_demand", clusters=50)
    configure_logging(snakemake)
    set_scenario_config(snakemake)

    # imagine we can replace the pop layout with a sf of data centers per node eventually.
    pop_layout = pd.read_csv(snakemake.input.clustered_pop_layout, index_col=0)

    nodal_data_center_data = build_nodal_data_center_demand(
        snakemake.input.data_center_demand_fn, pop_layout, snakemake.params.demand_year
    )
    nodal_data_center_data.to_csv(snakemake.output.data_center_demand)
