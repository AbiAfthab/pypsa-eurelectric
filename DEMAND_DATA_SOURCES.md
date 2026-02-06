# Demand Data Sources in PyPSA-EUr

This document provides a comprehensive list of all data sources used for different types of energy demand in PyPSA-EUr.

## 1. Electricity Demand

### Primary Sources

#### OPSD (Open Power System Data)
- **Source**: Open Power System Data
- **URL**: https://data.open-power-system-data.org/
- **Dataset**: Time series data (`time_series_60min_singleindex.csv`)
- **Data Fields**:
  - `{country}_load_actual_entsoe_transparency` (primary source)
  - `{country}_load_actual_entsoe_power_statistics` (fallback)
- **Used for**: Historical hourly electricity load/demand per country
- **Retrieval**: `scripts/retrieve_electricity_demand.py`
- **Processing**: `scripts/build_electricity_demand.py`
- **Note**: Uses ENTSO-E Transparency Platform data as primary, falls back to ENTSO-E Power Statistics

#### Synthetic Electricity Demand (Optional)
- **Source**: Model-generated / Pre-generated synthetic profiles
- **Configuration**: `data.synthetic_electricity_demand`
- **Used for**: Synthetic electricity demand profiles when historical data is unavailable or for scenario modeling
- **Retrieval**: `rules/retrieve.smk` → `retrieve_synthetic_electricity_demand`
- **Note**: Can supplement or replace OPSD data based on configuration

### Spatial Distribution
- **Population Data**: NUTS3 population from Eurostat (`nama_10r_3popgdp`)
- **GDP Data**: GDP per capita (archived dataset)
- **Distribution Key**: Configurable mix of GDP (60%) and population (40%) by default
- **Configuration**: `load.distribution_key` in `config/config.default.yaml`

## 2. Heat Demand

### Primary Sources

#### JRC IDEES
- **Source**: Joint Research Centre - IDEES database
- **URL**: https://joint-research-centre.ec.europa.eu/potencia-policy-oriented-tool-energy-and-climate-change-impact-assessment/jrc-idees_en
- **Data Files**: 
  - `JRC-IDEES-2021_Residential_{country}.xlsx`
  - `JRC-IDEES-2021_Tertiary_{country}.xlsx`
- **Used for**:
  - Residential heat demand (space heating, water heating, cooking)
  - Services/tertiary heat demand
  - Energy consumption by end-use
- **Processing**: `scripts/build_energy_totals.py` → `scripts/build_heat_totals.py`

#### Eurostat Energy Balances
- **Source**: Eurostat (European Statistical Office)
- **URL**: https://ec.europa.eu/eurostat/data/database
- **Used for**:
  - Rescaling IDEES data to match Eurostat totals
  - Filling gaps for countries not covered by JRC IDEES
  - Energy balances for non-EU28 countries

#### Eurostat Household Balances
- **Source**: Eurostat
- **Dataset**: `nrg_d_hhq` (Energy consumption in households)
- **Used for**:
  - Disaggregated household energy consumption
  - Residential space heating, water heating, and cooking energy use
  - Electricity consumption in households by end-use

### Temporal Profiles

#### BDEW Load Profiles
- **Source**: BDEW (German Association of Energy and Water Industries)
- **File**: `data/heat_load_profile_BDEW.csv`
- **Used for**: Temporal profiles for residential and services heat demand
- **Note**: Provides hourly load shapes for heat demand

#### Heating Degree Days (HDD)
- **Source**: Derived from ERA5 weather data
- **Used for**: 
  - Approximating heat demand for different weather years
  - Regression-based heat demand projection
- **Processing**: `scripts/build_heat_totals.py` uses polynomial regression of heat demand on HDD

## 3. Transport Demand

### Primary Sources

#### JRC IDEES
- **Source**: Joint Research Centre - IDEES database
- **Data Files**: `JRC-IDEES-2021_Transport_{country}.xlsx`
- **Used for**:
  - Road transport energy consumption
  - Rail transport energy consumption
  - Aviation energy consumption (domestic and international)
  - Shipping energy consumption
- **Processing**: `scripts/build_energy_totals.py` → `scripts/build_transport_demand.py`

#### Eurostat Energy Balances
- **Used for**:
  - Transport energy consumption for non-EU28 countries
  - Rescaling IDEES transport data

### Temporal Profiles

#### BASt Traffic Data (German Federal Highway Research Institute)
- **Source**: Bundesanstalt für Straßenwesen (BASt)
- **URL**: https://www.bast.de/DE/Verkehrstechnik/Fachthemen/v2-verkehrszaehlung/zaehl_node.html
- **Data Files**:
  - `data/mobility_profiles/build/{version}/kfz.csv` - Weekly profile for all motor vehicles
  - `data/mobility_profiles/build/{version}/pkw.csv` - Weekly profile for passenger cars
