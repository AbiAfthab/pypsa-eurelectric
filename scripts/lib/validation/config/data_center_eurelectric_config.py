from typing import Literal

from pydantic import BaseModel, Field

from scripts.lib.validation.config._base import ConfigUpdater, ConfigModel

class _DataCenterDSRConfig(ConfigModel):
    """Configuration for `data_center.dsr` (demand-side response) settings.

    Industry DSR models the flexibility potential of industrial electricity loads,
    allowing load shifting within configurable time windows. Each technology or
    profile can have its own flexibility parameters.
    """

    enable: bool = Field(
        False,
        description="Enable data center electricity demand-side response modeling. When enabled, adds flexibility stores and links for each data center demand bus.",
    )
    store_capital_cost: float = Field(
        5.0,
        description="Capital cost for DSR flexibility stores representing the cost of providing flexibility capacity (EUR/MWh/year). Higher values reduce DSR utilization.",
    )
    # link_capital_cost: float = Field(
    #     0.0,
    #     description="Capital cost for DSR links connecting loads to flexibility stores (EUR/MW/year). Usually set to 0 as the flexibility cost is captured in store_capital_cost.",
    # )
    flexibility_fraction: float = Field(
        0.0,
        description="Fraction of load that can participate in DSR, keyed by 'profile|technology' (e.g., 'Iron & steel industry|Scrap-EAF': 0.85). Values should be between 0 and 1. Technologies not listed are assumed to have zero flexibility.",
    )
    shift_hours: float = Field(
        6,
        description="Maximum hours that load can be shifted forward or backward, keyed by 'profile|technology' (e.g., 'Iron & steel industry|Scrap-EAF': 2). Determines the energy capacity of the flexibility store relative to the load.",
    )
    min_load: float = Field(
        0.8,
        description="Minimum load constraint as fraction of baseline load (hard operational limit), keyed by 'profile|technology'. E.g., 0.70 means load can only drop to 70% of baseline. Used for processes with minimum operating requirements.",
    )

class _DataCenterGenerationConfig(ConfigModel):
    """Configuration for `data_center.generation` (demand-side response) settings.

    Industry DSR models the flexibility potential of industrial electricity loads,
    allowing load shifting within configurable time windows. Each technology or
    profile can have its own flexibility parameters.
    """

    enable: bool = Field(
        False,
        description="Enable data center on site generation modeling. When enabled, adds flexibility stores and links for each data center demand bus.",
    )
    p_nom_pu: float = Field(
        0.2,
        description="Generation capacity as a fraction of the peak demand."
    )

class _DataCenterStorageConfig(ConfigModel):
    """Configuration for `data_center.generation` (demand-side response) settings.

    Industry DSR models the flexibility potential of industrial electricity loads,
    allowing load shifting within configurable time windows. Each technology or
    profile can have its own flexibility parameters.
    """

    enable: bool = Field(
        False,
        description="Enable data center on site generation modeling. When enabled, adds flexibility stores and links for each data center demand bus.",
    )
    p_nom_pu: float = Field(
        0.2,
        description="Storage capacity as a fraction of the peak demand."
    )
    e_nom_pu: float = Field(
        0.2,
        description="Storage capacity as a fraction of the peak demand."
    )

class DataCenterConfigSection(BaseModel):
    data_center_field: str = Field("data_center")

class DataCenterEurelectricConfigUpdater(ConfigUpdater):
    """Config updater for Eurelectric industry configuration options.

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

        # Extend DataCenterConfig with DSR and temporal load option
        data_center_config_field = self.base_config.model_fields["industry"]
        DataCenterConfigClass = data_center_config_field.default_factory().__class__

        ExtendedDataCenterConfig = self._apply_updates(
            __base__=DataCenterConfigClass,
            new_section=(
                DataCenterConfigSection, 
                Field(default_factory=DataCenterConfigSection)
            ),
        )

        ExtendedDataCenterConfig = self._apply_updates(
            __base__=DataCenterConfigClass,
            __doc__="Configuration for `data center` settings with Eurelectric DSR extensions.",
            dsr=(
                _DataCenterDSRConfig,
                Field(
                    default_factory=_DataCenterDSRConfig,
                    description="Data center demand-side response (DSR) configuration for modeling load flexibility.",
                ),
            ),
            generation=(
                _DataCenterGenerationConfig,
                Field(
                    default_factory=_DataCenterGenerationConfig,
                    description="Data center on site generation config"
                ),
            ),
            storage=(
                _DataCenterStorageConfig,
                Field(
                    default_factory=_DataCenterStorageConfig,
                    description="Data center on site storage config"
                ),
            ),
            enable_dc_to_grid=(
                bool,
                Field(
                    True,
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
