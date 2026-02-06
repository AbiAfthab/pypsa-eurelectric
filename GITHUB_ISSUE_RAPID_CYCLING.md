# Industry DSR: Rapid Charge/Discharge Cycling Behavior

## Problem Description

The current industry DSR implementation exhibits rapid charge/discharge cycling, where stores switch between positive (charge/increase load) and negative (discharge/decrease load) dispatch on an hourly basis. While this is mathematically optimal from a cost-minimization perspective, it may not be physically realistic for industrial processes.

### Current Behavior

- Industry DSR stores can charge and discharge freely within their energy bounds (`e_max_pu`/`e_min_pu`)
- No constraints on power ramp rates or minimum duration in charge/discharge mode
- Optimizer exploits hourly price differences by rapidly switching between charge and discharge
- This results in "sawtooth" dispatch patterns with frequent sign changes

### Example

```
Hour 1: Charge +10 MW  (price: 30 €/MWh)
Hour 2: Discharge -8 MW (price: 50 €/MWh)
Hour 3: Charge +12 MW  (price: 25 €/MWh)
Hour 4: Discharge -10 MW (price: 45 €/MWh)
...
```

## Comparison with Residential Heat DSM

Residential heat DSM uses the same `Store` component but exhibits smoother behavior. Key differences:

| Feature | Residential Heat DSM | Industry DSR |
|---------|---------------------|--------------|
| Component | `Store` | `Store` |
| `standing_loss` | > 0 (thermal losses) | 0.0 |
| Checkpoint periods | 12 hours (e.g., [10, 22]) | 24 hours (e.g., [0]) or 12 hours |
| Unidirectional option | Yes (overheat/undercool) | Yes (`negative_only`) |
| Rapid cycling | Less common | More common |

**Why heat DSM is smoother:**
1. **Thermal losses** (`standing_loss > 0`) penalize holding energy, reducing rapid cycling
2. **Shorter checkpoint periods** (12h) create natural boundaries
3. **Physics-based constraints** (heat pump COP, comfort bands) add implicit limits

## Current Implementation

Industry DSR stores are created with:
```python
n.add(
    "Store",
    store_names,
    bus=e_nom_series.index.tolist(),
    carrier="industry dsr",
    standing_loss=0.0,  # No losses
    e_cyclic=True,
    e_initial=0.0,
    e_nom=e_nom,
    e_max_pu=e_max_pu,  # Time-varying from checkpoint profile
    e_min_pu=e_min_pu,  # Time-varying from checkpoint profile
)
```

**Constraints:**
- Energy limits: `e_nom * e_min_pu ≤ e ≤ e_nom * e_max_pu`
- Cyclic constraint: `e_initial = e_final` (energy neutral over horizon)
- Checkpoint hours: Store must be empty at specified hours
- **No power limits** (no `p_nom`)
- **No ramp rate constraints**
- **No minimum duration constraints**

## Proposed Solutions


### Option 1: Switch to StorageUnit (Robust Solution)

Use `StorageUnit` instead of `Store` to get built-in power and duration limits:

```python
n.add(
    "StorageUnit",
    store_names,
    bus=e_nom_series.index.tolist(),
    carrier="industry dsr",
    p_nom=P_flex.max(),  # Power limit (MW)
    max_hours=tech_shift_hours,  # Duration limit (hours)
    standing_loss=0.0,
    cyclic_state_of_charge=True,
    state_of_charge_initial=0.0,
    # Note: StorageUnit uses p_max_pu/p_min_pu instead of e_max_pu/e_min_pu
)
```

**Pros:**
- Built-in power and duration limits
- More realistic behavior
- Prevents rapid cycling naturally

**Cons:**
- Requires refactoring (different API)
- `p_max_pu`/`p_min_pu` instead of `e_max_pu`/`e_min_pu`
- Need to handle time-varying constraints differently

### Option 2: Add Ramp Rate Constraints (Custom)

Add custom constraints limiting the change in dispatch per hour:

```python
# In solve_network.py, add to extra_functionality:
def add_dsr_ramp_constraints(n, snapshots):
    industry_dsr_stores = n.stores[n.stores.carrier == "industry dsr"]
    if industry_dsr_stores.empty:
        return
    
    store_p = n.model["Store-p"]
    max_ramp = 0.5  # Max 50% of e_nom per hour (configurable)
    
    for store in industry_dsr_stores.index:
        e_nom = n.stores.loc[store, "e_nom"]
        max_ramp_power = e_nom * max_ramp
        
        # Ramp up: p[t] - p[t-1] <= max_ramp_power
        # Ramp down: p[t] - p[t-1] >= -max_ramp_power
        for t in range(1, len(snapshots)):
            n.model.add_constraints(
                store_p.loc[snapshots[t], store] - store_p.loc[snapshots[t-1], store] <= max_ramp_power,
                name=f"DSR_ramp_up_{store}_{t}"
            )
            n.model.add_constraints(
                store_p.loc[snapshots[t], store] - store_p.loc[snapshots[t-1], store] >= -max_ramp_power,
                name=f"DSR_ramp_down_{store}_{t}"
            )
```

**Pros:**
- Keeps `Store` components
- Configurable ramp rates per technology
- Flexible implementation

**Cons:**
- Adds many constraints (2 per store per hour)
- More complex implementation
- Requires config parameter for ramp rates so more literature review for consistent data



## Questions for Discussion
FIRT OF ALL....
1. **Is rapid cycling a problem?** 
   - Is this behavior acceptable for the use case?
   - Or should we enforce more realistic constraints? 

2. **Which solution do you suggest?**
   - Robust solution (StorageUnit)?
   - Custom constraints (ramp rates)?
   - Other ideas?

3. **What are realistic constraints for industrial processes?**
   - What are typical ramp rates for different industries? Do you have already this data available by any chance?
   - What are minimum duration requirements?
   - Should constraints be technology-specific?


## Related Code
(NOT COMMITTED YET)
- Industry DSR implementation: `scripts/prepare_sector_network.py` (lines ~5070-5370) NOT COMMITTED YET
- Residential heat DSM: `scripts/prepare_sector_network.py` (lines ~2976-3030)
- Design document: `INDUSTRY_DSR_DESIGN.md` (line 97-99 mentions rate limits)

## Additional Context

- Industry DSR uses technology-specific flexibility (steel, aluminium, cement, etc.)
- Different technologies may have different constraints
- Some technologies are "negative only" (can only reduce load, not increase)
- H2-DRI-EAF has coupling constraints with H2 storage

## References

- PyPSA Store documentation: https://pypsa.readthedocs.io/en/latest/components.html#store
- PyPSA StorageUnit documentation: https://pypsa.readthedocs.io/en/latest/components.html#storageunit
- Residential heat DSM design: `doc/supply_demand.rst` (lines 172-199)
