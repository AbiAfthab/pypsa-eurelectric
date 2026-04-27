# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

rule add_data_centers:
    message:
        "Building data center list for {wildcards.clusters} clusters"
    params:
        data_center=config_provider("data_center"),
    input:
        network=resources("networks/base_s_{clusters}.nc"),
        data_center_demand="resources/eurelectric_data_centers/dc_loads.csv",
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