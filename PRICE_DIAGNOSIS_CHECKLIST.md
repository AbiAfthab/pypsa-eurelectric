# Price Issue Diagnosis Checklist

## Problem
Prices are showing as 52,000-59,000 €/MWh instead of expected ~30-100 €/MWh.

## Steps to Diagnose

### 1. Run the diagnostic script
```bash
python diagnose_price_issue.py
```

### 2. Check optimization logs
Look for warnings/errors in:
- `results/Test_2030/logs/solve_sector_network/base_s_5___2030.log`
- Check if optimization completed successfully (status = "ok")

### 3. Compare with other networks
Check if other solved networks have realistic prices:
```bash
# If you have other solved networks, check their prices
python -c "import pypsa; n = pypsa.Network('path/to/other/network.nc'); print(n.buses_t.marginal_price.mean().mean())"
```

### 4. Check generator costs
Verify generator marginal costs are reasonable:
- Should be ~30-100 €/MWh for typical generators
- Check `config/test/config.industry.flex.yaml` for cost parameters

### 5. Test without temporal aggregation
Temporarily disable temporal aggregation to see if prices are correct:
- Set `clustering.temporal.resolution_sector: false` in config
- Rebuild and solve network
- Check if prices are realistic

### 6. Check if it's a plotting issue
Compare how different scripts retrieve prices:
- `scripts/make_summary.py` (line 229): Direct access
- `scripts/plot_balance_map.py` (line 137): Uses weightings
- Our plotting scripts: Direct access

## Expected Outcomes

### If it's a PLOTTING ISSUE:
- Other scripts show realistic prices
- Generator costs are reasonable
- Optimization completed successfully
- **Solution**: Fix price retrieval in plotting scripts

### If it's an OPTIMIZATION ISSUE:
- All scripts show unrealistic prices
- Generator costs might be wrong
- Optimization might have failed or warnings
- Binding constraints causing issues
- **Solution**: Fix optimization setup, costs, or constraints

## Quick Test

Run this to compare price retrieval methods:
```python
import pypsa
n = pypsa.Network("results/Test_2030/networks/base_s_5___2030.nc")

# Method 1: Direct (what we're using)
prices1 = n.buses_t.marginal_price[n.buses.carrier == "AC"].mean(axis=1).mean()
print(f"Direct access: {prices1:.2f} €/MWh")

# Method 2: Weighted (plot_balance_map.py)
weights = n.snapshot_weightings.generators
buses = n.buses.index[n.buses.carrier == "AC"]
prices2 = (weights @ n.buses_t.marginal_price[buses] / weights.sum()).mean()
print(f"Weighted access: {prices2:.2f} €/MWh")

# Method 3: Check generator costs
if len(n.generators) > 0:
    mc = n.generators.marginal_cost.mean()
    print(f"Generator marginal cost: {mc:.2f} €/MWh")
    print(f"Price/Cost ratio: {prices1/mc:.2f}x")
```
