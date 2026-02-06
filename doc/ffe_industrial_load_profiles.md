# FFE Industrial Load Profiles Integration

## Overview

This document describes the integration of industrial electricity load profiles from FfE (Forschungsstelle für Energiewirtschaft e.V.) open data into PyPSA-Eur-Sec for modeling temporally-resolved industrial electricity demand.

**Important Notes:**
- The FfE temporal profiles are **only applied to future industrial electricity demand**, not to current/present demand from JRC IDEES
- Current industrial electricity demand from JRC IDEES is removed from the general electricity load but remains constant (flat)
- Industrial heat demand (low-temperature heat) also remains constant (flat) across all time steps

## Data Source

### Source Information

- **Organization:** Forschungsstelle für Energiewirtschaft e.V. (FfE)
- **Dataset:** Normalized Industrial Electrical Load Profiles (Germany)
- **API Endpoint:** `https://api.opendata.ffe.de/opendata`
- **Dataset ID:** 59
- **License:** CC-BY 4.0
- **Link:** https://opendata.ffe.de/dataset/normalized-industrial-electrical-load-profiles-germany/
- **Reference Year:** 2017 (hourly profiles for full year)

### Data Content

The FfE dataset contains normalized hourly electricity load profiles for different German industrial sectors. The profiles are provided as synthetic load curves representing typical consumption patterns throughout the year 2017.

**Available Industry Profiles:**
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

## Data Retrieval

### Snakemake Rule

The data is automatically retrieved through the Snakemake workflow:

**File:** `rules/retrieve.smk` (lines 1166-1181)

```python
rule retrieve_ffe_load_profiles:
    output:
        "data/ffe_industry_load_profiles.json",
    log:
        "logs/retrieve_ffe_load_profiles.log",
    resources:
        mem_mb=1000,
    retries: 2
    run:
        data = requests.get(
            "https://api.opendata.ffe.de/opendata",
            params={"id_opendata": 59}
        ).json()
        
        with open(output[0], "w") as f:
            json.dump(data, f)
```

The rule downloads the JSON data from the FfE open data API and stores it locally as `data/ffe_industry_load_profiles.json`.

## Data Processing

### Main Processing Script

**File:** `scripts/build_industrial_energy_demand_per_node.py`

### Step 1: Loading FFE Profiles

The function `load_ffe_load_profiles()` (lines 80-120) processes the downloaded JSON file:

1. **Load JSON data:** Reads the pre-downloaded JSON file containing FfE data
2. **Map internal IDs:** Maps internal profile IDs to human-readable profile names:
   - ID 1 → "Iron & steel industry"
   - ID 4 → "Non-metallic Minerals"
   - ID 5 → "Transport Equipment"
   - ID 6 → "Machinery"
   - ID 7 → "Mining and Quarrying"
   - ID 8 → "Food and Tobacco"
   - ID 9 → "Paper, Pulp and Print"
   - ID 10 → "Wood and Wood Products"
   - ID 11 → "Construction"
   - ID 12 → "Textile and Leather"
   - ID 13 → "Non-specified (Industry)"

3. **Create timestamps:** Generates hourly timestamps for 2017 (8760 hours)
4. **Parse data:** Converts JSON structure into a pandas DataFrame with:
   - Index: Timestamps (hourly, 2017)
   - Columns: Industry profile names
   - Values: Normalized load values

### Step 2: Sector Mapping

The script maps PyPSA-Eur-Sec industrial sectors to FfE profiles using the `INDUSTRY_CATEGORY_TO_PROFILE` dictionary (lines 48-77):

**Key Mappings:**
- Steel sectors (Electric arc, DRT + Electric arc, Integrated steelworks, Alumina, Aluminium) → "Iron & steel industry"
- Cement, Ceramics, Glass → "Non-metallic Minerals"
- Pulp, Paper, Printing → "Paper, Pulp and Print"
- Food, beverages, tobacco → "Food and Tobacco"
- Transport equipment → "Transport Equipment"
- Machinery → "Machinery"
- Textiles and leather → "Textile and Leather"
- Wood products → "Wood and Wood Products"
- Chemicals, HVC, Ammonia, Chlorine, Methanol → "Non-specified (Industry)"

### Step 3: Nodal Profile Creation

The function `create_nodal_electricity_profiles()` (lines 122-200) creates hourly electricity demand profiles for each network node:

**Important:** The profiles are created from **future industrial electricity demand** only, not from current demand.

1. **Extract electricity demands:** Gets sector-specific **future** electricity demands per node (TWh/a) from `nodal_sector_df.loc["elec"]`
   - This comes from future production and sector ratios, not current JRC IDEES data
2. **Map sectors to profiles:** Maps each industrial sector to its corresponding FfE profile
3. **Aggregate to profile level:** Groups sector demands by FfE profile type
4. **Weighted combination:** Uses matrix multiplication to combine FfE profiles weighted by sector demands:
   ```
   weighted_profiles = ffe_profiles[profiles] × profile_demands
   ```
   - `ffe_profiles`: (hours × profiles) - normalized hourly profiles
   - `profile_demands`: (profiles × nodes) - **future** annual demands per profile per node
   - Result: (hours × nodes) - weighted hourly profiles per node

5. **Calendar mapping:** Maps 2017 reference profiles to target year snapshots (see below)
6. **Unit conversion:** Converts from normalized values to MW
7. **Validation:** Verifies that hourly profiles sum to **future** annual demand (`nodal_df["electricity"]`)

### Step 4: Temporal Mapping

The function `map_profile_to_snapshots()` (lines 203-295) maps the 2017 German reference profiles to target year snapshots:

**Process:**

1. **Compute average day profiles:** Creates weekday-hour averages from 2017 data
2. **Normalize German holidays:** Replaces German holidays in 2017 with weekday-hour averages
3. **Weekday alignment:** Shifts dates to align weekdays between source (2017) and target year
4. **Leap year handling:**
   - For leap years: adjusts dates from March onward, adds Dec 31 using weekday averages
   - For non-leap years: removes Feb 29 if present
5. **Target country holidays:** Replaces target country holidays with Sunday-hour averages
6. **Map to snapshots:** Reindexes to match exact snapshot timestamps
7. **Energy preservation:** Scales profiles to preserve total annual energy (with 2% tolerance check)

**Key Features:**
- Preserves energy balance (annual totals match)
- Accounts for country-specific holidays
- Handles leap years correctly
- Maintains weekday patterns

## Integration into Network

### Snakemake Workflow

**File:** `rules/build_sector.smk` (lines 1095-1132)

The rule `build_industrial_energy_demand_per_node` processes the data:

**Inputs:**
- Industry sector ratios (by planning horizon)
- Industrial production per node
- Current industrial energy demand per node
- FFE profiles JSON file

**Outputs:**
- Annual industrial energy demand per node (CSV)
- Temporal industrial electricity demand per node (CSV) - hourly profiles in MW

### Network Integration

**File:** `scripts/prepare_sector_network.py` (lines 4990-5038)

The function `add_industry()` integrates the temporal profiles into the PyPSA network:

1. **Remove current electricity:** First, removes current industrial electricity demand from JRC IDEES from the general electricity load (lines 4990-5004):
   ```python
   # remove today's industrial electricity demand by scaling down total electricity demand
   factor = 1 - industrial_demand.loc[loads_i, "current electricity"].sum() / ...
   n.loads_t.p_set[loads_i] *= factor
   ```
   - This current electricity remains **constant (flat)** and is not given temporal profiles

2. **Configuration check:** Verifies if temporal profiles are enabled for **future** demand:
   ```python
   use_temporal = snakemake.params.industry.get(
       "temporal_electricity_industry_load", False
   )
   ```

3. **Load profiles:** Reads the hourly profiles CSV file (MW) - these represent **future** industrial electricity demand

4. **Create loads:** Adds Load components to the network for **future** industrial electricity:
   - Load names: `"{node} industry electricity"`
   - Carrier: `"industry electricity"`
   - Bus: Node name
   - `p_set`: Hourly load profile (MW) - **temporal profiles applied only here**

5. **Fallback:** If temporal profiles are disabled, uses constant annual **future** demand divided by hours

### Industrial Heat Demand

Industrial heat demand is handled separately and **always uses constant (flat) profiles**:

**File:** `scripts/prepare_sector_network.py` (lines 4974-4988)

```python
n.add(
    "Load",
    nodes,
    suffix=" low-temperature heat for industry",
    bus=[...],
    carrier="low-temperature heat for industry",
    p_set=industrial_demand.loc[nodes, "low-temperature heat"] / nhours,
)
```

The heat demand is calculated as:
- **Annual demand** (TWh/a) divided by **total hours** (`nhours`)
- This creates a **constant hourly value** across all snapshots
- No temporal variation is applied to industrial heat demand

This differs from residential/services heat demand, which uses temporal profiles based on heating degree days and BDEW profiles.

### Configuration

The feature is controlled by the configuration parameter:

- **Parameter:** `temporal_electricity_industry_load`
- **Location:** `config.yaml` under `industry` section
- **Type:** Boolean
- **Default:** `false`
- **Description:** Enables temporally-resolved electricity industry load profiles from FfE

## Data Flow Summary

```
1. FfE Open Data API
   ↓
2. retrieve_ffe_load_profiles rule
   → data/ffe_industry_load_profiles.json
   ↓
3. build_industrial_energy_demand_per_node rule
   → Loads FFE JSON
   → Maps sectors to profiles
   → Creates nodal profiles
   → Maps to target year
   → industrial_electricity_demand_temporal_*.csv
   ↓
4. prepare_sector_network rule (add_industry function)
   → Loads temporal profiles CSV
   → Adds Load components to network
   → Sets hourly p_set values
```

## Key Assumptions

1. **Future demand only:** Temporal profiles are applied **only to future industrial electricity demand**, not to current demand from JRC IDEES
2. **Current demand handling:** Current industrial electricity from JRC IDEES is removed from general load but remains constant (flat)
3. **Geographic projection:** German profiles (2017) are applied to all European countries for the same industry sectors
4. **Sector mapping:** PyPSA-Eur-Sec industrial sectors are mapped to FfE profile categories
5. **Temporal patterns:** Weekday patterns and seasonal variations from 2017 Germany are preserved
6. **Holiday adjustment:** Country-specific holidays replace German holidays in the target year
7. **Energy preservation:** Total annual energy demand is preserved during temporal mapping

## Validation

The implementation includes several validation checks:

1. **Sector mapping:** Ensures all sectors have corresponding FfE profiles
2. **Profile existence:** Verifies all required profiles exist in FfE data
3. **Energy balance:** Checks that hourly profiles sum to annual demand (within tolerance)
4. **Sector demand consistency:** Validates that sector demands match total node demand

## References

- FfE Open Data Portal: https://opendata.ffe.de/
- Dataset: https://opendata.ffe.de/dataset/normalized-industrial-electrical-load-profiles-germany/
- License: CC-BY 4.0
- Implementation: `scripts/build_industrial_energy_demand_per_node.py`
- Integration: `scripts/prepare_sector_network.py` (add_industry function)
