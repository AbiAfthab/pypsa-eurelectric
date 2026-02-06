# Industry DSR Implementation - Comprehensive Review

## Executive Summary

This document provides a comprehensive review of the industry DSR (Demand-Side Response) implementation, checking for logic errors, coding issues, Snakemake rule problems, and documenting expected differences from the standard model.

## 1. Logic Review

### ✅ Correct Logic

1. **Technology Breakdown Flow**:
   - ✅ If `technology_breakdown` is provided, only profiles with breakdown get DSR stores
   - ✅ Profiles without breakdown are skipped (no DSR)
   - ✅ If `technology_breakdown` is not provided at all, no DSR stores are created
   - ✅ Technology shares are normalized to sum to 1.0

2. **Auto-calculation of Shares**:
   - ✅ Only calculates for "Iron & steel industry" profile
   - ✅ Falls back gracefully if production data not available
   - ✅ User-provided shares take precedence over auto-calculated

3. **Negative-Only DSR**:
   - ✅ `e_max_pu = 0.0` prevents charging (load increase)
   - ✅ `e_min_pu = -max_reduction` allows discharge (load decrease)
   - ✅ At checkpoint hours, `e_min_pu = 0.0` forces store to empty
   - ✅ `max_reduction = min(flexibility_fraction, 1.0 - min_load)` correctly limits reduction

4. **H2-DRI-EAF Coupling**:
   - ✅ Constraint limits DRI dispatch based on H2 storage capacity
   - ✅ Handles both fixed and extendable H2 storage
   - ✅ Correctly calculates H2_per_DRI_electricity ratio

5. **Store Bus Assignment**:
   - ✅ Stores initially added to main AC buses
   - ✅ `insert_electricity_distribution_grid` moves them to low voltage buses
   - ✅ Stores end up on same buses as industry loads

### ⚠️ Potential Logic Issues

1. **Auto-calculation Limitation**:
   - ⚠️ Only implemented for "Iron & steel industry" profile
   - ⚠️ Other profiles with technology breakdown (e.g., "Non-metallic Minerals") cannot use "auto"
   - **Impact**: Low - users can provide manual shares for other profiles

2. **Technology Share Normalization**:
   - ⚠️ Normalization happens AFTER auto-calculation, which is correct
   - ⚠️ But if auto-calculation fails and shares don't sum to 1.0, normalization still happens
   - **Impact**: Low - normalization ensures shares always sum to 1.0

3. **Manufacturing Technology**:
   - ⚠️ "Manufacturing" is not in production data, so auto-calculation distributes remaining share
   - ⚠️ If user provides "Manufacturing": "auto", it gets equal share of remaining
   - **Impact**: Low - "Manufacturing" should typically have a fixed small share

4. **DSR Profile Fallback**:
   - ⚠️ If DSR profile file is missing, uses constant constraints (no checkpoints)
   - ⚠️ This means `e_cyclic` won't enforce periodic balancing
   - **Impact**: Medium - should warn user if profile file missing

## 2. Coding Review

### ✅ Correct Code

1. **Error Handling**:
   - ✅ Auto-calculation wrapped in try-except with graceful fallback
   - ✅ Checks for file existence before reading
   - ✅ Handles missing columns/data gracefully

2. **Data Types**:
   - ✅ Proper handling of DataFrame vs scalar for `e_max_pu`/`e_min_pu`
   - ✅ Correct reshaping for time-varying constraints
   - ✅ Proper index alignment

3. **Store Creation**:
   - ✅ Correct `e_nom` calculation: `P_flex.max() * shift_hours`
   - ✅ Proper carrier assignment: "industry dsr"
   - ✅ Correct `e_cyclic=True` and `e_initial=0.0`

### ⚠️ Potential Coding Issues

1. **Missing Import Check**:
   - ⚠️ `os.path.exists` used but `os` import not explicitly checked
   - **Fix**: Already imported at top of file (line 10: `import os`)

2. **Division by Zero**:
   - ⚠️ In auto-calculation: `total_production` could be 0
   - ✅ **Fixed**: Check `if total_production > 0:` before division

3. **H2-DRI Coupling Constraint**:
   - ⚠️ Division by `elec_dri_ratio` could be zero
   - ✅ **Fixed**: Check `if elec_dri_ratio == 0:` with warning (but not in current code)
   - **Recommendation**: Add check for `elec_dri_ratio == 0`

