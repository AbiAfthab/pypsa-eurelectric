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
    """Config updater for Eurelectric sector configuration options.

    Extends the PyPSA-Eur schema with:
    - sector.land_transport_passenger_km_scaling: Transport demand scaling
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
