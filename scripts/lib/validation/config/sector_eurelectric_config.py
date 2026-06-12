# SPDX-FileCopyrightText: Eurelectric / Contributors to PyPSA-Eur
# SPDX-License-Identifier: MIT

"""
Eurelectric transport configuration extensions for PyPSA-Eur.

This module extends the PyPSA-Eur configuration schema with Eurelectric-specific
sector options.

The ConfigUpdater pattern allows adding custom fields without modifying upstream
schema files, making it easier to merge future PyPSA-Eur updates.
"""

from pydantic import Field

from scripts.lib.validation.config._base import ConfigUpdater


class SectorEurelectricConfigUpdater(ConfigUpdater):
    """
    Config updater for Eurelectric sector configuration options.

    Extends the PyPSA-Eur schema with:
    - sector.land_transport_passenger_km_scaling: Transport demand scaling
    - sector.land_transport_truck_km_scaling: Truck transport demand scaling
    - sector.land_transport_van_km_scaling: Van transport demand scaling
    - sector.land_transport_bus_km_scaling: Bus transport demand scaling
    - sector.land_transport_fuel_shares_*: Per-country transport fuel share CSV config
    - sector.*_bev_avail_*: Class-specific BEV availability assumptions
    - sector.land_transport_*_{fuel_cell,electric,ice}_share: Segment-specific fuel shares
    - sector.transport_*_{electric,fuel_cell,ice}_efficiency: Segment-specific efficiencies
    - sector.battery_p_nom_min_*: Battery minimum installed capacity options
    """

    @property
    def name(self) -> str:
        # Return empty string to merge into the same config file as other updaters
        return ""

    @property
    def docs_url(self) -> str | None:
        return None

    def update(self):
        """Apply Eurelectric sector schema extensions."""

        # Extend SectorConfig with Eurelectric transport and battery options
        sector_config_field = self.base_config.model_fields["sector"]
        SectorConfigClass = sector_config_field.default_factory().__class__

        ExtendedSectorConfig = self._apply_updates(
            __base__=SectorConfigClass,
            __doc__="Configuration for `sector` settings with Eurelectric sector extensions.",
            land_transport_passenger_km_scaling=(
                dict[int, float],
                Field(
                    default_factory=dict,
                    description="Year-indexed scaling factors for land transport passenger-km demand. Maps planning horizon year to scaling factor (e.g., {2030: 1.03, 2040: 1.06}).",
                ),
            ),
            land_transport_truck_km_scaling=(
                dict[int, float],
                Field(
                    default_factory=dict,
                    description="Year-indexed scaling factors for land transport truck-km demand.",
                ),
            ),
            land_transport_van_km_scaling=(
                dict[int, float],
                Field(
                    default_factory=dict,
                    description="Year-indexed scaling factors for land transport van-km demand.",
                ),
            ),
            land_transport_bus_km_scaling=(
                dict[int, float],
                Field(
                    default_factory=dict,
                    description="Year-indexed scaling factors for land transport bus-km demand.",
                ),
            ),
            land_transport_fuel_shares_enable=(
                bool,
                Field(
                    False,
                    description="Enable loading per-country, per-segment land transport fuel shares from CSV.",
                ),
            ),
            land_transport_fuel_shares_file=(
                str,
                Field(
                    "data/land_transport_fuel_shares.csv",
                    description="CSV file path with per-country, per-segment land transport fuel shares.",
                ),
            ),
            pkw_bev_avail_max=(
                float,
                Field(
                    0.95,
                    description="Maximum plugged-in availability for passenger BEVs.",
                ),
            ),
            pkw_bev_avail_mean=(
                float,
                Field(
                    0.8, description="Mean plugged-in availability for passenger BEVs."
                ),
            ),
            bus_bev_avail_max=(
                float,
                Field(0.9, description="Maximum plugged-in availability for bus BEVs."),
            ),
            bus_bev_avail_mean=(
                float,
                Field(0.6, description="Mean plugged-in availability for bus BEVs."),
            ),
            hd_bev_avail_max=(
                float,
                Field(
                    0.85,
                    description="Maximum plugged-in availability for heavy-duty BEVs.",
                ),
            ),
            hd_bev_avail_mean=(
                float,
                Field(
                    0.7, description="Mean plugged-in availability for heavy-duty BEVs."
                ),
            ),
            lfw_bev_avail_max=(
                float,
                Field(
                    0.92,
                    description="Maximum plugged-in availability for light commercial BEVs.",
                ),
            ),
            lfw_bev_avail_mean=(
                float,
                Field(
                    0.7,
                    description="Mean plugged-in availability for light commercial BEVs.",
                ),
            ),
            land_transport_truck_fuel_cell_share=(
                dict[int, float],
                Field(
                    default_factory=dict,
                    description="Year-indexed truck fuel-cell transport share.",
                ),
            ),
            land_transport_truck_electric_share=(
                dict[int, float],
                Field(
                    default_factory=dict,
                    description="Year-indexed truck electric transport share.",
                ),
            ),
            land_transport_truck_ice_share=(
                dict[int, float],
                Field(
                    default_factory=dict,
                    description="Year-indexed truck ICE transport share.",
                ),
            ),
            land_transport_van_fuel_cell_share=(
                dict[int, float],
                Field(
                    default_factory=dict,
                    description="Year-indexed van fuel-cell transport share.",
                ),
            ),
            land_transport_van_electric_share=(
                dict[int, float],
                Field(
                    default_factory=dict,
                    description="Year-indexed van electric transport share.",
                ),
            ),
            land_transport_van_ice_share=(
                dict[int, float],
                Field(
                    default_factory=dict,
                    description="Year-indexed van ICE transport share.",
                ),
            ),
            land_transport_bus_fuel_cell_share=(
                dict[int, float],
                Field(
                    default_factory=dict,
                    description="Year-indexed bus fuel-cell transport share.",
                ),
            ),
            land_transport_bus_electric_share=(
                dict[int, float],
                Field(
                    default_factory=dict,
                    description="Year-indexed bus electric transport share.",
                ),
            ),
            land_transport_bus_ice_share=(
                dict[int, float],
                Field(
                    default_factory=dict,
                    description="Year-indexed bus ICE transport share.",
                ),
            ),
            transport_passenger_electric_efficiency=(
                float,
                Field(
                    53.19,
                    description="Passenger electric transport efficiency in 100 km per MWh.",
                ),
            ),
            transport_passenger_fuel_cell_efficiency=(
                float,
                Field(
                    30.003,
                    description="Passenger fuel-cell transport efficiency in 100 km per MWh_H2.",
                ),
            ),
            transport_passenger_ice_efficiency=(
                float,
                Field(
                    16.0712,
                    description="Passenger ICE transport efficiency in 100 km per MWh_fuel.",
                ),
            ),
            transport_truck_electric_efficiency=(
                float,
                Field(
                    25.0,
                    description="Truck electric transport efficiency in 100 km per MWh.",
                ),
            ),
            transport_truck_fuel_cell_efficiency=(
                float,
                Field(
                    3.565,
                    description="Truck fuel-cell transport efficiency in 100 km per MWh_H2.",
                ),
            ),
            transport_truck_ice_efficiency=(
                float,
                Field(
                    3.75,
                    description="Truck ICE transport efficiency in 100 km per MWh_fuel.",
                ),
            ),
            transport_van_electric_efficiency=(
                float,
                Field(
                    40.0,
                    description="Van electric transport efficiency in 100 km per MWh.",
                ),
            ),
            transport_van_fuel_cell_efficiency=(
                float,
                Field(
                    30.003,
                    description="Van fuel-cell transport efficiency in 100 km per MWh_H2.",
                ),
            ),
            transport_van_ice_efficiency=(
                float,
                Field(
                    15.6,
                    description="Van ICE transport efficiency in 100 km per MWh_fuel.",
                ),
            ),
            transport_bus_electric_efficiency=(
                float,
                Field(
                    25.0,
                    description="Bus electric transport efficiency in 100 km per MWh.",
                ),
            ),
            transport_bus_fuel_cell_efficiency=(
                float,
                Field(
                    3.565,
                    description="Bus fuel-cell transport efficiency in 100 km per MWh_H2.",
                ),
            ),
            transport_bus_ice_efficiency=(
                float,
                Field(
                    3.75,
                    description="Bus ICE transport efficiency in 100 km per MWh_fuel.",
                ),
            ),
            battery_p_nom_min_enable=(
                bool,
                Field(
                    False,
                    description="Enable sector-specific minimum battery power capacity constraints.",
                ),
            ),
            battery_p_nom_min_file=(
                str,
                Field(
                    "data/battery_p_nom_min.csv",
                    description="CSV file path with minimum battery power capacity requirements.",
                ),
            ),
            battery_p_nom_min_include_existing=(
                bool,
                Field(
                    True,
                    description="If true, subtract fixed existing battery capacity from the minimum requirement before applying constraints.",
                ),
            ),
        )

        return self._apply_updates(
            sector=(
                ExtendedSectorConfig,
                Field(
                    default_factory=ExtendedSectorConfig,
                    description="Sector coupling configuration.",
                ),
            ),
        )
