# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Build land transport demand per clustered model region including efficiency
improvements due to drivetrain changes, time series for electric vehicle
availability and demand-side management constraints.
"""

import logging

import numpy as np
import pandas as pd
import pypsa
import xarray as xr

from scripts._helpers import (
    configure_logging,
    generate_periodic_profiles,
    get_snapshots,
    set_scenario_config,
)

logger = logging.getLogger(__name__)


def build_nodal_transport_data(fn, pop_layout, year):
    # get numbers of car and fuel efficiency per country
    transport_data = pd.read_csv(fn, index_col=[0, 1])
    transport_data = transport_data.xs(year, level="year")

    # break number of cars down to nodal level based on population density
    nodal_transport_data = transport_data.loc[pop_layout.ct].fillna(0.0)
    nodal_transport_data.index = pop_layout.index

    nodal_transport_data["number cars"] = (
        pop_layout["fraction"] * nodal_transport_data["number cars"]
    )

    # NEW: passenger_car_pkm should be scaled to nodes (extensive)
    if "passenger_car_pkm" in nodal_transport_data.columns:
        nodal_transport_data["passenger_car_pkm"] = (
            pop_layout["fraction"] * nodal_transport_data["passenger_car_pkm"]
        )
    #hgv_mtkm should be scaled to nodes (extensive)
    if "hgv_mtkm" in nodal_transport_data.columns:
        nodal_transport_data["hgv_mtkm"] = (
            pop_layout["fraction"] * nodal_transport_data["hgv_mtkm"]
        )
    #bus million_passenger_km should be scaled to nodes (extensive)
    if "bus_mpkm" in nodal_transport_data.columns:
        nodal_transport_data["bus_mpkm"] = (
            pop_layout["fraction"] * nodal_transport_data["bus_mpkm"]
        )
    #lcv_mtkm should be scaled to nodes (extensive)
    if "lcv_mtkm" in nodal_transport_data.columns:
        nodal_transport_data["lcv_mtkm"] = (
            pop_layout["fraction"] * nodal_transport_data["lcv_mtkm"]
        )


    # passengers_per_movement is a ratio -> do NOT scale; just keep country value
    # (already mapped by .loc[pop_layout.ct])

    # fill missing fuel efficiency with average data
    nodal_transport_data.loc[
        nodal_transport_data["average fuel efficiency"] == 0.0,
        "average fuel efficiency",
    ] = transport_data["average fuel efficiency"].mean()

    # NEW: fill missing passengers_per_movement with average (if any zeros)
    if "passengers_per_movement" in nodal_transport_data.columns:
        nodal_transport_data.loc[
            nodal_transport_data["passengers_per_movement"] == 0.0,
            "passengers_per_movement",
        ] = transport_data["passengers_per_movement"].mean()

    # fill missing/zero heavy-truck load factor at nodal level
    if "hgv_t_per_movement" in nodal_transport_data.columns:
        nodal_transport_data.loc[
            nodal_transport_data["hgv_t_per_movement"] == 0.0,
            "hgv_t_per_movement",
        ] = transport_data["hgv_t_per_movement"].mean()

    # fill missing/zero bus passengers-per-movement at nodal level
    if "bus_passengers_per_movement" in nodal_transport_data.columns:
        nodal_transport_data.loc[
            nodal_transport_data["bus_passengers_per_movement"] == 0.0,
            "bus_passengers_per_movement",
        ] = transport_data["bus_passengers_per_movement"].mean()

    # fill missing/zero van load factor at nodal level
    if "lcv_t_per_movement" in nodal_transport_data.columns:
        nodal_transport_data.loc[
            nodal_transport_data["lcv_t_per_movement"] == 0.0,
            "lcv_t_per_movement",
        ] = transport_data["lcv_t_per_movement"].mean()


    return nodal_transport_data


def build_transport_demand(traffic_fn_passenger, traffic_fn_truck, nodes, nodal_transport_data):
    """
    Returns transport demand per bus in unit km driven [100 km].
    """
    # Passenger temporal profile
    traffic_passenger = pd.read_csv(
        traffic_fn_passenger, skiprows=2, usecols=["count"]
    ).squeeze("columns")

    transport_shape_passenger = generate_periodic_profiles(
        dt_index=snapshots,
        nodes=nodes,
        weekly_profile=traffic_passenger.values,
    )
    transport_shape_passenger = transport_shape_passenger / transport_shape_passenger.sum()

    #Truck temporal profile (temporary proxy using KFZ = all motor vehicles)
    # TODO: replace with dedicated Lkw truck profile when available.
    traffic_truck = pd.read_csv(
        traffic_fn_truck, skiprows=2, usecols=["count"]
    ).squeeze("columns")
    transport_shape_truck = generate_periodic_profiles(
        dt_index=snapshots,
        nodes=nodes,
        weekly_profile=traffic_truck.values,
    )
    transport_shape_truck = transport_shape_truck / transport_shape_truck.sum() 

    pkm = nodal_transport_data["passenger_car_pkm"]
    ppm = nodal_transport_data["passengers_per_movement"]
    
    # safety against division by zero
    ppm = ppm.replace(0, np.nan)
    if ppm.isna().any():
        raise ValueError("passengers_per_movement contains zero or NaN values after filling.")
    planning_year = int(pd.Index(snapshots).year[0])
    pkm_scale = options.get("land_transport_passenger_km_scaling", {}).get(planning_year, 1.0)
    pkm = pkm * float(pkm_scale)

    km_driven = pkm / ppm

    km_100km = km_driven / 100.0

    demand_passenger = transport_shape_passenger.multiply(km_100km) * nyears

    # Truck demand from HGV tonne-km and load factor
    hgv_mtkm = nodal_transport_data["hgv_mtkm"]
    truck_scale = options.get("land_transport_truck_km_scaling", {}).get(planning_year, 1.0)
    hgv_mtkm = hgv_mtkm * float(truck_scale)
    hgv_t_per_movement = nodal_transport_data["hgv_t_per_movement"].replace(0, np.nan)
    if hgv_t_per_movement.isna().any():
        raise ValueError("hgv_t_per_movement contains zero or NaN values after filling.")
    truck_movements = hgv_mtkm / hgv_t_per_movement
    truck_100km = truck_movements / 100.0
    demand_truck = transport_shape_truck.multiply(truck_100km) * nyears

    # Van demand from LCV tonne-km and load factor
    lcv_mtkm = nodal_transport_data["lcv_mtkm"]
    van_scale = options.get("land_transport_van_km_scaling", {}).get(planning_year, 1.0)
    lcv_mtkm = lcv_mtkm * float(van_scale)

    lcv_t_per_movement = nodal_transport_data["lcv_t_per_movement"].replace(0, np.nan)
    if lcv_t_per_movement.isna().any():
        raise ValueError("lcv_t_per_movement contains zero or NaN values after filling.")

    van_movements = lcv_mtkm / lcv_t_per_movement
    van_100km = van_movements / 100.0
    demand_van = transport_shape_truck.multiply(van_100km) * nyears

    # Bus demand from bus passenger-km and load factor
    bus_mpkm = nodal_transport_data["bus_mpkm"]
    bus_scale = options.get("land_transport_bus_km_scaling", {}).get(planning_year, 1.0)
    bus_mpkm = bus_mpkm * float(bus_scale)

    bus_passengers_per_movement = nodal_transport_data["bus_passengers_per_movement"].replace(
        0, np.nan
    )
    if bus_passengers_per_movement.isna().any():
        raise ValueError(
            "bus_passengers_per_movement contains zero or NaN values after filling."
        )

    bus_movements = bus_mpkm / bus_passengers_per_movement
    bus_100km = bus_movements / 100.0
    demand_bus = transport_shape_truck.multiply(bus_100km) * nyears

    demand_passenger.columns = pd.Index(demand_passenger.columns, name=None)
    demand_truck.columns = pd.Index(demand_truck.columns, name=None)
    demand_van.columns = pd.Index(demand_van.columns, name=None)
    demand_bus.columns = pd.Index(demand_bus.columns, name=None)
    transport_demand = pd.concat(
    {
        "passenger": demand_passenger,
        "truck": demand_truck,
        "van": demand_van,
        "bus": demand_bus,
    },
    axis=1,)
    return transport_demand


def transport_degree_factor(
    temperature,
    deadband_lower=15,
    deadband_upper=20,
    lower_degree_factor=0.5,
    upper_degree_factor=1.6,
):
    """
    Work out how much energy demand in vehicles increases due to heating and
    cooling.

    There is a deadband where there is no increase. Degree factors are %
    increase in demand compared to no heating/cooling fuel consumption.
    Returns per unit increase in demand for each place and time
    """

    dd = temperature.copy()

    dd[(temperature > deadband_lower) & (temperature < deadband_upper)] = 0.0

    dT_lower = deadband_lower - temperature[temperature < deadband_lower]
    dd[temperature < deadband_lower] = lower_degree_factor / 100 * dT_lower

    dT_upper = temperature[temperature > deadband_upper] - deadband_upper
    dd[temperature > deadband_upper] = upper_degree_factor / 100 * dT_upper

    return dd


def vehicle_availability_profile(fn, snapshots, nodes, avail_max, avail_mean, label):
    traffic = pd.read_csv(fn, skiprows=2, usecols=["count"]).squeeze("columns")

    avail = avail_max - (avail_max - avail_mean) * (traffic - traffic.min()) / (traffic.mean() - traffic.min()
    )

    if not avail[avail < 0].empty:
        logger.warning(
            f"The {label} weekly availability profile has negative values, which can cause infeasibility."
        )
    return generate_periodic_profiles(
        dt_index=snapshots,
        nodes=nodes,
        weekly_profile=avail.values,
    )        




def bev_dsm_profile(snapshots, nodes, options):
    dsm_week = np.zeros((24 * 7,))

    # assuming that at a certain time ("bev_dsm_restriction_time") EVs have to
    # be charged to a minimum value (defined in bev_dsm_restriction_value)
    dsm_week[(np.arange(0, 7, 1) * 24 + options["bev_dsm_restriction_time"])] = options[
        "bev_dsm_restriction_value"
    ]

    return generate_periodic_profiles(
        dt_index=snapshots,
        nodes=nodes,
        weekly_profile=dsm_week,
    )


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake("build_transport_demand", clusters=128)
    configure_logging(snakemake)
    set_scenario_config(snakemake)

    pop_layout = pd.read_csv(snakemake.input.clustered_pop_layout, index_col=0)

    nodes = pop_layout.index

    pop_weighted_energy_totals = pd.read_csv(
        snakemake.input.pop_weighted_energy_totals, index_col=0
    )

    options = snakemake.params.sector

    snapshots = get_snapshots(
        snakemake.params.snapshots, snakemake.params.drop_leap_day, tz="UTC"
    )

    n = pypsa.Network(snakemake.input.network)
    nyears = n.snapshot_weightings.generators.sum() / 8760.0

    energy_totals_year = snakemake.params.energy_totals_year
    nodal_transport_data = build_nodal_transport_data(
        snakemake.input.transport_data, pop_layout, energy_totals_year
    )

    transport_demand = build_transport_demand(
        snakemake.input.traffic_data_Pkw,
        snakemake.input.traffic_data_Bus,
        snakemake.input.traffic_data_HD,
        snakemake.input.traffic_data_LFW,
        nodes,
        nodal_transport_data,
    )

    avail_profile_pkw = vehicle_availability_profile(
        snakemake.input.traffic_data_Pkw,
        snapshots,
        nodes,
        options["pkw_bev_avail_max"],
        options["pkw_bev_avail_mean"],
        label="PKW",
    )
    
    avail_profile_bus = vehicle_availability_profile(
        snakemake.input.traffic_data_Bus,
        snapshots,
        nodes,
        options["bus_bev_avail_max"],
        options["bus_bev_avail_mean"],
        label="BUS",
    )

    avail_profile_hd = vehicle_availability_profile(
        snakemake.input.traffic_data_HD,
        snapshots,
        nodes,
        options["hd_bev_avail_max"],
        options["hd_bev_avail_mean"],
        label="HD",
    )

    avail_profile_lfw = vehicle_availability_profile(
        snakemake.input.traffic_data_LFW,
        snapshots,
        nodes,
        options["lfw_bev_avail_max"],
        options["lfw_bev_avail_mean"],
        label="LFW",
    )

    dsm_profile = bev_dsm_profile(snapshots, nodes, options)

    nodal_transport_data.to_csv(snakemake.output.transport_data)
    transport_demand.to_csv(snakemake.output.transport_demand)
    avail_profile_pkw.to_csv(snakemake.output.avail_profile_pkw)
    avail_profile_bus.to_csv(snakemake.output.avail_profile_bus)
    avail_profile_hd.to_csv(snakemake.output.avail_profile_hd)
    avail_profile_lfw.to_csv(snakemake.output.avail_profile_lfw)
    dsm_profile.to_csv(snakemake.output.dsm_profile)