4. **Store Name Collision**:
   - ⚠️ Store names: `"{node} industry dsr {profile} {technology}"`
   - ✅ Should be unique (node + profile + technology combination is unique)

5. **DataFrame Index Alignment**:
   - ⚠️ When creating `e_max_pu`/`e_min_pu` DataFrames, index must match `n.snapshots`
   - ✅ **Fixed**: Uses `index=n.snapshots` explicitly

## 3. Snakemake Review

### ✅ Correct Rules

1. **build_industry_dsr_profile Rule**:
   - ✅ Input: `industrial_electricity_demand_per_profile_temporal`
   - ✅ Output: `industrial_dsr_profile`
   - ✅ Params: `restriction_time`, `technology_breakdown`
   - ✅ Conditional: Only runs if `industry.dsr.enable`

2. **prepare_sector_network Rule**:
   - ✅ Conditional inputs for DSR files
   - ✅ `industrial_electricity_profiles_per_profile` only if `temporal_electricity_industry_load` and `dsr.enable`
   - ✅ `industrial_dsr_profile` only if `dsr.enable`

### ⚠️ Potential Snakemake Issues

1. **Rule Dependency**:
   - ⚠️ `build_industry_dsr_profile` depends on `build_industrial_energy_demand_per_node` (for per-profile temporal file)
   - ✅ **Fixed**: Dependency chain is correct in rules

2. **Conditional Input Handling**:
   - ⚠️ `industrial_dsr_profile` can be empty list `[]` if DSR not enabled
   - ✅ **Fixed**: Code checks with `getattr` and handles `None`/empty list

3. **Technology Breakdown Parameter**:
   - ⚠️ `technology_breakdown` passed as param to `build_industry_dsr_profile`
   - ✅ **Fixed**: Uses `config_provider` with `default={}`

## 4. Edge Cases

### ✅ Handled Edge Cases

1. **Empty Technology Breakdown**:
   - ✅ If `technology_breakdown` is empty dict, no DSR stores created
   - ✅ Logs informative message

2. **Technology with Zero Share**:
   - ✅ Technologies with `share <= 0` are skipped
   - ✅ No stores created for zero-share technologies

3. **Technology with Zero Flexibility**:
   - ✅ Technologies with `flexibility_fraction <= 0` are skipped
   - ✅ No stores created for non-flexible technologies

4. **Missing DSR Profile File**:
   - ✅ Falls back to constant constraints
   - ⚠️ **Issue**: Should warn user (currently silent)

5. **Missing Restriction Time**:
   - ✅ Falls back to profile-level `restriction_time`
   - ✅ If still missing, uses constant constraints

6. **No H2 Storage for DRI**:
   - ✅ Logs warning but continues
   - ✅ DRI flexibility may be overestimated (expected behavior)

7. **Extendable H2 Storage**:
   - ✅ Uses model variable `Store-e_nom` for extendable storage
   - ✅ Allows optimizer to build storage to enable DRI flexibility

### ⚠️ Unhandled Edge Cases

1. **Negative Shares**:
   - ⚠️ Negative shares are skipped (`if share <= 0`)
   - ⚠️ But normalization still happens, which could cause issues
   - **Impact**: Low - negative shares shouldn't occur in valid config

2. **Technology Not in Breakdown**:
   - ⚠️ If technology in `flexibility_fraction` but not in `technology_breakdown`, it's ignored
   - **Impact**: Low - user error, but could warn

3. **Profile in Breakdown but No Load**:
   - ⚠️ If profile has breakdown but no load columns, skipped silently
   - **Impact**: Low - expected if profile has no load

## 5. Expected Differences from Standard Model

### Model Structure Changes

1. **New Components**:
   - ✅ New `Store` components with carrier "industry dsr"
   - ✅ One store per `(node, profile, technology)` combination
   - ✅ Stores on "low voltage" buses (same as industry loads)

2. **Load Behavior**:
   - ✅ Industry electricity loads remain fixed (baseline)
   - ✅ Net demand = baseline + store dispatch
   - ✅ Store dispatch can be positive (charge/increase load) or negative (discharge/decrease load)

3. **Constraints**:
   - ✅ Time-varying `e_max_pu`/`e_min_pu` based on checkpoint hours
   - ✅ `e_cyclic=True` enforces energy neutrality over optimization horizon
   - ✅ Checkpoint hours force store to empty (demand balanced within periods)

### Optimization Behavior Changes

