# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""
Config validation update record for PyPSA-EUR.

Any imports included in this file will be automatically registered as config updaters and applied to the base config schema.
See the docs for more details: https://pypsa-eur.readthedocs.io/en/latest/validation_dev.html#soft-fork-ext
"""

import scripts.lib.validation.config.industry_eurelectric_config  # noqa: F401
import scripts.lib.validation.config.sector_eurelectric_config  # noqa: F401
import scripts.lib.validation.config.data_center_eurelectric_config