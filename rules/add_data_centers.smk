# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

# build out data centers analogous to the transport demand rules
# johannes to provide the osm data in the form of a list 
rule add_data_centers:
    message:
        "Building data center list for clusters and planning horizon "
    params:
        data_center=config_provider("data_center"),
    input:
        network=resources("networks/base_s_50___2050.nc"),
        data_center_demand="resources/eurelectric_data_centers/data_center_data.csv",
    output:
        network=resources("networks/base_s_50___2050_dc.nc"),
    log:
        logs("build_powerplants_s_50_2050.log"),
    benchmark:
        benchmarks("build_powerplants_s_50_2050")
    threads: 1
    resources:
        mem_mb=7000,
    script:
        scripts("eurelectric/add_data_centers.py")

rule solve_network_data_center:
    message:
        "Solving electricity network optimization for {wildcards.clusters} clusters and {wildcards.planning_horizons}"
    params:
        solving=config_provider("solving"),
        foresight=config_provider("foresight"),
        co2_sequestration_potential=config_provider(
            "sector", "co2_sequestration_potential", default=200
        ),
        custom_extra_functionality=input_custom_extra_functionality,
    input:
        network="resources/networks/base_s_{clusters}_{opts}__{planning_horizons}_dc.nc",
    output:
        network=RESULTS + "networks/base_s_{clusters}_{opts}__{planning_horizons}_dc.nc",
        config=RESULTS + "configs/config.base_s_{clusters}_elec_{opts}_{planning_horizons}.yaml",
        model=(
            RESULTS + "models/base_s_{clusters}_elec_{opts}_{planning_horizons}.nc"
            if config["solving"]["options"]["store_model"]
            else []
        ),
    log:
        solver=normpath(
            RESULTS + "logs/solve_network/base_s_{clusters}_elec_{opts}_{planning_horizons}_solver.log"
        ),
        memory=RESULTS + "logs/solve_network/base_s_{clusters}_elec_{opts}_{planning_horizons}_memory.log",
        python=RESULTS + "logs/solve_network/base_s_{clusters}_elec_{opts}_{planning_horizons}_python.log",
    benchmark:
        (RESULTS + "benchmarks/solve_network/base_s_{clusters}_elec_{opts}_{planning_horizons}")
    threads: solver_threads
    resources:
        mem_mb=memory,
        runtime=config_provider("solving", "runtime", default="6h"),
    shadow:
        shadow_config
    script:
        scripts("solve_network.py")

rule retrieve_data_center_demand_profiles:
    message:
        "Retrieving data center half hourly demand profiles from UKPN"
    input:
        xlsx=storage("https://ukpowernetworks.opendatasoft.com/api/explore/v2.1/catalog/datasets/ukpn-data-centre-demand-profiles/attachments/data_triage_data_centre_profiles_half_hourly_xlsx")
    output:
        xlsx=resources("eurelectric_data_centers/load_profiles_half_hourly.xlsx")
    run:
        copy2(input['xlsx'], output['xlsx'])

rule build_data_center_demand:
    message:
        "Creating a nodal distribution of data center demand (annualized)"
    input:
        data_center_demand=resources('eurelectric_data_centers/data_center_demand.csv'),
        clustered_pop_layout=resources("pop_layout_base_s_{clusters}.csv"),
    output:
        data_center_demand=resources('eurelectric_data_centers/data_center_demand_s_{clusters}.csv')
    script:
        scripts('eurelectric/build_data_center_profiles.py')