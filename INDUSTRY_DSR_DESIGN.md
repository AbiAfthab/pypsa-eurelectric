# Industry electricity demand-side response (DSR) – design

This document describes the **design** for industry flexibility based on temporal FfE profiles. Naming follows “DSR” for industry (like “DSM” for residential heat). Modelling choices, config, and mapping to the existing residential heat DSM logic.

## Goal

- Model **industry electricity flexibility** as virtual storage: part of industrial load can **shift in time** (e.g. 20% of cement load up to 2 h).
- Demand is **energy-neutral** over the horizon: load can move between hours but total demand over the optimisation horizon is unchanged.
- Follow the **same logic as `residential_heat.dsm`**: baseline load stays a normal Load; a **Store** on the electricity bus represents the shiftable share (charge = over-consumption now, discharge = under-consumption later).

## Config (already added)

In `config.default.yaml` and test configs under `industry`:

- **`industry.dsr.enable`**  
  Toggle industry electricity DSR on/off (same idea as `residential_heat.dsm.enable`).

- **`industry.dsr.flexibility_fraction`**  
  Share of load that can be shifted, **per FfE profile** (0..1).  
  Keys must match the FfE profile names used in `INDUSTRY_CATEGORY_TO_PROFILE` in `build_industrial_energy_demand_per_node.py`, e.g.:
  - `"Non-metallic Minerals"`: 0.20 (e.g. cement)
  - `"Iron & steel industry"`: 0.15
  - `"Paper, Pulp and Print"`: 0.10
  - etc.

- **`industry.dsr.shift_hours`**  
  Maximum shift duration in hours, **per FfE profile**, e.g.:
  - `"Non-metallic Minerals"`: 2
  - `"Paper, Pulp and Print"`: 8
  - etc.

- **`industry.dsr.restriction_time`**  
  Checkpoint hours (0–23) **per FfE profile** at which the DSR store must be empty; demand is then balanced within each period between checkpoints. Different sectors have different operating times (e.g. 24/7 vs day shift). Example: `"Iron & steel industry": [6, 18]`, `"Non-metallic Minerals": [0, 12]`.

- **`industry.dsr.restriction_value`**  
  Scale factor (0..1) for the DSR profile; 1.0 = full flexibility between checkpoints.

So: “20% of cement load can shift for max 2 h” is expressed as `flexibility_fraction["Non-metallic Minerals"]: 0.20` and `shift_hours["Non-metallic Minerals"]: 2`.

**FfE profile names vs PyPSA industry categories:** Config keys (`flexibility_fraction`, `shift_hours`, `restriction_time`) use **FfE profile names** (e.g. "Iron & steel industry", "Non-metallic Minerals"), not the specific PyPSA industry categories (e.g. "Electric arc", "Integrated steelworks", "Cement", "Pharmaceutical products etc."). The mapping is in `INDUSTRY_CATEGORY_TO_PROFILE` in `build_industrial_energy_demand_per_node.py`: several PyPSA sectors map to one FfE profile. Load and Stores are at FfE profile level, so config is keyed by FfE profile.

## Inputs (conceptual)

1. **Baseline industrial electricity load per node (hourly)**  
   Already available when `temporal_electricity_industry_load: true`: `industry_load[node, t]` in MW from the industrial electricity profiles CSV.

2. **Flexibility availability profile**  
   `flex_availability[node, t]` in [0..1]: at each hour, which fraction of (flexible) load is allowed to over-/under-consume.  
   Analogous to `heat_dsm_profile` in residential: can be built from FfE profiles and config (e.g. constant `flexibility_fraction` in time, or time-varying if needed). Must be aligned to `n.snapshots`.

3. **Shift duration**  
   From config: `shift_hours[profile]` (hours). Used to size the energy buffer (see below).

## Mapping to residential heat DSM

Same structure as in `prepare_sector_network.py` for heat DSM:

- **Baseline load**  
  Stays a normal **Load** with `p_set = industry_load` (MW).

- **Virtual Store** on the **electricity bus** (same bus as the industry load):
  - **Carrier** e.g. `"industry dsr"`.
  - **Charge** → extra draw from the bus (over-consumption now).
  - **Discharge** → less draw later (pay back earlier over-consumption).
  - **`e_cyclic = True`** so that over the full horizon the shift is energy-neutral (demand is only shifted, not created or destroyed).
  - **`e_initial = 0`** (optional but clear).
  - **`standing_loss = 0`** (no leakage).
  - **`e_nom`** = energy capacity of the “shift buffer” (MWh).
  - **`e_max_pu[node, t]`** = upper bound on state (fraction of `e_nom`) → how much over-consumption credit can be built at `t`.
  - **`e_min_pu[node, t]`** = lower bound → how much under-consumption debt is allowed at `t`.  
  Typically: `e_max_pu = flex_availability`, `e_min_pu = -flex_availability` (both directions).

