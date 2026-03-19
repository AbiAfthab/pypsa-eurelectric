# SPDX-FileCopyrightText: Eurelectric / Contributors to PyPSA-Eur
# SPDX-License-Identifier: MIT

"""
Eurelectric data configuration extensions for PyPSA-Eur.

This module documents Eurelectric-specific data files available as alternatives
to the default PyPSA-Eur data files.

Available alternative data files:
- data/agg_p_nom_real_0.1_res_cap.csv: Capacity limits with 10% reserve capacity
- data/agg_p_nom_real_0.3_res_cap.csv: Capacity limits with 30% reserve capacity
- data/agg_p_nom_solar_cap.csv: Capacity limits with solar-focused constraints

These can be used by setting `solving.agg_p_nom_limits.file` in your config.
"""

from pydantic import Field

from scripts.lib.validation.config._base import ConfigUpdater


class DataEurelectricConfigUpdater(ConfigUpdater):
    """Config updater for Eurelectric data file documentation.

    Documents alternative data files available for:
    - solving.agg_p_nom_limits.file: Alternative capacity limit files
    """

    @property
    def name(self) -> str:
        # Return empty string to merge into base config
        return ""

    @property
    def docs_url(self) -> str | None:
        return None

    def update(self):
        """Document Eurelectric data file alternatives in solving config."""

        # Extend SolvingConfig to document alternative agg_p_nom files
        solving_config_field = self.base_config.model_fields["solving"]
        SolvingConfigClass = solving_config_field.default_factory().__class__

        # Get the agg_p_nom_limits config class
        agg_p_nom_limits_field = SolvingConfigClass.model_fields["agg_p_nom_limits"]
        AggPNomLimitsClass = agg_p_nom_limits_field.default_factory().__class__

        # Extend with updated description documenting alternatives
        ExtendedAggPNomLimitsConfig = self._apply_updates(
            __base__=AggPNomLimitsClass,
            __doc__="Configuration for `solving.agg_p_nom_limits` settings with Eurelectric alternatives.",
            file=(
                str,
                Field(
                    "data/agg_p_nom_minmax.csv",
                    description=(
                        "Reference to `.csv` file specifying per carrier generator nominal capacity "
                        "constraints for individual countries and planning horizons. "
                        "Default: `data/agg_p_nom_minmax.csv`. "
                        "Eurelectric alternatives: "
                        "`data/agg_p_nom_real_0.1_res_cap.csv` (10% reserve), "
                        "`data/agg_p_nom_real_0.3_res_cap.csv` (30% reserve), "
                        "`data/agg_p_nom_solar_cap.csv` (solar-focused)."
                    ),
                ),
            ),
        )

        ExtendedSolvingConfig = self._apply_updates(
            __base__=SolvingConfigClass,
            __doc__="Configuration for `solving` settings with Eurelectric data alternatives.",
            agg_p_nom_limits=(
                ExtendedAggPNomLimitsConfig,
                Field(
                    default_factory=ExtendedAggPNomLimitsConfig,
                    description="Aggregate capacity limits configuration with Eurelectric alternatives.",
                ),
            ),
        )

        return self._apply_updates(
            solving=(
                ExtendedSolvingConfig,
                Field(
                    default_factory=ExtendedSolvingConfig,
                    description="Solver and optimization configuration.",
                ),
            ),
        )