1. **Load Shifting**:
   - ✅ Industry can shift load from high-price to low-price hours
   - ✅ Shifting limited by `flexibility_fraction` and `shift_hours`
   - ✅ Periodic balancing enforced at checkpoint hours

2. **Price Response**:
   - ✅ Industry load should correlate with electricity prices
   - ✅ Load increases (charge) when prices are low
   - ✅ Load decreases (discharge) when prices are high

3. **System Costs**:
   - ✅ Should reduce system costs by shifting demand
   - ✅ Reduces need for expensive peaking generation
   - ✅ Better utilization of renewable generation

### Technology-Specific Differences

1. **Steel Technologies**:
   - ✅ Scrap-EAF: High flexibility (85%), short shift (2h)
   - ✅ H2-DRI-EAF: Moderate flexibility (20%), longer shift (6h), limited by H2 storage
   - ✅ BF-BOF-CCUS: Low flexibility (5%), short shift (1h)

2. **Aluminium Technologies**:
   - ✅ Aluminium-primary/secondary: Conservative flexibility (12.5%), 3h shift
   - ✅ Alumina: Not flexible (0%)

3. **Negative-Only DSR** (e.g., Chlor-alkali):
   - ✅ Can only reduce load (discharge), not increase (charge)
   - ✅ Minimum load constraint (e.g., 70% of baseline)
   - ✅ Load reduction limited by both flexibility and min_load

4. **H2-DRI-EAF Coupling**:
   - ✅ DRI flexibility constrained by available H2 storage capacity
   - ✅ If H2 storage is extendable, optimizer can build more to enable flexibility
   - ✅ Constraint: `|DRI_dispatch| ≤ H2_storage_capacity / 5.28` (MWh_H2/MWh_el ratio)

### Expected Output Differences

1. **Network File**:
   - ✅ Contains new `Store` components with carrier "industry dsr"
   - ✅ Store names: `"{node} industry dsr {profile} {technology}"`
   - ✅ Stores have time-varying `e_max_pu`/`e_min_pu` constraints

2. **Load Profiles**:
   - ✅ Baseline load: Fixed (from FfE profiles)
   - ✅ Net load: Baseline + store dispatch (varies with optimization)
   - ✅ Store dispatch: Can be positive or negative

3. **Optimization Results**:
   - ✅ Lower system costs (due to load shifting)
   - ✅ Better price correlation with industry load
   - ✅ Store states should be zero at checkpoint hours
   - ✅ Total store dispatch over horizon should be ~0 (energy neutral)

## 6. Recommendations

### High Priority

1. **Add Warning for Missing DSR Profile**:
   ```python
   if dsr_profile_df is None:
       logger.warning("DSR profile file not found. Using constant constraints (no checkpoints).")
   ```

2. **Add Check for elec_DRI == 0**:
   ```python
   if elec_dri_ratio == 0:
       logger.warning("elec_DRI is 0, cannot calculate H2_per_DRI_electricity_ratio. Skipping coupling constraint.")
       return
   ```

### Medium Priority

1. **Extend Auto-calculation**:
   - Support auto-calculation for other profiles (e.g., "Non-metallic Minerals")
   - Would require mapping technology names to sectors for each profile

2. **Add Validation**:
   - Warn if technology in `flexibility_fraction` but not in `technology_breakdown`
   - Warn if profile in `technology_breakdown` but has no load

### Low Priority

1. **Documentation**:
   - Add more examples to config file
   - Document expected behavior differences

2. **Testing**:
   - Add unit tests for auto-calculation
   - Add integration tests for DSR behavior

## 7. Summary

### ✅ Implementation Status: **READY FOR TESTING**

The implementation is logically sound and handles most edge cases correctly. The main areas for improvement are:

1. Add warnings for missing DSR profile file
2. Add check for `elec_DRI == 0` in H2-DRI coupling
3. Consider extending auto-calculation to other profiles

### Expected Test Results

When running the model with industry DSR enabled:

1. **Network should contain**:
   - New Store components with carrier "industry dsr"
   - Stores on low voltage buses
   - Time-varying constraints

2. **Optimization should show**:
   - Load shifting behavior (correlation with prices)
   - Energy-neutral store dispatch (total ~0)
   - Store states at zero at checkpoint hours
   - Lower system costs compared to baseline

3. **Diagnostic scripts should confirm**:
   - Stores and loads on same buses
   - Correct constraint values at checkpoint hours
   - Energy balance maintained
