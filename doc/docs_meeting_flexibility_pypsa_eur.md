# PyPSA-EUR Flexibility Modeling: Meeting Notes and Q&A

This document addresses questions about flexibility modeling in PyPSA-EUR, prepared for the meeting with Amedeo and Abi.

---

## 1. Current Flexibility Modeling in PyPSA-EUR

### Overview

PyPSA-EUR currently models flexibility through three main mechanisms:

| Technology | Implementation Status | Primary Mechanism |
|------------|----------------------|-------------------|
| **V2G (Vehicle-to-Grid)** | Implemented | Bidirectional EV-grid links |
| **Residential Heating** | Implemented (incl. new Heat DSM in this branch) | Thermal storage + building thermal mass |
| **Industry with H2** | Partial (supply-side only) | H2 storage enables temporal flexibility |

---

### 1.1 V2G (Vehicle-to-Grid)

**Configuration:** `config.yaml` → `sector.v2g: true`

**Key files:**
- `scripts/prepare_sector_network.py` (lines 2231-2389)
- `scripts/build_transport_demand.py` (lines 121-163)

**How it works:**
1. **EV Battery as Storage**: Electric vehicles are modeled with explicit battery storage (`Store` component)
2. **Bidirectional Charging**: V2G creates `Link` components that allow power flow from EV batteries back to the grid
3. **Availability Constraints**:
   - `bev_avail_max: 0.95` - Maximum plugged-in availability
   - `bev_avail_mean: 0.8` - Average availability
   - `bev_dsm_availability: 0.5` - Fraction of EVs available for V2G
4. **DSM Profile**: Checkpoint-based approach ensures minimum SOC at specific hours
   - `bev_dsm_restriction_time: 7` - 7 AM checkpoint
   - `bev_dsm_restriction_value: 0.8` - 80% minimum SOC at checkpoint

**Mathematical representation:**
```
EV Battery Store ←→ BEV Charger (Link) ←→ AC Bus
                ←→ V2G Link (when enabled) ←→ AC Bus
```

**Key parameters:**
```yaml
sector:
  bev_dsm: true
  bev_dsm_availability: 0.5
  bev_energy: 0.05  # MWh/vehicle
  bev_charge_efficiency: 0.9
  bev_charge_rate: 0.011  # MW/vehicle
  v2g: true
```

---

### 1.2 Residential Heating Flexibility

**Configuration:** `config.yaml` → `sector.residential_heat.dsm`

**Key files:**
- `scripts/prepare_sector_network.py` (lines 2772-3250)
- `scripts/build_hourly_heat_demand.py` (lines 29-69) - *new in this branch*

**Components of heating flexibility:**

#### A. Thermal Energy Storage (TES)

| Type | Application | Key Features |
|------|-------------|--------------|
| **Water Tanks** | Decentralized & Centralized | Charger/discharger links, standing losses ~1-2%/hr |
| **PTES (Pit Storage)** | Central heating only | Dynamic capacity option, max 90°C |
| **ATES (Aquifer Storage)** | Central heating only | Recovery factor 0.6, underground storage |

#### B. Heat DSM via Building Thermal Mass (NEW in this branch)

This branch introduces **residential heat demand-side management** based on the smartEn/DNV methodology.

**Mechanism:**
- Building thermal mass is represented as implicit storage
- Heat can be "pre-charged" (overheat) or "borrowed" (undercool)
- Checkpoint hours enforce that consumption requirements are met within 12-hour periods

**Configuration:**
```yaml
sector:
  residential_heat:
    dsm:
      enable: false  # Set to true to activate
      direction:
        - overheat   # Allow pre-heating
        - undercool  # Allow delayed heating
      restriction_value:
        2020: 0.06   # 6% of demand can be shifted
        2025: 0.16
        2030: 0.27
        2050: 0.40   # 40% by 2050
      restriction_time:
        - 10  # 10 AM checkpoint (in local time)
        - 22  # 10 PM checkpoint
```

**Key implementation details (from `build_hourly_heat_demand.py`):**
```python
def heat_dsm_profile(nodes, options):
    """
    Generate heat DSM availability profile with periodic restrictions.

    Creates a weekly profile that restricts heat storage availability at
    checkpoint hours to enforce consumption within 12-hour periods.
    """
    weekly_profile = np.ones(24 * 7)
    for i in options["residential_heat"]["dsm"]["restriction_time"]:
        weekly_profile[(np.arange(0, 7, 1) * 24 + int(i))] = 0
    # ... generates profile
```

**What the checkpoints achieve:**
- Prevents building thermal mass from acting as seasonal storage
- Ensures heat demand is met within day/night periods
- Creates short-term load shifting capability (up to 12 hours)

---

### 1.3 Industry with H2