**Sizing `e_nom` (buffer size):**

- Flexible power at each hour:  
  `P_flex(node, t) = baseline_load(node, t) * flex_availability(node, t)` (MW).
- Choose a representative power, e.g. `P_flex_max = P_flex.max()` or a high quantile.
- Then:  
  `e_nom(node) = P_flex_max * shift_hours` (MWh).  
  So “X MW flexible for H hours” → buffer of X·H MWh.  
  If implementation is **per FfE profile**: same formula per profile (and possibly per node), using that profile’s `shift_hours` and its share of load.

## Sector-specific (FfE profile) flexibility

Two possible implementation options:

- **Option A – One aggregated industry DSR store per node**  
  Single Store per node; `flex_availability` and `e_nom` derived from a weighted mix of sector parameters. Simpler, but different shift windows per sector are only approximated.

- **Option B – One Store per FfE profile per node**  
  Each profile has its own `flexibility_fraction`, `shift_hours`, and (if available) per-profile load. One Store per (node, profile). Allows different shift windows (e.g. cement 2 h, pulp 8 h) and is consistent with the per-profile config above. Requires either:
  - per-profile (or per-sector) temporal load output from the build (e.g. extra file or MultiIndex columns), or
  - recomputing profile-level load in the sector script from existing data.

Config is already per FfE profile so that Option B can be implemented without config changes.

## Rate limits (power bounds)

Residential heat DSM uses a Store without an explicit power (MW) cap; flexibility is effectively limited by `e_nom` and the time-varying `e_max_pu`/`e_min_pu`. The same can be used for industry DSR. If in the future you want explicit ramp/rate limits (e.g. max MW charge/discharge per hour), that would require either a StorageUnit with `p_nom` and `max_hours`, or additional constraints (e.g. Link-based). Not part of the current design.

## Constraint: demand per day vs per horizon

- **What is enforced today (industry DSR):**  
  With **`e_cyclic=True`**, each industry DSR Store must end the optimisation horizon with the same state it started (e.g. `e_initial=0` ⇒ net charge over the horizon = 0). So **total demand over the full optimisation horizon** is preserved: the integral of (baseline load − store power) over the horizon equals the integral of baseline load, i.e. demand is only shifted in time, not created or destroyed.  
  Because there is **one Store per FfE profile per node**, this holds **per sector (profile)** as well: each sector’s total electricity demand over the horizon is met.

- **Per day:**  
  The current industry DSR formulation does **not** enforce that **each day’s** demand is met. The solver can shift load from one day to another as long as over the whole horizon the net shift is zero.

---

### How residential heat DSM enforces “demand met within each period”

Residential heat DSM also uses **`e_cyclic=True`** (so full-horizon net shift is zero), but it enforces **demand met within each sub-period** (e.g. each 12 hours) by **checkpoint hours**:

1. **`restriction_time`** (e.g. `[10, 22]`) defines **checkpoint hours** (e.g. 10:00 and 22:00) at which the thermal store must be **empty**.
2. The **heat DSM profile** is built in `build_hourly_heat_demand.py`: it is 1.0 at most hours and **0.0 at those checkpoint hours** (same hour every day).
3. In `prepare_sector_network.py`, **`e_max_pu`** and **`e_min_pu`** are set from that profile (scaled by `restriction_value`). So at checkpoint hours, **`e_max_pu = 0`** and **`e_min_pu = 0`**.
4. The Store state must satisfy `e_nom * e_min_pu ≤ e ≤ e_nom * e_max_pu`. At checkpoint hours both bounds are 0, so **the store state is forced to 0** at 10:00 and 22:00 every day.
5. So between two consecutive checkpoints (e.g. 10:00→22:00 or 22:00→10:00), the store starts at 0 and must end at 0 ⇒ **net charge over that 12-hour window is zero** ⇒ demand is balanced within each 12-hour period. Load can shift freely *within* each period, but cannot be carried across checkpoints.

So residential DSM preserves “demand met within each period” **not** by a separate daily constraint, but by **time-varying `e_max_pu` / `e_min_pu` that are zero at checkpoint hours**, forcing the store to settle at those times.

---

### Industry DSR checkpoint profile per sector (implemented)

