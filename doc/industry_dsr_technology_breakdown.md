# Industry DSR Technology-Specific Flexibility

## Overview

The industry DSR implementation now supports **technology-specific flexibility** within each FfE profile. This allows different industrial processes/technologies within the same sector to have different flexibility characteristics, matching the literature more accurately.

**Important**: The implementation is **generic** and works for **any FfE profile**. You can define technology breakdowns for:
- Iron & steel industry
- Non-metallic Minerals (cement)
- Paper, Pulp and Print
- Any other profile you want to split by technology

**Crucially**: If `technology_breakdown` is provided in the config, **only profiles with a technology breakdown defined will get DSR stores**. Profiles without a breakdown will be skipped (no DSR applied), even if they have profile-level flexibility parameters defined. If `technology_breakdown` is *not provided at all*, no DSR stores will be created.

## Configuration

### Technology Breakdown

Define how each FfE profile is split into technologies. You can either:

1. **Auto-calculate shares from production data** (recommended): Set shares to `"auto"` and the model will calculate them automatically from the production data.

2. **Manual shares**: Provide explicit share values (must sum to 1.0 per profile).

```yaml
industry:
  dsr:
    technology_breakdown:
      "Iron & steel industry":
        # Option 1: Auto-calculate (recommended)
        "Scrap-EAF": "auto"           # Auto from "Electric arc" production
        "H2-DRI-EAF": "auto"          # Auto from "DRI + Electric arc" production
        "BF-BOF-CCUS": "auto"         # Auto from "Integrated steelworks" production
        "Aluminium-primary": "auto"    # Auto from "Aluminium - primary production" production
        "Aluminium-secondary": "auto" # Auto from "Aluminium - secondary production" production
        "Alumina": "auto"             # Auto from "Alumina production" production
        "Manufacturing": 0.05         # Fixed share (not in production data)
        
        # Option 2: Manual shares (if you want to override)
        # "Scrap-EAF": 0.30
        # "H2-DRI-EAF": 0.50
        # "BF-BOF-CCUS": 0.15
        # "Manufacturing": 0.05
```

**Auto-calculation**: When shares are set to `"auto"`, the model calculates them from production data (`industrial_production_per_node`) by:
1. Summing production (kt/a) for each sector across all nodes
2. Calculating shares based on production volumes (assuming similar electricity intensity per ton)
3. Normalizing to sum to 1.0

**Important**: 
- Technology shares must sum to 1.0 per profile. The code will normalize if they don't.
- Auto-calculation works for technologies that map to PyPSA sectors in the production data (e.g., "Electric arc", "DRI + Electric arc", "Aluminium - primary production").
- Technologies not in production data (e.g., "Manufacturing") should use manual shares.

### Technology-Specific Flexibility

Use the format `"profile|technology"` for technology-specific parameters:

```yaml
industry:
  dsr:
    flexibility_fraction:
      "Iron & steel industry|Scrap-EAF": 0.85     # 85% flexible
      "Iron & steel industry|H2-DRI-EAF": 0.20    # 20% flexible
      "Iron & steel industry|BF-BOF-CCUS": 0.05   # 5% flexible
      "Iron & steel industry|Manufacturing": 0.0  # Not flexible
      "Iron & steel industry|Aluminium-primary": 0.125    # Conservative: 12.5% (10-15% range)
      "Iron & steel industry|Aluminium-secondary": 0.125 # Conservative: 12.5% (same as primary)
      "Iron & steel industry|Alumina": 0.0              # Not flexible (continuous process)
    
    shift_hours:
      "Iron & steel industry|Scrap-EAF": 2        # 2h shift window
      "Iron & steel industry|H2-DRI-EAF": 6        # 6h shift window
      "Iron & steel industry|BF-BOF-CCUS": 1       # 1h shift window
      "Iron & steel industry|Aluminium-primary": 3     # Conservative: 3h shift (2-4h range)
      "Iron & steel industry|Aluminium-secondary": 3  # Conservative: 3h shift (same as primary)
    
    restriction_time:
      "Iron & steel industry|Scrap-EAF": [6, 18]  # Checkpoints at 6:00 and 18:00
      "Iron & steel industry|H2-DRI-EAF": [0, 12]  # Checkpoints at midnight and noon
      "Iron & steel industry|Aluminium-primary": [0]    # Daily checkpoint at midnight (conservative)
      "Iron & steel industry|Aluminium-secondary": [0]   # Daily checkpoint at midnight (same as primary)
    
    negative_only: # New section for negative-only DSR
      "Non-specified (Industry)|Chlor-alkali": true # Chlor-alkali can only reduce load
    
    min_load: # New section for minimum load constraint (0.0-1.0)
      "Non-specified (Industry)|Chlor-alkali": 0.70 # Chlor-alkali: load cannot go below 70% of baseline
```

### Fallback Behavior

- If a technology doesn't have a specific `flexibility_fraction`, it defaults to `0.0` (not flexible)
- If a technology doesn't have a specific `shift_hours`, it falls back to the profile-level value (if available)
- If a technology doesn't have a specific `restriction_time`, it inherits from the profile-level value (if available)
- If a technology doesn't have a specific `min_load`, it defaults to `0.0` (no minimum load constraint)
- **Important**: If `technology_breakdown` is provided, **only profiles with a technology breakdown get DSR**. Profiles without a breakdown are skipped (no DSR stores created).
- If `technology_breakdown` is **not provided at all**, no DSR stores are created.

## How It Works

1. **Load Splitting**: Each `node|profile` load is split proportionally by technology shares
   - Example: `"BE0 0|Iron & steel industry"` = 100 MW
   - After splitting: `"BE0 0|Iron & steel industry|Scrap-EAF"` = 30 MW, etc.

2. **Store Creation**: One Store is created per `node|profile|technology` combination
   - Store name: `"{node} industry dsr {profile} {technology}"`
   - Each store has its own `flexibility_fraction`, `shift_hours`, `restriction_time`, `negative_only`, and `min_load`

3. **Negative-Only DSR**: For technologies marked `negative_only: true`:
   - `e_max_pu` is set to `0.0` for all hours (prevents charging).
   - `e_min_pu` is set to `-max_reduction` (where `max_reduction = min(flexibility_fraction, 1.0 - min_load)`) for non-checkpoint hours.
   - At checkpoint hours, `e_min_pu` is `0.0` (forcing the store to empty).

4. **H2-DRI-EAF DSR-H2 Storage Coupling**: A constraint is added in `scripts/solve_network.py` that limits the dispatch of H2-DRI-EAF DSR stores based on the available H2 storage capacity at the same node. This ensures that DRI load shifting is physically feasible given H2 storage constraints.

5. **No Double Counting**: Each MW of load appears in exactly one technology, ensuring no double counting of flexibility

## Example

See `config/examples/config.industry.dsr.technology.yaml` for a complete example configuration.

## Backward Compatibility

If `technology_breakdown` is not provided in the config, **no industry DSR stores will be created**. This ensures that DSR is only applied where technology-specific data is explicitly configured.

## Notes

- Technology-specific flexibility does **not** prevent rapid charge/discharge cycling. To address that, additional constraints (ramp limits, minimum duration) would need to be added separately.
- The technology breakdown is **config-based**, not data-based. If you need actual technology-specific load data, that would require extending the data pipeline.
- Auto-calculation of shares uses production data as a proxy for electricity demand. For more accuracy, you can manually calculate shares from actual electricity demand data.
