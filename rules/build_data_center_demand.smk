# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT


rule build_data_center_demand:
    message:
        "Creating a nodal distribution of data center demand (annualized) for {wildcards.clusters} clusters, {wildcards.planning_horizons} planning horizons"
    params:
        demand_year=config_provider("scenario", "planning_horizons"),
    input:
        data_center_demand_fn="data/eurelectric_data_centers/manual/v0.1/demand_projection.csv",
        clustered_pop_layout=resources("pop_layout_base_s_{clusters}.csv"),
    output:
        data_center_demand=resources(
            "data_center/demand_s_{clusters}_{planning_horizons}.csv"
        ),
    script:
        scripts("eurelectric/build_data_center_demand.py")
