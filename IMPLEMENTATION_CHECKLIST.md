# Industry DSR Implementation Checklist

## ✅ Core Features Implemented

### 1. Technology-Specific DSR (technology_breakdown)
- ✅ **Location**: `scripts/prepare_sector_network.py` (lines ~5089-5370)
- ✅ **Functionality**: 
  - Splits FfE profiles into technologies based on `technology_breakdown`
  - Creates separate DSR stores per `(node, profile, technology)` combination
  - Only profiles with `technology_breakdown` get DSR stores
  - Profiles without breakdown are skipped (no DSR)
- ✅ **Config**: `technology_breakdown` section in config
- ✅ **Snakemake**: `build_industry_dsr_profile` rule passes `technology_breakdown` param

### 2. Auto-Calculation of Technology Shares
- ✅ **Location**: `scripts/prepare_sector_network.py` (lines ~5123-5198)
- ✅ **Functionality**:
  - Calculates shares from `industrial_production_per_node` data
  - Maps technology names to PyPSA sector names
  - Supports `"auto"` keyword in config
  - Falls back gracefully if production data not available
  - User-provided shares take precedence
- ✅ **Mapping**: Includes steel and aluminium technologies
- ✅ **Config**: Can use `"auto"` for technology shares

### 3. Negative-Only DSR
- ✅ **Location**: `scripts/prepare_sector_network.py` (lines ~5253-5334)
- ✅ **Functionality**:
  - Checks `negative_only` config flag per technology
  - Sets `e_max_pu = 0.0` (prevents charging/increasing load)
  - Sets `e_min_pu = -max_reduction` (allows discharging/reducing load)
  - Respects checkpoint hours (forces store to 0)
- ✅ **Config**: `negative_only` section with `"profile|technology": true`
- ✅ **Use case**: Chlor-alkali (can only reduce load, not increase)

### 4. Minimum Load Constraint (min_load)
- ✅ **Location**: `scripts/prepare_sector_network.py` (lines ~5259-5267)
- ✅ **Functionality**:
  - Reads `min_load` config per technology (fraction of baseline)
  - Calculates `max_reduction = min(flexibility_fraction, 1.0 - min_load)`
  - Limits load reduction for negative-only DSR
  - Example: `min_load: 0.70` means load cannot go below 70% of baseline
- ✅ **Config**: `min_load` section with `"profile|technology": fraction`
- ✅ **Use case**: Chlor-alkali (column stability constraint)

### 5. H2-DRI-EAF DSR-H2 Storage Coupling
- ✅ **Location**: `scripts/solve_network.py` (lines ~1165-1280, ~1336-1340)
- ✅ **Functionality**:
  - Finds DRI DSR stores (those with "H2-DRI-EAF" in name)
  - Finds corresponding H2 storage stores at same node
  - Adds constraints: `|DRI_dispatch| ≤ H2_storage_capacity / (H2_DRI / elec_DRI)`
  - Handles both fixed and extendable H2 storage
  - Uses `H2_DRI` and `elec_DRI` from config
- ✅ **Integration**: Called from `extra_functionality` in `solve_network.py`
- ✅ **Config**: Uses existing `industry.H2_DRI` and `industry.elec_DRI` parameters

### 6. Aluminium Flexibility Parameters
- ✅ **Location**: 
  - Auto-calculation mapping: `scripts/prepare_sector_network.py` (lines ~5132-5134)
  - Config example: `config/examples/config.industry.dsr.technology.yaml`
- ✅ **Functionality**:
  - Aluminium technologies included in `technology_to_sector` mapping
  - Conservative values: 12.5% flexible, 3h shift window
  - Daily checkpoint at midnight
- ✅ **Config**: Added to test config with conservative values

### 7. DSR Profile Building (Technology-Specific)
- ✅ **Location**: `scripts/build_industry_dsr_profile.py` (lines ~74-145)
- ✅ **Functionality**:
  - Handles `technology_breakdown` parameter
  - Builds profiles for `"profile|technology"` keys
  - Falls back to profile-level if technology-specific not found
  - Creates checkpoint profiles (0 at checkpoint hours, 1.0 elsewhere)