**Key files:**
- `scripts/prepare_sector_network.py` (lines 4492-5000)
- `config.yaml` → `industry` section

**How H2 provides flexibility:**

The industry sector uses hydrogen for several processes, and because H2 can be stored, this creates *indirect* temporal flexibility:

| Process | H2 Requirement | Flexibility Source |
|---------|---------------|-------------------|
| **DRI Steel** | 1.7 MWh H2/t steel | H2 storage + variable production |
| **Ammonia (Haber-Bosch)** | 5.93 MWh H2/t NH3 | H2 storage |
| **Methanol** | Via methanolisation | H2 storage |
| **Fischer-Tropsch** | Synthetic fuels | H2 storage |

**Important clarification:** The *demand* for H2 from industry is fixed (constant hourly profile), but the *production* of H2 (via electrolysis) is flexible. H2 storage acts as a buffer, enabling:
- Electrolysis during low electricity prices
- Industry consumption decoupled from production timing

---

### 1.4 Planned/Future Developments

Based on current codebase activity and the heat_dsm_2025 branch:

| Feature | Status | Notes |
|---------|--------|-------|
| Heat DSM | In development (this branch) | ~40 commits, near completion |
| Industrial demand flexibility | Not implemented | No current plans found in codebase |
| Enhanced EV DSM | Implemented | Checkpoint-based approach |
| PTES dynamic capacity | Implemented | Seasonal temperature-dependent |
| ATES (Aquifer storage) | Implemented | Requires aquifer suitability data |

---

## 2. Industry Demand Calculation

### Confirmation: Your understanding is correct

**Data flow:**
```
JRC-IDEES 2021 → Annual totals per sector → Constant hourly values → Fixed inelastic demand
```

### Detailed breakdown:

#### Step 1: Data Retrieval
- **Source:** JRC-IDEES 2021 database
- **Script:** `scripts/retrieve_jrc_idees.py`
- **Coverage:** 11 major industrial sectors across EU countries

#### Step 2: Sector Ratios
- **Script:** `scripts/build_industry_sector_ratios.py`
- **Output:** Specific energy consumption (MWh/t material) per subsector
- **Conversion:** `toe_to_MWh = 11.630`

#### Step 3: Spatial Distribution
- **Scripts:** `scripts/build_industrial_production_per_node.py`, `scripts/build_industrial_energy_demand_per_node.py`
- **Method:** Hotmaps Industrial Database (georeferenced industrial sites in EU28)
- **Sectors covered:** Cement, basic chemicals, glass, iron and steel, non-ferrous metals, non-metallic minerals, paper, refineries

#### Step 4: Temporal Profile (FLAT)
- **Script:** `scripts/prepare_sector_network.py` (line 4698)
- **Conversion:**
```python
nhours = n.snapshot_weightings.generators.sum()
nyears = nhours / 8760
industrial_demand = pd.read_csv(industrial_demand_file) * 1e6 * nyears

# Creates CONSTANT hourly demand:
p_set = industrial_demand.loc[nodes, "hydrogen"] / nhours
```

#### Step 5: Network Integration
- **Component:** PyPSA `Load` with fixed `p_set`
- **Elasticity:** Zero (completely inelastic)
- **Time profile:** Flat (no diurnal or seasonal variation)

### Key observation

Unlike heat demand (which has hourly profiles based on temperature and BDEW patterns), **industrial demand is uniformly distributed across all hours**. This means:

- No representation of real industrial load patterns
- No weekend/weekday differentiation
- No seasonal variation (except for ambient temperature effects on some processes)
- No demand-side flexibility

---

## 3. Options for Industry Demand Flexibility

Based on your proposed approaches, here's an analysis of implementation strategies:

### Option A: Industry Demand as Fictional Generator

**Concept:** Treat demand reduction as negative generation

**PyPSA Implementation:**
```python
n.add("Generator",
      "industry_dsm_DE",
      bus="DE0 0 low voltage",
      carrier="industry_dsm",
      p_nom=max_shiftable_demand,
      p_min_pu=-1,  # Can "generate" (reduce demand) or "consume" (increase)
      p_max_pu=1,
      marginal_cost=dsm_activation_cost)
```

**Pros:**
- Simple to implement
- Can assign marginal costs to DSM activation
- Works well for demand curtailment

**Cons:**
- Doesn't naturally enforce energy conservation (shifted energy must be consumed later)
- May need additional constraints to prevent infinite demand reduction
- Not intuitive for load shifting (better for demand curtailment)

---

### Option B: Industry Demand as Flexible Storage

**Concept:** Model industrial processes as storage units