To enforce that **each day’s** (or each period’s) industry demand is met while still allowing load to shift within the period:

1. **Build an industry DSR “checkpoint” profile** (analogous to `heat_dsm_profile`): e.g. 1.0 at most hours and **0.0 at chosen checkpoint hours** (e.g. one hour per day such as midnight, or two per day like 6:00 and 18:00).
2. Use that profile as **time-varying `e_max_pu` and `e_min_pu`** for the industry DSR Stores (instead of constant `flexibility_fraction` and `-flexibility_fraction`). At checkpoint hours the store state is forced to 0, so net shift is zero over each interval between checkpoints ⇒ demand is met per day (or per 12h, depending on checkpoint choice).
3. Config could add e.g. **`industry.dsr.restriction_time`** (list of hours, like residential) and optionally **`restriction_value`** (scale factor on the profile). The build script would produce an industry DSR profile file, and `prepare_sector_network` would use it when adding the Stores.

That would mirror the residential heat DSM logic and give you “demand met per period, load can shift within the period” for industry DSR.

## Summary

- **Config:** `industry.dsr.enable`, `industry.dsr.flexibility_fraction` (per FfE profile), `industry.dsr.shift_hours` (per FfE profile), `industry.dsr.restriction_time` (per FfE profile), `industry.dsr.restriction_value`. Config keys use **FfE profile names**, not PyPSA industry categories.
- **Model:** Baseline industry load remains a Load; add a virtual Store per (node, profile) on the electricity bus with `e_cyclic=True`, time-varying `e_max_pu`/`e_min_pu` from the DSR checkpoint profile (0 at checkpoint hours ⇒ demand balanced per period), `e_nom` from flexible power × shift_hours.
- **Demand:** With checkpoint profile: demand is balanced **within each period between checkpoints** per sector. Total demand over the full horizon is also preserved.

## Implementation (Option B)

Option B is implemented:

1. **`scripts/build_industrial_energy_demand_per_node.py`**  
   - `create_nodal_electricity_profiles_per_profile()` builds hourly demand per (node, FfE profile) in MW.  
   - Writes `industrial_electricity_demand_per_profile_temporal_base_s_{clusters}_{planning_horizons}.csv` (columns `node|profile`, index = snapshots).

2. **`scripts/build_industry_dsr_profile.py`**  
   - Builds industry DSR checkpoint profile per FfE profile: (snapshots × profiles), value 0 at `restriction_time[profile]` hours, 1.0 elsewhere.  
   - Writes `industrial_dsr_profile_base_s_{clusters}_{planning_horizons}.csv`.

3. **`rules/build_sector.smk`**  
   - `build_industrial_energy_demand_per_node` outputs `industrial_electricity_demand_per_profile_temporal`.  
   - `build_industry_dsr_profile`: input = per-profile temporal, params = `restriction_time`, output = `industrial_dsr_profile`.  
   - `prepare_sector_network`: conditional inputs `industrial_electricity_profiles_per_profile` and `industrial_dsr_profile` when `industry.dsr.enable`.

4. **`scripts/prepare_sector_network.py`** (in `add_industry`)  
   - When DSR enabled: reads per-profile load and (if present) DSR profile; builds `e_nom = P_flex.max() * shift_hours` per (node, profile); uses time-varying `e_max_pu`/`e_min_pu` from DSR profile × `flexibility_fraction` × `restriction_value` (or constant if no profile file); adds one Store per (node, profile).

5. **`config/plotting.default.yaml`**  
   - Carrier `industry dsr` has a plotting color.

6. **Visualizing industry DSR (with vs without shift)**  
   - **Script:** `scripts/plot_industry_dsr_comparison.py` loads a solved network (with industry DSR) and plots: (1) baseline industry electricity demand (fixed Load); (2) net industry demand (baseline + industry DSR Store dispatch) so you can see how load is shifted; (3) store dispatch (shift) in a second panel.  
   - **Snakemake:** rule `plot_industry_dsr_comparison` in `rules/postprocess.smk` produces `results/.../maps/static/...-industry_dsr_comparison.pdf` from the solved sector network. Run after solving (e.g. `snakemake plot_industry_dsr_comparison` with the right config/wildcards).  
   - **Two-network comparison:** To compare “with DSR” vs “without DSR”, run the workflow twice (config with `industry.dsr.enable: true` and with `false`), then run the script manually:  
     `python scripts/plot_industry_dsr_comparison.py --network-with-dsr path/with_dsr.nc --network-without-dsr path/without_dsr.nc --output comparison.pdf`
