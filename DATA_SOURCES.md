# Data Sources and Their Uses in PyPSA-Eur-Sec

This document provides a comprehensive list of all input data sources used in the PyPSA-Eur-Sec model and what they are used for.

## Weather Data for Renewable Energy Generation

### ERA5 (ECMWF Reanalysis Dataset)
- **Source**: ECMWF (European Centre for Medium-Range Weather Forecasts)
- **URL**: https://www.ecmwf.int/en/forecasts/datasets/reanalysis-datasets/era5
- **Used for**:
  - Wind power generation profiles (wind speeds at 100m)
  - Solar power generation profiles (surface solar radiation, direct/diffuse radiation)
  - Temperature data for heat pump COP calculations
  - Runoff data for hydroelectric power generation
  - Heating Degree Days (HDD) for space heating demand calculations
  - Soil temperature for ground-sourced heat pumps
  - Surface pressure, albedo, and other meteorological variables

### SARAH-3 (Surface Solar Radiation Dataset)
- **Source**: CMSAF (Satellite Application Facility on Climate Monitoring)
- **URL**: https://wui.cmsaf.eu/safira/action/viewDoiDetails?acronym=SARAH_V002
- **Used for**:
  - Solar radiation data (amends ERA5 solar data with satellite-based observations)
  - Surface solar radiation (direct, diffuse, TOA)
  - Temperature, albedo, and solar radiation fields
  - Typically used in combination with ERA5 (priority order: SARAH first, then ERA5)

### HERA (Hydrological and Environmental Research and Analysis)
- **Source**: JRC (Joint Research Centre) - CEMS-EFAS
- **URL**: https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/HERA/
- **Used for**:
  - River discharge data for surface water heat potential calculations
  - Ambient temperature data for river water heat extraction
  - District heating systems using rivers as heat sources

### Seawater Temperature
- **Source**: Derived from ERA5 or other oceanographic datasets
- **Used for**:
  - Seawater temperature for district heating systems using seawater as heat source
  - Heat pump COP calculations for seawater-sourced heat pumps

## Industry and Energy Demand Data

### JRC IDEES (Institute for Energy and Transport)
- **Source**: Joint Research Centre - IDEES database
- **URL**: https://joint-research-centre.ec.europa.eu/potencia-policy-oriented-tool-energy-and-climate-change-impact-assessment/jrc-idees_en
- **Used for**:
  - Industrial production data per country and sector
  - Industrial energy consumption by sector (iron & steel, cement, chemicals, etc.)
  - Heat demand per country (residential and services)
  - Energy balances for EU28 countries
  - Process emissions from industry
  - Transport energy consumption
  - Residential and services energy consumption

### Eurostat Energy Balances
- **Source**: Eurostat (European Statistical Office)
- **URL**: https://ec.europa.eu/eurostat/data/database
- **Used for**:
  - Energy balances for non-EU28 countries
  - Energy consumption data for countries not covered by JRC IDEES
  - Rescaling JRC IDEES data to match Eurostat totals
  - CO2 emissions calculations from fuel consumption
  - Energy statistics for validation and calibration

### Eurostat Household Balances
- **Source**: Eurostat
- **Dataset**: `nrg_d_hhq` (Energy consumption in households)
- **Used for**:
  - Disaggregated household energy consumption
  - Residential space heating, water heating, and cooking energy use
  - Electricity consumption in households by end-use

### Hotmaps Industrial Database
- **Source**: Hotmaps Project
- **URL**: https://gitlab.com/hotmaps/industrial_sites/industrial_sites_Industrial_Database
- **Used for**:
  - Spatial distribution of industrial sites across Europe
  - Geographic mapping of energy-intensive industries (cement, chemicals, steel, etc.)
  - Nodal distribution of industrial energy demand
  - Industrial site locations for regional energy demand allocation

### FfE Industrial Load Profiles
- **Source**: Forschungsstelle für Energiewirtschaft e.V. (FfE)
- **URL**: https://api.opendata.ffe.de/opendata
- **Used for**:
  - Temporal electricity load profiles for industrial sectors
  - Hourly industrial electricity demand patterns
  - Future industrial electricity demand time series

### GEM Europe Gas Tracker
- **Source**: Global Energy Monitor
- **Used for**:
  - Gas infrastructure data
  - Gas plant locations and capacities

### GEM Global Steel Plant Tracker (GSPT)
- **Source**: Global Energy Monitor
- **Used for**:
  - Steel plant locations and capacities
  - Steel production data