- **Used for**: 
  - Weekly traffic patterns for road transport
  - Temporal distribution of transport demand
- **Processing**: `scripts/build_mobility_profiles.py` → `scripts/build_transport_demand.py`

#### Temperature Data (ERA5)
- **Used for**: 
  - Temperature-dependent transport demand correction
  - Vehicle heating/cooling energy consumption
- **Configuration**: 
  - `sector.transport_heating_deadband_lower` (default: 15°C)
  - `sector.transport_heating_deadband_upper` (default: 20°C)
  - `sector.ICE_lower_degree_factor` (default: 0.5)
  - `sector.ICE_upper_degree_factor` (default: 1.6)

### Vehicle Stock Data

#### BFS Road Vehicle Stock (Switzerland)
- **Source**: Swiss Federal Statistical Office (Bundesamt für Statistik)
- **URL**: https://pubdb.bfe.admin.ch/
- **Used for**: 
  - Vehicle stock data for Switzerland
  - Transport energy consumption for Switzerland (not covered by Eurostat)

## 4. Industrial Demand

### Primary Sources

#### JRC IDEES
- **Source**: Joint Research Centre - IDEES database
- **Data Files**: `JRC-IDEES-2021_Industry_{country}.xlsx`
- **Used for**:
  - Industrial production data per country and sector
  - Industrial energy consumption by sector:
    - Iron & steel (Electric arc, Integrated steelworks)
    - Cement
    - Chemicals (HVC, Ammonia, Chlorine, Methanol)
    - Non-metallic minerals (Ceramics, Glass)
    - Paper and pulp
    - Food, beverages and tobacco
    - Aluminium (primary and secondary)
    - Other industrial sectors
- **Reference Year**: Configurable via `industry.reference_year` (default: 2019)
- **Processing**: 
  - `scripts/build_industrial_production_per_country.py`
  - `scripts/build_industrial_energy_demand_per_country_today.py`

#### Eurostat Energy Balances
- **Used for**:
  - Industrial energy consumption for non-EU28 countries
  - Rescaling IDEES industrial data

### Spatial Distribution

#### Hotmaps Industrial Database
- **Source**: Hotmaps Project
- **URL**: https://gitlab.com/hotmaps/industrial_sites/industrial_sites_Industrial_Database
- **Used for**:
  - Spatial distribution of industrial sites across Europe
  - Geographic mapping of energy-intensive industries
  - Nodal distribution of industrial energy demand
- **Processing**: `scripts/build_industrial_production_per_node.py`

### Temporal Profiles (Optional)

#### FfE Industrial Load Profiles
- **Source**: Forschungsstelle für Energiewirtschaft e.V. (FfE)
- **URL**: https://api.opendata.ffe.de/opendata
- **Dataset ID**: 59
- **License**: CC-BY 4.0
- **Reference Year**: 2017 (hourly profiles for full year)
- **Used for**: 
  - Temporal electricity load profiles for industrial sectors
  - Hourly industrial electricity demand patterns
  - **Note**: Only applied to future industrial electricity demand (not current demand from JRC IDEES)
- **Configuration**: `industry.temporal_electricity_industry_load: true/false`
- **Processing**: `scripts/build_industrial_energy_demand_per_node.py`
- **Available Profiles**:
  - Iron & steel industry
  - Non-metallic Minerals
  - Transport Equipment
  - Machinery
  - Mining and Quarrying
  - Food and Tobacco
  - Paper, Pulp and Print
  - Wood and Wood Products
  - Construction
  - Textile and Leather
  - Non-specified (Industry)

## 5. Agriculture Demand

### Primary Sources

#### JRC IDEES
- **Data Files**: `JRC-IDEES-2021_Industry_{country}.xlsx`
- **Used for**:
  - Agriculture, forestry and fishing sector energy consumption
  - Split into:
    - Electricity (lighting, ventilation, electric pumping)
    - Heat (specific heat uses, low enthalpy heat)
    - Machinery oil (motor drives, farming machines, diesel pumping)

#### Eurostat Energy Balances
- **Used for**: Agriculture energy consumption for non-EU28 countries

### Spatial Distribution
- **Distribution Method**: Constant time series, distributed by population

## 6. Natural Gas (Methane) Demand

### Primary Sources

#### JRC IDEES
- **Source**: Joint Research Centre - IDEES database
- **Data Files**: 
  - `JRC-IDEES-2021_Industry_{country}.xlsx`
  - `JRC-IDEES-2021_Residential_{country}.xlsx`
  - `JRC-IDEES-2021_Tertiary_{country}.xlsx`
