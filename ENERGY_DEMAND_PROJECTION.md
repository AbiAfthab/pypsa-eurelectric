# Energy Demand Sources and Future Projections in PyPSA-EUr

## Energy Demand Data Sources

### Primary Sources

1. **JRC IDEES (Institute for Energy and Transport)**
   - **Source**: Joint Research Centre - IDEES database
   - **URL**: https://joint-research-centre.ec.europa.eu/potencia-policy-oriented-tool-energy-and-climate-change-impact-assessment/jrc-idees_en
   - **Data years**: Typically 2015 or 2021
   - **Contains**:
     - Industrial production data per country and sector
     - Industrial energy consumption by sector (iron & steel, cement, chemicals, etc.)
     - Heat demand per country (residential and services)
     - Transport energy consumption
     - Residential and services energy consumption
     - Process emissions from industry

2. **Eurostat Energy Balances**
   - **Source**: Eurostat (European Statistical Office)
   - **URL**: https://ec.europa.eu/eurostat/data/database
   - **Used for**:
     - Energy balances for non-EU28 countries
     - Rescaling JRC IDEES data to match Eurostat totals
     - Filling gaps for countries not covered by JRC IDEES
     - CO2 emissions calculations from fuel consumption

3. **Eurostat Household Balances**
   - **Dataset**: `nrg_d_hhq` (Energy consumption in households)
   - **Contains**: Disaggregated household energy consumption by end-use

### Data Processing Flow

The energy demand data goes through the following processing steps:

1. **`build_energy_totals.py`**: 
   - Combines data from JRC IDEES, Eurostat, and Swiss data sources
   - Creates country-level energy totals by sector and year
   - Rescales IDEES data using Eurostat ratios (see `rescale_idees_from_eurostat()`)
   - Output: `resources/<run_name>/energy_totals.csv`

2. **`build_population_weighted_energy_totals.py`**:
   - Distributes country-level energy demands to network nodes based on population
   - Output: `resources/<run_name>/pop_weighted_energy_totals_s_{clusters}.csv`

3. **`build_heat_totals.py`** (for heat demand):
   - Approximates heat demand for different weather years using HDD regression
   - Uses polynomial regression of heat demand on Heating Degree Days (HDD)
   - Output: `resources/<run_name>/heat_totals.csv`

## Future Demand Projections (2030, 2040, etc.)

### General Approach

**Important**: PyPSA-EUr does NOT automatically scale energy demand to future years. Instead:

1. **Base Year Configuration**: 
   - The configuration parameter `energy.energy_totals_year` (default: 2019) specifies which year's energy totals to use
   - This year's demand data is used for ALL planning horizons (2030, 2040, 2050, etc.)
   - Location: `config/config.default.yaml` → `energy.energy_totals_year: 2019`

2. **No Automatic Scaling**: 
   - The model assumes the same total energy demand for future years as the base year
   - This is a "greenfield" or "overnight" approach where the system is rebuilt to meet the same demand level

### Sector-Specific Projections

However, some sectors DO have future projections:

#### 1. Industrial Production

**Script**: `build_industrial_production_per_country_tomorrow.py`

**Base Production**: 
- Industrial production is first calculated from JRC IDEES data for the **reference year** (default: 2019, configurable via `industry.reference_year`)
- This base production is stored in `industrial_production_per_country.csv`

**Future Production Method**: 
The script takes the **base production from the reference year** and redistributes it between primary and secondary (recycled) production. **Important: Total production quantities remain the same as the reference year** - only the production method mix changes.

- **Steel production**:
  - Total steel production stays constant (sum of Integrated steelworks + Electric arc)
  - `St_primary_fraction`: Fraction of steel from primary production (more energy-intensive)
  - `DRI_fraction`: Fraction of primary steel from DRI (Direct Reduced Iron) plants
  - Production is redistributed: primary vs. secondary (recycling), but total stays the same
  
- **Aluminium production**:
  - Total aluminium production stays constant (sum of primary + secondary)
  - `Al_primary_fraction`: Fraction of aluminium from primary production
  - Production is redistributed between primary and secondary, but total stays the same
  
- **High Value Chemicals (HVC)**:
  - Base HVC production is from reference year
  - `HVC_primary_fraction`: Fraction from primary production (reduces primary HVC)
  - `HVC_mechanical_recycling_fraction`: Fraction from mechanical recycling (adds new category)
  - `HVC_chemical_recycling_fraction`: Fraction from chemical recycling (adds new category)
  - **Note**: Total HVC production may change slightly because: Total = primary + mechanical + chemical = base_HVC × (primary_fraction + mechanical_fraction + chemical_fraction)
  - In 2020: 0.88 + 0.12 + 0.0 = 1.0 (same)
  - In 2050: 0.4 + 0.30 + 0.20 = 0.9 (slightly reduced)

