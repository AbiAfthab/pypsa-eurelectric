# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

# rule retrieve_data_center_demand_profiles:
#     message:
#         "Retrieving data center half hourly demand profiles from UKPN"
#     input:
#         xlsx=storage("https://ukpowernetworks.opendatasoft.com/api/explore/v2.1/catalog/datasets/ukpn-data-centre-demand-profiles/attachments/data_triage_data_centre_profiles_half_hourly_xlsx")
#     output:
#         xlsx="data/eurelectric_data_centers/load_profiles_half_hourly.xlsx"
#     run:
#         copy2(input['xlsx'], output['xlsx'])


rule build_data_center_demand:
    message:
        "TESTING TESTING TESTING //Creating a nodal distribution of data center demand (annualized)"
    params:
        demand_year=config_provider("scenario", "planning_horizons"),
    input:
        data_center_demand_fn="data/eurelectric_data_centers/archive/v0.1/manual/data_center_demand_projection.csv",
        clustered_pop_layout=resources("pop_layout_base_s_{clusters}.csv"),
    output:
        data_center_demand=resources(
            "eurelectric_data_centers/data_center_demand_s_{clusters}.csv"
        ),
    script:
        scripts("eurelectric/build_data_center_profiles.py")