### BFS Road Vehicle Stock (Switzerland)
- **Source**: Swiss Federal Statistical Office (Bundesamt für Statistik)
- **URL**: https://pubdb.bfe.admin.ch/
- **Used for**:
  - Vehicle stock data for Switzerland
  - Transport energy consumption for Switzerland (not covered by Eurostat)

### BFS GDP and Population (Switzerland)
- **Source**: Swiss Federal Statistical Office
- **Used for**:
  - GDP and population data for Switzerland
  - Economic and demographic data for energy demand calculations

## Geographic and Administrative Data

### NUTS Regions (2013 and 2021)
- **Source**: Eurostat
- **Used for**:
  - Administrative boundaries (NUTS levels 0, 1, 2, 3)
  - Regional aggregation for energy system modeling
  - Country and sub-national region definitions

### NUTS3 Population
- **Source**: Eurostat
- **Dataset**: `nama_10r_3popgdp`
- **Used for**:
  - Population data at NUTS3 level
  - Regional population distribution
  - Demand allocation based on population

### LAU Regions
- **Source**: Eurostat
- **Used for**:
  - Local Administrative Units boundaries
  - Fine-scale administrative boundaries

### OSM (OpenStreetMap) Boundaries
- **Source**: OpenStreetMap
- **Used for**:
  - Administrative boundaries from OSM
  - Country and region boundaries for non-EU countries

### OSM Infrastructure Data
- **Source**: OpenStreetMap
- **Used for**:
  - Electricity transmission infrastructure (lines, transformers, substations)
  - Power grid topology
  - Network components for electricity system modeling

## Land Use and Land Cover

### CORINE Land Cover
- **Source**: Copernicus Land Monitoring Service
- **URL**: https://land.copernicus.eu/
- **Used for**:
  - Land cover classification
  - Land use constraints for renewable energy deployment
  - Protected area identification
  - Spatial planning constraints

### Copernicus Global Land Cover
- **Source**: Copernicus Land Monitoring Service
- **Used for**:
  - Global land cover classification
  - Land use data for renewable energy potential calculations

### LUISA Base Map
- **Source**: JRC - LUISA (Land Use-based Integrated Sustainability Assessment)
- **URL**: https://ec.europa.eu/jrc/en/luisa
- **Used for**:
  - Land use and land cover data
  - Spatial planning and land use constraints

### Natura 2000
- **Source**: European Environment Agency
- **Used for**:
  - Protected area boundaries
  - Environmental constraints for infrastructure deployment
  - Biodiversity protection areas

### WDPA (World Database on Protected Areas)
- **Source**: Protected Planet / UNEP-WCMC
- **URL**: https://www.protectedplanet.net/
- **Used for**:
  - Terrestrial protected areas
  - Constraints for renewable energy and infrastructure deployment

### WDPA Marine
- **Source**: Protected Planet / UNEP-WCMC
- **Used for**:
  - Marine protected areas
  - Constraints for offshore renewable energy deployment

## Population and Economic Data

### WorldPop Population Count
- **Source**: WorldPop / World Bank
- **Used for**:
  - High-resolution population raster data
  - Population distribution at 1km resolution
  - Demand allocation based on population density

### GDP per Capita
- **Source**: Various (archived dataset)
- **Used for**:
  - Economic data for demand allocation
  - GDP-based distribution of energy demand

### World Bank Urban Population
- **Source**: World Bank
- **Dataset**: `API_SP.URB.TOTL.IN.ZS`
- **Used for**:
  - Urban population statistics
  - Urban/rural classification for heat demand distribution

### JRC ARDECO
- **Source**: JRC - ARDECO (Administrative Regions Database for Europe)
- **Used for**:
  - GDP data at administrative level
  - Population data at administrative level
  - Economic and demographic statistics

## Energy Infrastructure

### SciGrid Gas Infrastructure
- **Source**: SciGrid Project
- **Used for**:
  - Natural gas pipeline network
  - Gas storage facilities
  - Gas border points and interconnection points
  - Gas infrastructure topology

### TYNDP (Ten-Year Network Development Plan)
- **Source**: ENTSO-E / ENTSOG
- **Used for**:
  - Planned electricity transmission lines
  - Reference grid data
  - Network node definitions
  - Future transmission infrastructure

### Power Plants Database
- **Source**: Various (primary source)
- **Used for**:
  - Existing power plant locations and capacities
  - Power plant technology types
  - Historical generation data