**Key Point**: **Total production quantities remain the same as the reference year (2019)** - the model does NOT assume production growth or reduction. Only the production method mix (primary vs. secondary/recycling) changes.

**Configuration - Technology Shares**: You can configure all these technology adoption shares in `config/config.default.yaml` under the `industry` section. These are year-dependent values that you can modify:

```yaml
industry:
  reference_year: 2019  # Base year for industrial production
  
  # Steel production technology shares
  St_primary_fraction:      # Share of steel from primary production (vs. recycling)
    2020: 0.6
    2025: 0.55
    2030: 0.5
    2035: 0.45
    2040: 0.4
    2045: 0.35
    2050: 0.3
  DRI_fraction:             # Share of primary steel from DRI (Direct Reduced Iron) technology
    2020: 0
    2025: 0
    2030: 0.05
    2035: 0.2
    2040: 0.4
    2045: 0.7
    2050: 1
  
  # Aluminium production technology shares
  Al_primary_fraction:      # Share of aluminium from primary production (vs. recycling)
    2020: 0.4
    2025: 0.375
    2030: 0.35
    2035: 0.325
    2040: 0.3
    2045: 0.25
    2050: 0.2
  
  # High Value Chemicals (HVC) production technology shares
  HVC_primary_fraction:     # Share from primary production (crude oil/Fischer-Tropsch)
    2020: 0.88
    2025: 0.85
    2030: 0.78
    2035: 0.7
    2040: 0.6
    2045: 0.5
    2050: 0.4
  HVC_mechanical_recycling_fraction:  # Share from mechanical recycling
    2020: 0.12
    2025: 0.15
    2030: 0.18
    2035: 0.21
    2040: 0.24
    2045: 0.27
    2050: 0.30
  HVC_chemical_recycling_fraction:   # Share from chemical recycling
    2020: 0.0
    2025: 0.0
    2030: 0.04
    2035: 0.08
    2040: 0.12
    2045: 0.16
    2050: 0.20
  
  # Energy efficiency progress (interpolation between current and future best-in-class)
  sector_ratios_fraction_future:  # Progress towards future energy efficiency
    2020: 0.0
    2025: 0.05
    2030: 0.2
    2035: 0.45
    2040: 0.7
    2045: 0.85
    2050: 1.0
```

**What You Can Control**:
- **Steel**: Primary vs. secondary production share, DRI technology adoption
- **Aluminium**: Primary vs. secondary production share
- **HVC**: Primary production vs. mechanical recycling vs. chemical recycling shares
- **Energy efficiency**: Progress towards future best-in-class energy consumption (via `sector_ratios_fraction_future`)

**Output**: `resources/<run_name>/industrial_production_per_country_tomorrow.csv`

#### 2. Heat Demand

**Script**: `build_heat_totals.py`

**Method**: 
- Uses polynomial regression of historical heat demand on Heating Degree Days (HDD)
- Regression is based on data from 2007-2021
- Projects heat demand for future years based on HDD data for those years
- Different weather years will have different heat demands

**Note**: This only affects heat demand, not total energy demand.

#### 3. Industrial Electricity Demand (Temporal Profiles)

**Script**: `build_industrial_energy_demand_per_node.py`

**Method** (when `temporal_electricity_industry_load: true`):
- Uses **future industrial production** (from `build_industrial_production_per_country_tomorrow.py`)
- **Important**: This "future" production is NOT scaled - it uses the same total production quantities as the reference year (2019)
- The only difference is the production method mix (primary vs. secondary/recycling), which affects energy intensity but not total production volume
- Applies FfE load profiles to future electricity demand based on this production
- Current industrial electricity from JRC IDEES is removed from general load
- Only future industrial electricity demand gets temporal profiles

**Key Point**: Even though it's called "future production", the total production quantities remain the same as the reference year. The temporal profiles are applied to electricity demand calculated from this production, but the production volumes themselves are not scaled to future years.

**Configuration**: `industry.temporal_electricity_industry_load: true/false`

### Rescaling with Eurostat Data

**Function**: `rescale_idees_from_eurostat()` in `build_energy_totals.py`

**Method**:
1. Takes JRC IDEES data from 2021 (base year)
2. Calculates ratio: `Eurostat_data[target_year] / Eurostat_data[2021]`
3. Applies this ratio to IDEES data to scale it to target year
4. This allows using more recent Eurostat data to update IDEES data

**Note**: This rescaling is applied during the `build_energy_totals` step, but the target year is still typically the base year (2019 or 2021).

## Configuration Parameters

