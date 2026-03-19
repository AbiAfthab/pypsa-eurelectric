# SPDX-FileCopyrightText: Eurelectric / Contributors to PyPSA-Eur
# SPDX-License-Identifier: MIT

"""
Eurelectric custom configuration extensions for PyPSA-Eur.

This module extends the PyPSA-Eur configuration schema with Eurelectric-specific
options, particularly for Industry Demand-Side Response (DSR).

The ConfigUpdater pattern allows adding custom fields without modifying upstream
schema files, making it easier to merge future PyPSA-Eur updates.
"""

from typing import Any

from pydantic import Field

from scripts.lib.validation.config._base import ConfigModel, ConfigUpdater


class _IndustryDSRConfig(ConfigModel):
    """Configuration for `industry.dsr` (demand-side response) settings.

    Industry DSR models the flexibility potential of industrial electricity loads,
    allowing load shifting within configurable time windows. Each technology or
    profile can have its own flexibility parameters.
    """

    enable: bool = Field(
        False,
        description="Enable industry electricity demand-side response modeling. When enabled, adds flexibility stores and links for each configured technology/profile combination.",
    )
    store_capital_cost: float = Field(
        5.0,
        description="Capital cost for DSR flexibility stores representing the cost of providing flexibility capacity (EUR/MWh/year). Higher values reduce DSR utilization.",
    )
    link_capital_cost: float = Field(
        0.0,
        description="Capital cost for DSR links connecting loads to flexibility stores (EUR/MW/year). Usually set to 0 as the flexibility cost is captured in store_capital_cost.",
    )
    flexibility_fraction: dict[str, float] = Field(
        default_factory=dict,
        description="Fraction of load that can participate in DSR, keyed by 'profile|technology' (e.g., 'Iron & steel industry|Scrap-EAF': 0.85). Values should be between 0 and 1. Technologies not listed are assumed to have zero flexibility.",
    )
    shift_hours: dict[str, float] = Field(
        default_factory=dict,
        description="Maximum hours that load can be shifted forward or backward, keyed by 'profile|technology' (e.g., 'Iron & steel industry|Scrap-EAF': 2). Determines the energy capacity of the flexibility store relative to the load.",
    )
    restriction_time: dict[str, list[int]] = Field(
        default_factory=dict,
        description="Checkpoint hours (0-23) at which DSR stores must return to baseline state of charge, keyed by 'profile|technology'. E.g., [6, 18] creates 12-hour periods with balance requirements at 6am and 6pm. Default [] means daily balance (at midnight).",
    )
    restriction_value: float = Field(
        1.0,
        description="Maximum state of charge as fraction for DSR flexibility storage (0 to 1). Set to 1.0 to allow full utilization of shift_hours capacity.",
    )
    technology_breakdown: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Technology breakdown within each FfE profile. Maps profile name to dictionary of {technology: share}. Shares must sum to 1.0 within each profile. Use 'auto' for automatic calculation from production data.",
    )
    negative_only: dict[str, bool] = Field(
        default_factory=dict,
        description="Technologies that can only reduce load (not increase), keyed by 'profile|technology'. Set to true for processes like chlor-alkali where ramping up is not feasible. Default false = bidirectional flexibility.",
    )
    min_load: dict[str, float] = Field(
        default_factory=dict,
        description="Minimum load constraint as fraction of baseline load (hard operational limit), keyed by 'profile|technology'. E.g., 0.70 means load can only drop to 70% of baseline. Used for processes with minimum operating requirements.",
    )
    ramp_rate: dict[str, float] = Field(
        default_factory=lambda: {"default": 1.0},
        description="Ramp rate limits per hour as fraction of capacity, keyed by 'profile|technology' or 'default'. E.g., {'default': 0.5} = 50%/hour max ramp. Use 1.0 for no ramp constraint.",
    )