### Attributed Ports
- **Source**: Various
- **Used for**:
  - Port locations and attributes
  - Shipping infrastructure
  - Maritime transport data

## Renewable Energy Resources

### ENSPRESO Biomass
- **Source**: ENSPRESO Project
- **Used for**:
  - Biomass potential data
  - Biomass resource availability
  - Bioenergy potential assessments

### H2 Salt Caverns
- **Source**: Various geological surveys
- **Used for**:
  - Hydrogen storage potential in salt caverns
  - Geological storage sites for hydrogen
  - Storage capacity data

### Aquifer Data (BGR)
- **Source**: BGR (Federal Institute for Geosciences and Natural Resources, Germany)
- **Used for**:
  - Aquifer locations and properties
  - Groundwater storage potential
  - Aquifer Thermal Energy Storage (ATES) potential

### Geothermal Heat Utilisation Potentials
- **Source**: ISI (Institute for Sustainable Infrastructure)
- **Used for**:
  - Geothermal heat potential
  - Shallow geothermal energy resources
  - District heating potential from geothermal sources

### District Heating Areas
- **Source**: Various
- **Used for**:
  - Existing district heating network areas
  - District heating system boundaries
  - Heat demand aggregation for district heating

## Environmental and Climate Data

### GHG Emissions (UNFCCC)
- **Source**: UNFCCC (United Nations Framework Convention on Climate Change)
- **Dataset**: `UNFCCC_v23`
- **Used for**:
  - Historical greenhouse gas emissions
  - Emissions validation and calibration
  - Climate policy constraints

### Country Runoff (ERA5-based)
- **Source**: Derived from ERA5
- **Used for**:
  - River runoff per country
  - Hydroelectric potential calculations
  - Water availability for energy systems

### Country HDD (Heating Degree Days, ERA5-based)
- **Source**: Derived from ERA5
- **Used for**:
  - Heating degree days per country
  - Space heating demand calculations
  - Seasonal heat demand patterns

## Maritime and Shipping

### Ship Raster (Ship Density)
- **Source**: Various maritime databases
- **Used for**:
  - Shipping routes and density
  - Maritime transport demand
  - Shipping fuel consumption patterns

### EEZ (Exclusive Economic Zones)
- **Source**: Marine Regions / Flanders Marine Institute
- **Used for**:
  - Maritime boundaries
  - Offshore area definitions
  - Marine spatial planning

## Carbon Capture and Storage

### CO2Stop
- **Source**: JRC
- **Used for**:
  - CO2 storage potential
  - Hydrocarbon storage units
  - CO2 sequestration sites
  - Carbon capture and storage infrastructure

## Cost and Technology Data

### Technology Costs
- **Source**: Technology-data repository (primary source)
- **Used for**:
  - Capital costs for energy technologies
  - Operating and maintenance costs
  - Technology cost projections by planning horizon

## Validation Data

### Monthly CO2 Prices (EEX)
- **Source**: EEX (European Energy Exchange)
- **URL**: https://www.eex-group.com/
- **Used for**:
  - Historical CO2 price validation
  - Emissions trading data

### Monthly Fuel Prices
- **Source**: Various
- **Used for**:
  - Historical fuel price validation
  - Energy price trends

## Synthetic and Modeled Data

### Synthetic Electricity Demand
- **Source**: Model-generated
- **Used for**:
  - Synthetic electricity demand profiles
  - Scenario modeling
  - Demand projections

### Mobility Profiles
- **Source**: Various transport databases
- **Used for**:
  - Vehicle mobility patterns
  - Transport demand profiles
  - Electric vehicle charging patterns

## Bathymetry and Topography

### GEBCO (General Bathymetric Chart of the Oceans)
- **Source**: GEBCO
- **Used for**:
  - Ocean bathymetry
  - Water depth for offshore wind deployment
  - Marine infrastructure planning

## Nitrogen Statistics
- **Source**: Various
- **Used for**:
  - Nitrogen fertilizer production data
  - Ammonia production statistics
  - Agricultural sector data

---

## Notes

- **Archive vs Primary Sources**: Many datasets are available from both archive (pre-processed, cached) and primary (original) sources. The configuration determines which source is used.
- **Data Versioning**: Most datasets support versioning to ensure reproducibility.
- **Geographic Coverage**: Most datasets focus on Europe (EU28/EU27), with some global datasets used for context.
- **Temporal Coverage**: Weather data typically covers 2013, 2019, or 2023, with some datasets extending from 1940 to 2024.
