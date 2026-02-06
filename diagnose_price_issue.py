#!/usr/bin/env python3
"""Diagnose whether price issue is plotting/retrieval or optimization problem."""

import pypsa
import pandas as pd
import numpy as np

network_path = "results/Test_2030/networks/base_s_5___2030.nc"
n = pypsa.Network(network_path)

print("=" * 80)
print("DIAGNOSING PRICE ISSUE: Plotting vs Optimization")
print("=" * 80)

# 1. Check how prices are stored in the network
print("\n1. CHECKING HOW PRICES ARE STORED")
print("-" * 80)
if hasattr(n.buses_t, 'marginal_price'):
    print("✓ marginal_price exists in buses_t")
    print(f"  Type: {type(n.buses_t.marginal_price)}")
    print(f"  Shape: {n.buses_t.marginal_price.shape}")
    print(f"  Dtype: {n.buses_t.marginal_price.dtypes.iloc[0]}")
    
    # Sample values
    sample_bus = n.buses_t.marginal_price.columns[0]
    sample_prices = n.buses_t.marginal_price[sample_bus].iloc[:5]
    print(f"\n  Sample prices (first bus '{sample_bus}', first 5 hours):")
    print(f"  {sample_prices.values}")
else:
    print("✗ No marginal_price found")

# 2. Check how other scripts retrieve prices
print("\n2. CHECKING HOW OTHER SCRIPTS RETRIEVE PRICES")
print("-" * 80)
print("Looking at make_summary.py and plot_balance_map.py patterns...")

# Pattern from make_summary.py (line 229)
ac_buses = n.buses.index[n.buses.carrier == "AC"]
if len(ac_buses) > 0:
    prices_direct = n.buses_t.marginal_price[ac_buses]
    print(f"\n  Direct access (make_summary.py pattern):")
    print(f"    Range: {prices_direct.min().min():.2f} - {prices_direct.max().max():.2f}")
    print(f"    Mean: {prices_direct.mean().mean():.2f}")

# Pattern from plot_balance_map.py (line 137) - uses weightings
if hasattr(n, 'snapshot_weightings') and len(ac_buses) > 0:
    try:
        weights = n.snapshot_weightings.generators
        prices_weighted = weights @ n.buses_t.marginal_price[ac_buses] / weights.sum()
        print(f"\n  Weighted access (plot_balance_map.py pattern):")
        if isinstance(prices_weighted, pd.Series):
            print(f"    Range: {prices_weighted.min():.2f} - {prices_weighted.max():.2f}")
            print(f"    Mean: {prices_weighted.mean():.2f}")
        elif isinstance(prices_weighted, pd.DataFrame):
            print(f"    Range: {prices_weighted.min().min():.2f} - {prices_weighted.max().max():.2f}")
            print(f"    Mean: {prices_weighted.mean().mean():.2f}")
        else:
            # Scalar result
            print(f"    Value: {prices_weighted:.2f}")
    except Exception as e:
        print(f"\n  Weighted access failed: {e}")

# 3. Check optimization status and objective
print("\n3. CHECKING OPTIMIZATION STATUS")
print("-" * 80)
if hasattr(n, 'objective'):
    print(f"✓ Network has objective: {n.objective:.2e}")
    print(f"  (This suggests optimization completed)")
else:
    print("✗ No objective found - network may not be solved")

if hasattr(n, 'status'):
    print(f"  Status: {n.status}")
else:
    print("  Status: Not available")

# 4. Check generator costs (to see if they're reasonable)
print("\n4. CHECKING GENERATOR COSTS")
print("-" * 80)
if len(n.generators) > 0:
    print(f"  Total generators: {len(n.generators)}")
    
    # Check marginal costs
    if 'marginal_cost' in n.generators.columns:
        mc = n.generators.marginal_cost
        print(f"\n  Generator marginal costs:")
        print(f"    Range: {mc.min():.2f} - {mc.max():.2f} €/MWh")
        print(f"    Mean: {mc.mean():.2f} €/MWh")
        print(f"    Median: {mc.median():.2f} €/MWh")
        
        # Check if any are unreasonably high
        high_mc = mc[mc > 1000]
        if len(high_mc) > 0:
            print(f"\n  ⚠️  WARNING: {len(high_mc)} generators have marginal_cost > 1000 €/MWh")
            print(f"    These might be causing unrealistic prices:")
            print(f"    {high_mc.head(10).to_dict()}")
        else:
            print(f"  ✓ All generator marginal costs seem reasonable")
    
    # Check if there are time-varying marginal costs
    if hasattr(n.generators_t, 'marginal_cost'):
        tv_mc = n.generators_t.marginal_cost
        if not tv_mc.empty:
            print(f"\n  Time-varying marginal costs found:")
            print(f"    Shape: {tv_mc.shape}")
            print(f"    Range: {tv_mc.min().min():.2f} - {tv_mc.max().max():.2f} €/MWh")
            high_tv_mc = (tv_mc > 1000).sum().sum()
            if high_tv_mc > 0:
                print(f"    ⚠️  WARNING: {high_tv_mc} values > 1000 €/MWh")