### Key Configuration Settings

```yaml
energy:
  energy_totals_year: 2019  # Base year for energy demand data

industry:
  St_primary_fraction:      # Steel primary production fraction by year
    2020: 0.65
    2030: 0.50
    2040: 0.35
    2050: 0.20
  DRI_fraction:              # DRI fraction in primary steel
    2020: 0.0
    2030: 0.1
    2040: 0.2
    2050: 0.3
  Al_primary_fraction:       # Aluminium primary production fraction
    2020: 0.60
    2030: 0.50
    2040: 0.40
    2050: 0.30
  HVC_primary_fraction:      # HVC primary production fraction
    2020: 1.0
    2030: 0.85
    2040: 0.70
    2050: 0.55
  HVC_mechanical_recycling_fraction:
    2020: 0.0
    2030: 0.10
    2040: 0.20
    2050: 0.30
  HVC_chemical_recycling_fraction:
    2020: 0.0
    2030: 0.05
    2040: 0.10
    2050: 0.15
  temporal_electricity_industry_load: false  # Enable temporal profiles for industrial electricity
```

## Demand Scaling Parameters

Yes! There are several configuration parameters that allow you to scale demand:

### 1. Electricity Load Scaling
**Parameter**: `load.scaling_factor`  
**Location**: `config/config.default.yaml` → `load` section  
**Default**: `1.0`  
**Usage**: Scales all electricity load/demand by this factor
```yaml
load:
  scaling_factor: 1.2  # Increases electricity demand by 20%
```

### 2. Sector-Specific Demand Factors

#### Aviation Demand
**Parameter**: `sector.aviation_demand_factor`  
**Default**: `1.0`  
**Usage**: Scales aviation energy demand
```yaml
sector:
  aviation_demand_factor: 1.5  # Increases aviation demand by 50%
```

#### HVC (High Value Chemicals) Demand
**Parameter**: `sector.HVC_demand_factor`  
**Default**: `1.0`  
**Usage**: Scales HVC (naphtha) demand for industry
```yaml
sector:
  HVC_demand_factor: 0.8  # Reduces HVC demand by 20%
```

### 3. Space Heat Demand Reduction
**Parameter**: `sector.reduce_space_heat_exogenously_factor`  
**Default**: Year-dependent values (see config)  
**Usage**: Reduces space heating demand by a percentage (e.g., due to building retrofits)
```yaml
sector:
  reduce_space_heat_exogenously: true
  reduce_space_heat_exogenously_factor:
    2020: 0.10  # 10% reduction
    2030: 0.09  # 9% reduction
    2040: 0.16  # 16% reduction
    2050: 0.29  # 29% reduction
```

**Note**: This is a reduction factor, so `0.10` means 10% reduction (demand is multiplied by `1 - 0.10 = 0.9`)

### Important Notes

- **Electricity load scaling** (`load.scaling_factor`) applies to the base electricity demand from the load data
- **Sector-specific factors** apply only to their respective sectors
- **Space heat reduction** is applied exogenously (not optimized endogenously)
- These scaling factors are **multiplicative** - set to `1.0` for no change, `>1.0` to increase, `<1.0` to decrease

## Summary

1. **Base Demand**: Energy demand comes from JRC IDEES (2015/2021) and Eurostat, rescaled to match Eurostat totals
2. **Base Year**: `energy.energy_totals_year` (default: 2019) determines which year's data is used
3. **Future Years**: By default, the same demand level is used for all planning horizons (2030, 2040, 2050)
4. **Exceptions**:
   - Industrial production is projected based on recycling rates and technology fractions
   - Heat demand can vary by weather year (via HDD regression)
   - Industrial electricity can use future production when temporal profiles are enabled
5. **No Automatic Growth**: The model does NOT assume demand growth or reduction - it's a greenfield optimization with fixed demand
6. **Technology Shares Are Configurable**: You can control the adoption shares of different production technologies (primary vs. secondary, DRI, recycling methods) through configuration parameters in `industry` section
7. **Demand Scaling Available**: You can scale demand using `load.scaling_factor` (electricity), `sector.aviation_demand_factor`, `sector.HVC_demand_factor`, and `sector.reduce_space_heat_exogenously_factor`

## References

- JRC IDEES: https://joint-research-centre.ec.europa.eu/potencia-policy-oriented-tool-energy-and-climate-change-impact-assessment/jrc-idees_en
- Eurostat: https://ec.europa.eu/eurostat/data/database
- Scripts:
  - `scripts/build_energy_totals.py`
  - `scripts/build_industrial_production_per_country_tomorrow.py`
  - `scripts/build_heat_totals.py`
  - `scripts/build_industrial_energy_demand_per_node.py`