class IndustryEurelectricConfigUpdater(ConfigUpdater):
    """Config updater for Eurelectric industry configuration options.

    Extends the PyPSA-Eur schema with:
    - industry.dsr: Industry demand-side response configuration
    - industry.temporal_electricity_industry_load: FfE temporal profiles toggle
    - solving.options.assign_all_duals: Dual variable export
    - enable.retrieve: Data retrieval toggle
    - run.shared_cutouts: Cutout sharing toggle
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
        """Apply Eurelectric-specific schema extensions."""

        # Step 1: Extend IndustryConfig with DSR and temporal load option
        industry_config_field = self.base_config.model_fields["industry"]
        IndustryConfigClass = industry_config_field.default_factory().__class__

        ExtendedIndustryConfig = self._apply_updates(
            __base__=IndustryConfigClass,
            __doc__="Configuration for `industry` settings with Eurelectric DSR extensions.",
            dsr=(
                _IndustryDSRConfig,
                Field(
                    default_factory=_IndustryDSRConfig,
                    description="Industry demand-side response (DSR) configuration for modeling load flexibility.",
                ),
            ),
            temporal_electricity_industry_load=(
                bool,
                Field(
                    False,
                    description="Use temporally resolved electricity industry load profiles from FfE data instead of flat annual profiles.",
                ),
            ),
        )

        # Step 2: Extend SolvingOptionsConfig with assign_all_duals
        solving_config_field = self.base_config.model_fields["solving"]
        SolvingConfigClass = solving_config_field.default_factory().__class__
        options_config_field = SolvingConfigClass.model_fields["options"]
        OptionsConfigClass = options_config_field.default_factory().__class__

        ExtendedOptionsConfig = self._apply_updates(
            __base__=OptionsConfigClass,
            __doc__="Configuration for `solving.options` with Eurelectric extensions.",
            assign_all_duals=(
                bool,
                Field(
                    False,
                    description="Assign dual values for all constraints (not just binding ones). Useful for marginal price analysis.",
                ),
            ),
        )

        ExtendedSolvingConfig = self._apply_updates(
            __base__=SolvingConfigClass,
            __doc__="Configuration for `solving` settings with Eurelectric extensions.",
            options=(
                ExtendedOptionsConfig,
                Field(
                    default_factory=ExtendedOptionsConfig,
                    description="Solving options.",
                ),
            ),
        )

        # Step 3: Extend EnableConfig with retrieve
        enable_config_field = self.base_config.model_fields["enable"]
        EnableConfigClass = enable_config_field.default_factory().__class__

        ExtendedEnableConfig = self._apply_updates(
            __base__=EnableConfigClass,
            __doc__="Configuration for `enable` settings with Eurelectric extensions.",
            retrieve=(
                bool,
                Field(
                    True,
                    description="Enable data retrieval rules. Set to false to skip downloading external data.",
                ),
            ),
        )

        # Step 4: Extend RunConfig with shared_cutouts
        run_config_field = self.base_config.model_fields["run"]
        RunConfigClass = run_config_field.default_factory().__class__

        ExtendedRunConfig = self._apply_updates(
            __base__=RunConfigClass,
            __doc__="Configuration for `run` settings with Eurelectric extensions.",
            shared_cutouts=(
                bool,
                Field(
                    False,
                    description="Share atlite cutouts between runs to save disk space and computation time.",
                ),
            ),
        )

        # Step 5: Apply all updates to the root schema
        return self._apply_updates(
            industry=(
                ExtendedIndustryConfig,
                Field(
                    default_factory=ExtendedIndustryConfig,
                    description="Industry sector configuration.",
                ),
            ),
            solving=(
                ExtendedSolvingConfig,
                Field(
                    default_factory=ExtendedSolvingConfig,
                    description="Solver and optimization configuration.",
                ),
            ),
            enable=(
                ExtendedEnableConfig,
                Field(
                    default_factory=ExtendedEnableConfig,
                    description="Flags to enable/disable workflow features.",
                ),
            ),
            run=(
                ExtendedRunConfig,
                Field(
                    default_factory=ExtendedRunConfig,
                    description="Run configuration for PyPSA-EUR workflow execution.",
                ),
            ),
        )