- ✅ **Snakemake**: Rule passes `technology_breakdown` param

### 8. Store Bus Assignment
- ✅ **Location**: 
  - Initial: `scripts/prepare_sector_network.py` (lines ~5355-5366)
  - Move to low voltage: `scripts/prepare_sector_network.py` (lines ~1587-1591)
- ✅ **Functionality**:
  - Stores initially added to main AC buses
  - `insert_electricity_distribution_grid` moves them to "low voltage" buses
  - Ensures stores are on same buses as industry loads

## ✅ Error Handling & Warnings

### 1. Missing DSR Profile Warning
- ✅ **Location**: `scripts/prepare_sector_network.py` (lines ~5092-5106)
- ✅ **Functionality**: Warns if DSR profile file not found

### 2. H2-DRI Coupling Safety Checks
- ✅ **Location**: `scripts/solve_network.py` (lines ~1193-1201)
- ✅ **Functionality**: 
  - Checks if `elec_DRI == 0` (prevents division by zero)
  - Warns if no H2 storage found
  - Returns early if conditions not met

### 3. Auto-Calculation Error Handling
- ✅ **Location**: `scripts/prepare_sector_network.py` (lines ~5194-5200)
- ✅ **Functionality**: Try-except block with graceful fallback

## ✅ Configuration Files

### 1. Example Config
- ✅ **Location**: `config/examples/config.industry.dsr.technology.yaml`
- ✅ **Content**: 
  - Complete technology breakdown examples
  - Steel and aluminium technologies
  - Negative-only DSR example (Chlor-alkali)
  - Min_load example
  - H2-DRI-EAF coupling notes

### 2. Test Config
- ✅ **Location**: `config/test/config.industry.flex.yaml`
- ✅ **Content**: 
  - Technology breakdown for "Iron & steel industry"
  - Auto-calculation enabled
  - Technology-specific parameters

## ✅ Documentation

### 1. Technology Breakdown Documentation
- ✅ **Location**: `doc/industry_dsr_technology_breakdown.md`
- ✅ **Content**: 
  - Overview of technology-specific DSR
  - Configuration examples
  - Auto-calculation explanation
  - Negative-only and min_load features

### 2. Release Notes
- ✅ **Location**: `doc/release_notes.rst`
- ✅ **Content**: Industry DSR feature documented

## ⚠️ Known Limitations

1. **Auto-calculation**: Only implemented for "Iron & steel industry" profile
   - Other profiles need manual shares
   - Could be extended in future

2. **Rapid Cycling**: No ramp rate or minimum duration constraints
   - Discussed in GitHub issue draft
   - Options proposed but not implemented

3. **Profile-Level Fallback**: Removed
   - If `technology_breakdown` not provided, no DSR stores created
   - This is intentional (explicit configuration required)

## ✅ Ready for Testing

All core features are implemented and ready for testing:

1. ✅ Technology-specific DSR with breakdown
2. ✅ Auto-calculation of shares
3. ✅ Negative-only DSR
4. ✅ Min_load constraint
5. ✅ H2-DRI-EAF coupling
6. ✅ Aluminium support
7. ✅ Error handling
8. ✅ Configuration examples
9. ✅ Documentation

## Test Command

```bash
cd /home/cecca/pypsa/pypsa-eurelectric
snakemake -j 1 results/Test_2030/networks/base_s_5___2030.nc \
  --configfile config/test/config.industry.flex.yaml
```

## Verification After Running

```bash
# Check DSR stores were created
PYTHONPATH=$PWD:$PYTHONPATH python check_industry_dsr.py

# Check logs for auto-calculation
grep -i "auto-calculated" results/Test_2030/logs/prepare_sector_network/base_s_5___2030.log

# Check H2-DRI coupling constraints
grep -i "DRI.*H2\|H2.*DRI\|coupling" results/Test_2030/logs/*/base_s_5___2030*.log
```