- **Used for**:
  - **Industrial gas demand**: Natural gas consumption in industry sectors (high-temperature heat, furnaces, steam processing)
  - **Residential gas demand**: Natural gas for space heating, water heating, cooking
  - **Services gas demand**: Natural gas for space heating, water heating in tertiary sector
  - **CHP plants**: Gas-fired combined heat and power plants
- **Processing**: 
  - `scripts/build_energy_totals.py` → extracts "Natural gas and biogas" consumption
  - `scripts/build_industry_sector_ratios.py` → converts to "methane" carrier
  - `scripts/build_industrial_energy_demand_per_node.py` → creates nodal gas demand
- **Note**: In the model, natural gas is represented as "methane" (CH4)

#### Eurostat Energy Balances
- **Used for**:
  - Natural gas consumption for non-EU28 countries
  - Rescaling IDEES gas data to match Eurostat totals
  - Gas consumption by sector

### Gas Demand Uses

Natural gas (methane) is used for:
1. **Industrial processes**:
   - High-temperature heat (>1000°C) in furnaces and steam processing
   - Process heat in various industrial sectors
   - Feedstock in some chemical processes (e.g., ammonia via SMR)
2. **Residential and services heating**:
   - Gas boilers for space heating
   - Water heating
   - Cooking (residential)
3. **Power generation**:
   - OCGT (Open Cycle Gas Turbines)
   - CCGT (Combined Cycle Gas Turbines)
   - CHP (Combined Heat and Power) plants
4. **District heating**:
   - Gas-fired district heating systems

### Is Gas Demand Fixed or Modifiable?

**Gas demand is NOT completely fixed** - it can be modified through several mechanisms:

#### 1. **Technology Electrification** (Automatic Transition)
- Many industrial processes are assumed to be **fully electrified** in future scenarios
- The model interpolates between current energy consumption (with gas) and future best-in-class consumption (more electrified)
- **Configuration**: `industry.sector_ratios_fraction_future` controls the interpolation:
  ```yaml
  industry:
    sector_ratios_fraction_future:
      2020: 0.0    # 100% current (with gas)
      2030: 0.2    # 20% future (more electrified)
      2040: 0.7    # 70% future
      2050: 1.0    # 100% future (fully electrified)
  ```
- **Effect**: As this fraction increases, gas demand decreases as processes are electrified
- **Processing**: `scripts/build_industry_sector_ratios_intermediate.py` calculates:
  ```
  intermediate_ratios = today_ratios × (1 - fraction_future) + future_ratios × fraction_future
  ```

#### 2. **Production Method Changes** (Configurable)
- **Steel**: More recycling (secondary production) reduces gas demand for primary steel production
  - Controlled by `industry.St_primary_fraction`
  - Less primary steel = less gas needed for integrated steelworks
- **Aluminium**: More recycling reduces gas demand for alumina production
  - Controlled by `industry.Al_primary_fraction`
  - Less primary aluminium = less gas needed for alumina production
- **Chemicals**: Changes in production methods affect gas demand
  - Ammonia: Can switch from SMR (gas) to electrolysis (electricity)
  - Methanol: Production method affects gas demand

#### 3. **Residential/Services Heating** (Endogenously Optimized)
- **Heat pump adoption**: Replaces gas boilers (optimized by the model)
- **Building retrofits**: Reduces total heat demand (and thus gas demand)
  - Controlled by `sector.reduce_space_heat_exogenously_factor`
- **Technology options**: Can enable/disable gas boilers, CHP, etc.
  - `sector.boilers: true/false`
  - `sector.chp.enable: true/false`
  - `sector.chp.fuel: [solid biomass, gas]`

#### 4. **Energy Efficiency Improvements**
- Energy efficiency improvements reduce total energy demand (including gas)
- Controlled by `industry.sector_ratios_fraction_future` (interpolates to future best-in-class efficiency)

**Key Point**: Gas demand is **derived from energy consumption data** but **changes based on technology assumptions and production methods**. The model assumes progressive electrification of industrial processes, which reduces gas demand over time. The transition is controlled by `sector_ratios_fraction_future`, which interpolates between current (gas-intensive) and future (electrified) energy consumption patterns.

### Gas Infrastructure Data

#### SciGrid Gas
- **Source**: SciGrid Project
- **URL**: https://www.gasgrid.net/
- **Used for**:
  - Natural gas pipeline network topology
  - Pipeline capacities, diameters, pressures
  - Gas storage facilities
  - Gas border points and interconnection points
- **Processing**: `scripts/build_gas_network.py`

#### GEM Europe Gas Tracker
- **Source**: Global Energy Monitor
- **Used for**:
  - LNG terminal locations and capacities
  - Gas extraction/production sites
  - Gas infrastructure data
- **Processing**: `scripts/build_gas_input_locations.py`

### Spatial Distribution

- **Industrial gas demand**: Distributed based on industrial site locations (Hotmaps)
- **Residential/services gas demand**: Distributed by population (from energy totals)
- **Configuration**: `sector.regional_gas_demand: true/false` (default: true for regional distribution)

