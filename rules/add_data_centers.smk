# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

rule add_data_centers:
    message:
        "Building data center list for {wildcards.clusters} clusters"
    params:
        custom_data_centers=config_provider("electricity", "custom_powerplants"),
        countries=config_provider("countries"),
    input:
        network=resources("networks/base_s_{clusters}.nc"),
        data_center_demand="resources/dc_loads.csv",
    output:
        network=resources("networks/base_s_{clusters}_dc.nc"),
    log:
        logs("build_powerplants_s_{clusters}.log"),
    benchmark:
        benchmarks("build_powerplants_s_{clusters}")
    threads: 1
    resources:
        mem_mb=7000,
    script:
        scripts("build_data_centers.py")