**PyPSA Implementation:**
```python
# Store represents "inventory" or production flexibility
n.add("Store",
      "industry_buffer_DE",
      bus="DE0 0 industry_demand",
      e_nom=daily_demand * max_shift_hours,
      e_cyclic=True,  # Enforce energy conservation
      standing_loss=0)  # No losses

# Links connect electricity to production
n.add("Link",
      "industry_consumption_DE",
      bus0="DE0 0 low voltage",
      bus1="DE0 0 industry_demand",
      efficiency=1.0,
      p_nom=max_consumption_rate)
```

**Pros:**
- Energy conservation automatically enforced via `e_cyclic=True`
- Can model inventory/buffer limits
- Intuitive for continuous processes

**Cons:**
- May not capture discrete batch processes well
- Needs careful calibration of storage capacity
- Doesn't capture ramp constraints

---

### Option C: Load Shifting with Intra-day Energy and Ramp Constraints (Recommended)

**Concept:** Explicit load shifting with time-based constraints (similar to Heat DSM implementation)

**PyPSA Implementation (following the Heat DSM pattern):**

```python
# 1. Create industry DSM bus
n.add("Bus", "DE0 0 industry_dsm", carrier="industry_dsm")

# 2. Create storage with checkpoint constraints
n.add("Store",
      "DE0 0 industry_dsm_store",
      bus="DE0 0 industry_dsm",
      e_nom_extendable=False,
      e_nom=shiftable_demand_max,
      e_cyclic=False,  # Checkpoints handle this
      e_min_pu=0,
      e_max_pu=dsm_profile)  # Profile with zeros at checkpoints

# 3. Link from electricity to DSM
n.add("Link",
      "DE0 0 industry_dsm_charger",
      bus0="DE0 0 low voltage",
      bus1="DE0 0 industry_dsm",
      efficiency=1.0,
      p_nom=max_ramp_rate)  # Ramp constraint

# 4. Modify base load to allow reduction
# Base demand becomes flexible within bounds
```

**Checkpoint Profile (similar to heat DSM):**
```python
def industry_dsm_profile(shift_window_hours=8):
    """
    Create checkpoint profile that enforces intra-day balancing.

    At checkpoint hours, storage must be empty (e_max_pu = 0),
    ensuring shifted load is consumed within the window.
    """
    checkpoints = [6, 14, 22]  # 8-hour windows
    weekly_profile = np.ones(24 * 7)
    for hour in checkpoints:
        weekly_profile[(np.arange(0, 7, 1) * 24 + hour)] = 0
    return weekly_profile
```

**Ramp Constraint Implementation:**
```python
# Option 1: Via p_nom on the link
p_nom = max_hourly_change  # MW/h ramp limit

# Option 2: Via custom constraint in solve_network.py
def add_industry_ramp_constraint(n, sns):
    """Add ramp rate constraints for industrial DSM."""
    industry_dsm_links = n.links.index[n.links.carrier == "industry_dsm"]

    p = get_var(n, "Link", "p")[industry_dsm_links]

    ramp_limit = n.links.loc[industry_dsm_links, "ramp_limit"]

    for i in range(1, len(sns)):
        lhs = p.loc[sns[i]] - p.loc[sns[i-1]]
        define_constraints(n, lhs, "<=", ramp_limit, f"industry_ramp_up_{i}")
        define_constraints(n, lhs, ">=", -ramp_limit, f"industry_ramp_down_{i}")
```

**Pros:**
- Follows established pattern (Heat DSM)
- Energy conservation via checkpoints
- Explicit ramp constraints possible
- Window-based flexibility (e.g., 4h, 8h, 12h)
- Can differentiate by industry subsector

**Cons:**
- More complex implementation
- Requires additional data (which industries can shift, by how much)
- May need industry-specific profiles

---

### Comparison Summary

| Aspect | Generator | Storage | Load Shifting (Recommended) |
|--------|-----------|---------|---------------------------|
| Energy Conservation | Manual | Automatic | Via checkpoints |
| Ramp Constraints | Difficult | Via p_nom | Explicit |
| Time Windows | Not natural | Via e_cyclic | Via profile checkpoints |
| Implementation Effort | Low | Medium | Medium-High |
| Alignment with Heat DSM | Low | Medium | High |
| Realism | Low | Medium | High |

---

## 4. Flexible Technology Modeling Examples

### Note on EURIMA and FORM ENERGY Projects

The PyPSA-EUR codebase does not contain specific references to EURIMA or FORM ENERGY project implementations. However, we can point to similar flexibility modeling patterns:

### Example 1: Long-Duration Storage (similar to FORM ENERGY iron-air batteries)

**Location:** `scripts/prepare_sector_network.py` → `add_storage` functions

```python
# Pattern used for H2 storage (multi-day/seasonal)
n.add("Store",
      nodes + " H2 Store",
      bus=nodes + " H2",
      e_nom_extendable=True,
      e_nom_max=h2_underground_max,  # Regional limits
      e_cyclic=True,
      capital_cost=costs.at["hydrogen storage underground", "investment"])
```

