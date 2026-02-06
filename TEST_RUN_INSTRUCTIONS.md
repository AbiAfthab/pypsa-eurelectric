# Test Run Instructions for Industry DSR

## Important Note

Your current config (`config/test/config.industry.flex.yaml`) has DSR enabled but **no `technology_breakdown`**. 

According to the current implementation, **DSR stores are only created if `technology_breakdown` is provided**. Without it, no DSR stores will be created (you'll see a log message: "No technology_breakdown provided. Industry DSR requires technology_breakdown to be defined.")

## Option 1: Test with Technology Breakdown (Recommended)

Add a minimal `technology_breakdown` to your config to test the full implementation:

```yaml
industry:
  dsr:
    enable: true
    technology_breakdown:
      "Iron & steel industry":
        "Scrap-EAF": "auto"
        "H2-DRI-EAF": "auto"
        "BF-BOF-CCUS": "auto"
        "Manufacturing": 0.05
    flexibility_fraction:
      "Iron & steel industry|Scrap-EAF": 0.85
      "Iron & steel industry|H2-DRI-EAF": 0.20
      "Iron & steel industry|BF-BOF-CCUS": 0.05
    shift_hours:
      "Iron & steel industry|Scrap-EAF": 2
      "Iron & steel industry|H2-DRI-EAF": 6
      "Iron & steel industry|BF-BOF-CCUS": 1
    restriction_time:
      "Iron & steel industry|Scrap-EAF": [6, 18]
      "Iron & steel industry|H2-DRI-EAF": [0, 12]
      "Iron & steel industry|BF-BOF-CCUS": [6, 18]
    restriction_value: 1.0
```

## Option 2: Test Basic Workflow (No DSR)

Run without DSR to test the basic workflow, then add DSR later.

## Snakemake Commands

### Build and Solve Network

```bash
# From project root
cd /home/cecca/pypsa/pypsa-eurelectric

# Build and solve (this will create the network with DSR if technology_breakdown is provided)
snakemake -j 1 results/Test_2030/networks/base_s_5___2030.nc \
  --configfile config/test/config.industry.flex.yaml
```

### Check if DSR Stores Were Created

After running, check the network:

```bash
# Using Python
python -c "
import pypsa
n = pypsa.Network('results/Test_2030/networks/base_s_5___2030.nc')
dsr_stores = n.stores[n.stores.carrier == 'industry dsr']
print(f'Industry DSR stores found: {len(dsr_stores)}')
if len(dsr_stores) > 0:
    print(f'Sample stores: {list(dsr_stores.index[:5])}')
    print(f'Store buses: {dsr_stores.bus.unique()[:5]}')
"
```

### Check Logs

Check the build log for DSR-related messages:

```bash
# Check prepare_sector_network log
tail -50 results/Test_2030/logs/prepare_sector_network/base_s_5___2030.log

# Check build_industry_dsr_profile log (if DSR enabled)
tail -50 results/Test_2030/logs/build_industry_dsr_profile/base_s_5___2030.log
```

### Expected Log Messages

**If technology_breakdown is provided:**
```
INFO:scripts.prepare_sector_network:Using technology-specific industry DSR
INFO:scripts.prepare_sector_network:DSR will only be applied to profiles with technology_breakdown: [...]
INFO:scripts.prepare_sector_network:Industry DSR Stores added.
```

**If technology_breakdown is NOT provided:**
```
INFO:scripts.prepare_sector_network:No technology_breakdown provided. Industry DSR requires technology_breakdown to be defined.
INFO:scripts.prepare_sector_network:No industry DSR stores will be created. Profiles will use baseline (fixed) load only.
```

## Quick Test Script

You can also use the diagnostic script:

```bash
PYTHONPATH=$PWD:$PYTHONPATH python check_industry_dsr.py
```

This will show:
- Number of industry loads
- Number of DSR stores
- Whether stores and loads are on the same buses
- Store dispatch statistics

## Troubleshooting

1. **No DSR stores created:**
   - Check if `technology_breakdown` is in config
   - Check logs for error messages
   - Verify `industry.dsr.enable: true`

2. **Stores on wrong buses:**
   - Should be on "low voltage" buses (same as loads)
   - Check `insert_electricity_distribution_grid` ran correctly

3. **Build errors:**
   - Check all dependencies are built
   - Verify config file syntax
   - Check Snakemake dry-run first: `snakemake --dry-run ...`