### Temporal Profiles

- **Industrial gas demand**: Typically constant (flat) across time, unless temporal profiles are enabled
- **Residential/services gas demand**: Follows heat demand temporal profiles (BDEW profiles, HDD-dependent)

### Gas Supply Sources

Gas can enter the system at:
1. **LNG terminals**: Import terminals for liquefied natural gas
2. **Pipeline entry points**: Cross-border pipeline connections
3. **Gas production sites**: Intra-European gas extraction
4. **Biogas upgrading**: Biogas upgraded to methane quality
5. **Synthetic methane**: Produced from hydrogen and CO2 (Sabatier reaction)

## 7. Shipping Demand

### Primary Sources

#### JRC IDEES
- **Used for**: International navigation (bunkers) energy consumption

#### Eurostat Energy Balances
- **Used for**: International navigation energy consumption

### Spatial Distribution

#### Ship Raster (Ship Density)
- **Source**: World Bank Data Catalogue
- **URL**: https://datacatalog.worldbank.org/search/dataset/0037580/Global-Shipping-Traffic-Density
- **Used for**:
  - Shipping routes and density
  - Maritime transport demand allocation
  - Shipping fuel consumption patterns

## Data Processing Flow

### Energy Totals
1. **JRC IDEES** → Country-level energy consumption by sector (including natural gas)
2. **Eurostat** → Rescaling and gap filling
3. **Swiss BFS** → Switzerland-specific data
4. **Output**: `resources/<run_name>/energy_totals.csv`

### Natural Gas Demand Processing
1. **JRC IDEES** → Extract "Natural gas and biogas" consumption by sector
2. **Industry sector ratios** → Convert to "methane" carrier and calculate specific energy consumption per material
3. **Industrial production** → Multiply production by energy ratios to get gas demand
4. **Spatial distribution** → Distribute to nodes based on industrial sites (Hotmaps) or population
5. **Output**: 
   - `resources/<run_name>/industrial_energy_demand_per_node.csv` (includes methane)
   - Gas demand added as Load components in network

### Population-Weighted Distribution
1. **NUTS3 Population** (Eurostat) → Regional population distribution
2. **GDP per Capita** → Economic distribution
3. **Distribution Key** → Mix of population and GDP (configurable)
4. **Output**: `resources/<run_name>/pop_weighted_energy_totals_s_{clusters}.csv`

### Temporal Profiles
1. **Historical Load Data** (OPSD, BDEW, BASt, FfE) → Temporal patterns
2. **Weather Data** (ERA5) → Temperature-dependent corrections
3. **Mapping** → Apply profiles to target years and regions
4. **Output**: Various profile files (`.nc`, `.csv`)

## Configuration

### Data Source Selection
All data sources can be configured in `config/config.default.yaml` under the `data` section:

```yaml
data:
  jrc_idees:
    source: archive  # or primary
    version: latest
  eurostat_balances:
    source: archive
    version: latest
  synthetic_electricity_demand:
    source: primary
    version: latest
  # ... etc.
```

### Reference Years
- **Energy Totals**: `energy.energy_totals_year: 2019` (default)
- **Industrial Production**: `industry.reference_year: 2019` (default)
- **Heat Demand**: Uses HDD regression from 2007-2021 data

## References

- **JRC IDEES**: https://joint-research-centre.ec.europa.eu/potencia-policy-oriented-tool-energy-and-climate-change-impact-assessment/jrc-idees_en
- **Eurostat**: https://ec.europa.eu/eurostat/data/database
- **OPSD**: https://data.open-power-system-data.org/
- **FfE Open Data**: https://opendata.ffe.de/
- **BASt**: https://www.bast.de/
- **Hotmaps**: https://gitlab.com/hotmaps/industrial_sites/industrial_sites_Industrial_Database
- **Swiss BFS**: https://pubdb.bfe.admin.ch/

## Notes

- **Archive vs Primary Sources**: Many datasets are available from both archive (pre-processed, cached) and primary (original) sources
- **Data Versioning**: Most datasets support versioning to ensure reproducibility (see `data/versions.csv`)
- **Geographic Coverage**: Most datasets focus on Europe (EU28/EU27), with some global datasets used for context
- **Temporal Coverage**: Historical data typically covers 2013-2021, with some datasets extending further back
- **Spatial Resolution**: Country-level data is distributed to network nodes using population/GDP weighting
- **Natural Gas Representation**: Natural gas is represented as "methane" (CH4) in the model, which includes both fossil natural gas and upgraded biogas
- **Gas Network Modeling**: Gas infrastructure can be modeled regionally (with pipeline constraints) or as copperplate (unconstrained transport) via `sector.gas_network: true/false`