For iron-air or similar long-duration storage, you would add:
```python
n.add("Store",
      nodes + " iron-air",
      bus=nodes,  # Connected to electricity bus
      e_nom_extendable=True,
      e_nom_max=regional_potential,
      e_cyclic=True,
      standing_loss=0.0,  # Very low self-discharge
      capital_cost=iron_air_capex)

n.add("Link",
      nodes + " iron-air charger",
      bus0=nodes,
      bus1=nodes + " iron-air",
      efficiency=charge_efficiency,
      p_nom_extendable=True,
      capital_cost=charger_capex)

n.add("Link",
      nodes + " iron-air discharger",
      bus0=nodes + " iron-air",
      bus1=nodes,
      efficiency=discharge_efficiency,
      p_nom_extendable=True,
      capital_cost=discharger_capex)
```

### Example 2: Building Envelope / Thermal Mass (EURIMA-style)

**Location:** `scripts/prepare_sector_network.py` → Heat DSM implementation (this branch)

The Heat DSM implementation in this branch follows principles relevant to EURIMA (building insulation and thermal mass):

```python
# From prepare_sector_network.py
def add_heat_dsm(n, costs, options):
    """
    Add residential heat demand-side management using building thermal mass.

    Implementation based on smartEn/DNV methodology.
    """
    # DSM store represents building thermal mass
    n.add("Store",
          nodes + " residential rural heat dsm",
          bus=nodes + " residential rural heat",
          e_nom=dsm_potential,  # Based on building stock
          e_min_pu=dsm_profile,  # Checkpoint constraints
          e_max_pu=dsm_profile,
          e_cyclic=False)
```

The building renovation optimization is also implemented:
```python
# Retrofitting reduces heat demand at a cost
n.add("Generator",
      "building_retrofitting_" + node,
      bus=node + " heat",
      p_nom_extendable=True,
      p_nom_max=max_savings,
      capital_cost=retrofit_cost_per_mwh_saved)
```

---

## 5. PyPSA Explorer by OET

### Overview

PyPSA Explorer is a web-based visualization tool developed by Open Energy Transition (OET) for exploring PyPSA model results.

### Reliability Assessment

**What it is:**
- Frontend visualization interface for pre-computed PyPSA-EUR scenarios
- Shows aggregated results: capacities, generation mix, costs, emissions
- Allows comparison across scenarios and regions

**What it shows accurately:**
- Installed capacities by technology and region
- Annual generation and demand balances
- System costs and emissions
- Transmission network topology

**Limitations to be aware of:**
- Shows post-processed/aggregated results, not raw optimization outputs
- Temporal resolution may be reduced (e.g., representative periods to annual)
- May not show all model constraints and their effects
- Custom scenarios or recent model changes may not be reflected

**Recommendations for validation:**
1. Cross-check key metrics with direct model outputs (NetCDF files)
2. Verify that the scenario assumptions match your analysis
3. For detailed temporal analysis, use the full model results
4. Consider it a "first look" tool, not a replacement for detailed analysis

**For detailed model exploration, prefer:**
```python
import pypsa
n = pypsa.Network("results/networks/elec_s_256_ec_lcopt_Co2L-24H.nc")
n.statistics()  # Comprehensive statistics
n.generators_t.p.sum()  # Generation by timestep
```

---

## Summary

### Key Takeaways

1. **Current flexibility in PyPSA-EUR:**
   - V2G: Fully implemented with availability and DSM constraints
   - Residential heat: Thermal storage + new DSM via building thermal mass (this branch)
   - Industry H2: Indirect flexibility via H2 storage (demand itself is fixed)

2. **Industry demand is indeed:**
   - From JRC-IDEES data
   - Converted to constant hourly profiles
   - Completely inelastic (no demand flexibility)

3. **For industrial flexibility implementation:**
   - **Recommended approach:** Load shifting with checkpoints (Option C)
   - Follows the established Heat DSM pattern
   - Allows energy conservation and ramp constraints

4. **PyPSA Explorer:**
   - Good for initial exploration and scenario comparison
   - Cross-validate important results with direct model outputs

---

## Appendix: Key Configuration Locations

| Feature | Config Path |
|---------|-------------|
| V2G | `sector.v2g`, `sector.bev_dsm*` |
| Heat DSM | `sector.residential_heat.dsm.*` |
| Thermal Storage | `sector.tes`, `sector.district_heating.ates/ptes` |
| Industry | `industry.*` |
| Steel/H2 | `industry.DRI_fraction`, `industry.H2_DRI` |

---

*Document prepared from PyPSA-EUR branch `heat_dsm_2025`, December 2025*
