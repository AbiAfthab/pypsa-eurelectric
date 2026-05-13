# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
from typing import Literal

from pydantic import BaseModel, Field

from scripts.lib.validation.config._base import ConfigModel, ConfigUpdater


class _DataCenterDSRConfig(ConfigModel):
    """
    Configuration for `data_center.dsr` (demand-side response) settings.

    Industry DSR models the flexibility potential of industrial electricity loads,
    allowing load shifting within configurable time windows. Each technology or
    profile can have its own flexibility parameters.
    """

    enable: bool = Field(
        False,
        description="Enable data center electricity demand-side response modeling. When enabled, adds flexibility stores and links for each data center demand bus.",
    )
    capital_cost: float = Field(
        0.1,
        description="Capital cost for DSR flexibility stores representing the cost of providing flexibility capacity (EUR/MWh/year). Higher values reduce DSR utilization.",
    )
    marginal_cost: float = Field(0.1, description="Cost of dispatching DSR (EUR/MWh).")
    p_pct_nom: float = Field(
        0.05,
        description="Fraction of nominal load capacity that can participate in DSR.",
    )
    shift_hours: float = Field(
        6,
        description="Maximum hours that load can be shifted forward or backward.",
    )


class _DataCenterGenerationConfig(ConfigModel):
    """
    Configuration for `data_center.generation` (demand-side response) settings.

    Industry DSR models the flexibility potential of industrial electricity loads,
    allowing load shifting within configurable time windows. Each technology or
    profile can have its own flexibility parameters.
    """

    enable: bool = Field(
        False,
        description="Enable data center on site generation modeling. When enabled, adds flexibility stores and links for each data center demand bus.",
    )
    p_pct_nom: float = Field(
        0.2,
        description="Generation capacity as a fraction of the nominal capacity of the data center.",
    )
    reference_technology: str = Field(
        "OCGT",
        description="Reference technology for cost/efficiency parameters. Should be a technology that already exists in network",
    )


class _DataCenterStorageConfig(ConfigModel):
    """
    Configuration for `data_center.generation` (demand-side response) settings.

    Industry DSR models the flexibility potential of industrial electricity loads,
    allowing load shifting within configurable time windows. Each technology or
    profile can have its own flexibility parameters.
    """

    enable: bool = Field(
        False,
        description="Enable data center on site generation modeling. When enabled, adds flexibility stores and links for each data center demand bus.",
    )
    p_pct_nom: float = Field(
        0.2,
        description="Storage capacity as a fraction of the nominal capacity of the data center.",
    )
    shift_hours: float = Field(
        6,
        description="Number of hours battery is capable of full dis/charge. e.g E_battery = P_battery * shift_hours.",
    )
    reference_technology: str = Field(
        "battery",
        description="Technology to base assumptions of efficiency/cost on. (Should be pre existing in the network)",
    )


class _DataCenterLoadConfig(ConfigModel):
    profile: Literal[
        "High Voltage Import", "Low Voltage Import", "Extra High Voltage Import"
    ] = Field(
        "High Voltage Import",
        description="Data center voltage classification in UKPN data set to base profile on",
    )
    profile_year: int = Field(
        2024, description="Year of  UKPN data set to use for load profile"
    )
    method: Literal["min", "max", "mean"] = Field(
        "max",
        description="Aggregation method for data center load profiles provided by the UKPN dataset",
    )
    demand_year: int = Field(
        2030,
        description="Year of the demand data to use for annualized country level demand.",
    )


class DataCenterConfigSection(BaseModel):
    dsr: bool = Field(
        True, description="Enable/disable demand side response via data centers"
    )
    # utilization_fraction: float = Field(
    #   description="Assumed percent loading of the data centers. (If not provided in a load profile csv)"
    # )


class DataCenterEurelectricConfigUpdater(ConfigUpdater):
    """
    Config updater for Eurelectric industry configuration options.

    Extends the PyPSA-Eur schema with:
    - data_center.dsr: Data center demand-side response configuration
    - data_center.storage: Data center on site storage
    - data_center.generation: Data center on site generation
    """

    @property
    def name(self) -> str:
        # Return empty string to merge into base config.default.yaml
        return ""

    @property
    def docs_url(self) -> str | None:
        # Return None to keep using upstream PyPSA-Eur docs URL
        return None

    def update(self):
        """Apply Eurelectric-specific schema extensions for industry DSR."""

        # # Extend DataCenterConfig with DSR and temporal load option
        # data_center_config_field = self.base_config.model_fields["industry"]
        # DataCenterConfigClass = data_center_config_field.default_factory().__class__

        ExtendedDataCenterConfig = self._apply_updates(
            __base__=DataCenterConfigSection,
        )

        ExtendedDataCenterConfig = self._apply_updates(
            __base__=DataCenterConfigSection,
            __doc__="Configuration for `data center` settings with Eurelectric DSR extensions.",
            dsr=(
                _DataCenterDSRConfig,
                Field(
                    default_factory=_DataCenterDSRConfig,
                    description="Data center demand-side response (DSR) configuration for modeling load flexibility.",
                ),
            ),
            load=(
                _DataCenterLoadConfig,
                Field(
                    default_factory=_DataCenterLoadConfig,
                    description="Load data to use for data center demand",
                ),
            ),
            onsite_generation=(
                _DataCenterGenerationConfig,
                Field(
                    default_factory=_DataCenterGenerationConfig,
                    description="Data center on site generation config",
                    alias="on-site generation",
                ),
            ),
            onsite_storage=(
                _DataCenterStorageConfig,
                Field(
                    default_factory=_DataCenterStorageConfig,
                    description="Data center on site storage config",
                    alias="on-site storage",
                ),
            ),
            grid_connection=(
                Literal["Grid to data center", "Data center to grid", "Bidirectional"],
                Field(
                    "Bidirectional",
                    description="Enables power to be pushed back from the data center to grid",
                ),
            ),
        )

        # Apply industry updates to the root schema
        return self._apply_updates(
            data_center=(
                ExtendedDataCenterConfig,
                Field(
                    default_factory=ExtendedDataCenterConfig,
                    description="Data center sector configuration.",
                ),
            ),
        )