# 5. Check snapshot weightings
print("\n5. CHECKING SNAPSHOT WEIGHTINGS")
print("-" * 80)
if hasattr(n, 'snapshot_weightings'):
    weights = n.snapshot_weightings
    print(f"  Shape: {weights.shape}")
    print(f"  Columns: {list(weights.columns)}")
    print(f"  Range: {weights.min().min():.2f} - {weights.max().max():.2f}")
    print(f"  Mean: {weights.mean().mean():.2f}")
    print(f"\n  First few values:")
    print(f"  {weights.head()}")
    
    # Check if weightings are constant
    if weights.nunique().sum() == len(weights.columns):
        print(f"  ✓ Weightings are constant (as expected for temporal aggregation)")
    else:
        print(f"  ⚠️  Weightings vary (unusual)")

# 6. Check if there are binding constraints that might affect prices
print("\n6. CHECKING GLOBAL CONSTRAINTS")
print("-" * 80)
if len(n.global_constraints) > 0:
    print(f"  Found {len(n.global_constraints)} global constraints:")
    for gc in n.global_constraints.index:
        print(f"    - {gc}")
        if 'mu' in n.global_constraints.columns:
            mu = n.global_constraints.loc[gc, 'mu']
            if pd.notna(mu):
                print(f"      Shadow price (mu): {mu:.2e}")
                if abs(mu) > 1000:
                    print(f"      ⚠️  Very high shadow price - might affect bus prices")
else:
    print("  No global constraints found")

# 7. Compare prices with generator costs
print("\n7. COMPARING PRICES WITH GENERATOR COSTS")
print("-" * 80)
if len(ac_buses) > 0 and len(n.generators) > 0:
    prices_mean = n.buses_t.marginal_price[ac_buses].mean(axis=1).mean()
    
    if 'marginal_cost' in n.generators.columns:
        mc_mean = n.generators.marginal_cost.mean()
        
        print(f"  Average bus price: {prices_mean:.2f} €/MWh")
        print(f"  Average generator marginal cost: {mc_mean:.2f} €/MWh")
        print(f"  Ratio: {prices_mean / mc_mean:.2f}x")
        
        if prices_mean / mc_mean > 100:
            print(f"  ⚠️  Prices are {prices_mean / mc_mean:.0f}x higher than generator costs!")
            print(f"      This strongly suggests an optimization or unit issue")

# 8. Check temporal aggregation settings
print("\n8. CHECKING TEMPORAL AGGREGATION")
print("-" * 80)
print(f"  Number of snapshots: {len(n.snapshots)}")
print(f"  Time span: {n.snapshots[0]} to {n.snapshots[-1]}")
print(f"  Duration: {(n.snapshots[-1] - n.snapshots[0]).total_seconds() / 3600:.1f} hours")
print(f"  Expected snapshots for 1 week: 168")
if len(n.snapshots) < 168:
    print(f"  ⚠️  Fewer snapshots than expected - temporal aggregation is active")
    if hasattr(n, 'snapshot_weightings'):
        total_hours = n.snapshot_weightings.generators.sum()
        print(f"  Total weighted hours: {total_hours:.1f}")
        print(f"  Hours per snapshot: {total_hours / len(n.snapshots):.1f}")

# 9. SUMMARY AND RECOMMENDATIONS
print("\n" + "=" * 80)
print("SUMMARY AND DIAGNOSIS")
print("=" * 80)

if hasattr(n.buses_t, 'marginal_price'):
    prices_max = n.buses_t.marginal_price.max().max()
    
    if prices_max > 10000:
        print("\n🔴 CRITICAL: Prices are definitely wrong (>10,000 €/MWh)")
        print("\n   This is likely an OPTIMIZATION ISSUE, not a plotting issue:")
        print("   1. Prices are stored incorrectly in the network file")
        print("   2. Optimization may have binding constraints causing unrealistic prices")
        print("   3. Generator costs or other parameters may be wrong")
        print("\n   RECOMMENDATIONS:")
        print("   - Check optimization logs for warnings/errors")
        print("   - Verify generator marginal costs are reasonable")
        print("   - Check if global constraints are binding")
        print("   - Try solving without temporal aggregation")
        print("   - Compare with a known-good network")
    elif prices_max > 1000:
        print("\n🟡 WARNING: Prices are high (>1,000 €/MWh) but might be correct")
        print("   Could be:")
        print("   1. Optimization issue (most likely)")
        print("   2. Unit conversion issue")
        print("   3. Temporal aggregation scaling")
        print("\n   Check generator costs and optimization status above")
    else:
        print("\n🟢 Prices seem reasonable (<1,000 €/MWh)")
        print("   If you're seeing high prices in plots, check the plotting code")

print("\n" + "=" * 80)
