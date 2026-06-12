# SPDX-FileCopyrightText: Eurelectric / Contributors to PyPSA-Eur
# SPDX-License-Identifier: MIT

"""
Eurelectric transport configuration extensions for PyPSA-Eur.

This module extends the PyPSA-Eur configuration schema with Eurelectric-specific
transport options.

The ConfigUpdater pattern allows adding custom fields without modifying upstream
schema files, making it easier to merge future PyPSA-Eur updates.
"""

from pydantic import Field

from scripts.lib.validation.config._base import ConfigUpdater


class TransportEurelectricConfigUpdater(ConfigUpdater):
    """Config updater for Eurelectric transport configuration options.

    Extends the PyPSA-Eur schema with:
    - sector.land_transport_passenger_km_scaling: Transport demand scaling
    """

    @property
    def name(self) -> str:
        # Return empty string to merge into the same config file as other updaters
        return ""

    @property
    def docs_url(self) -> str | None:
        return None

    def update(self):
        """Apply Eurelectric transport schema extensions."""

        # Extend SectorConfig with land_transport_passenger_km_scaling
        sector_config_field = self.base_config.model_fields["sector"]
        SectorConfigClass = sector_config_field.default_factory().__class__

        ExtendedSectorConfig = self._apply_updates(
            __base__=SectorConfigClass,
            __doc__="Configuration for `sector` settings with Eurelectric transport extensions.",
            land_transport_passenger_km_scaling=(
                dict[int, float],
                Field(
                    default_factory=dict,
                    description="Year-indexed scaling factors for land transport passenger-km demand. Maps planning horizon year to scaling factor (e.g., {2030: 1.03, 2040: 1.06}).",
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
