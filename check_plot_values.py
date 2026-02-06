#!/usr/bin/env python3
"""Check the actual values being plotted to see why there's no visible difference."""

import pypsa
import pandas as pd
import matplotlib.pyplot as plt

# Load the network
network_path = "results/Test_2030/networks/base_s_5___2030.nc"
n = pypsa.Network(network_path)

# Get industry loads
industry_loads = n.loads.index[n.loads.carrier == "industry electricity"]
baseline = n.loads_t.p_set[industry_loads].sum(axis=1)

# Get industry DSR stores
industry_stores = n.stores.index[n.stores.carrier == "industry dsr"]
store_dispatch = n.stores_t.p[industry_stores].sum(axis=1)

# Calculate net
net = baseline + store_dispatch

# Check first 24 hours in detail
print("=" * 80)
print("DETAILED COMPARISON - First 24 hours")
print("=" * 80)
comparison = pd.DataFrame({
    'baseline_MW': baseline.iloc[:24],
    'store_dispatch_MW': store_dispatch.iloc[:24],
    'net_MW': net.iloc[:24],
    'difference_MW': (net - baseline).iloc[:24],
    'difference_%': ((net - baseline) / baseline * 100).iloc[:24]
})
print(comparison.to_string())

print("\n" + "=" * 80)
print("STATISTICS")
print("=" * 80)
print(f"Baseline range: {baseline.min():.2f} - {baseline.max():.2f} MW")
print(f"Net range: {net.min():.2f} - {net.max():.2f} MW")
print(f"Max absolute difference: {(net - baseline).abs().max():.2f} MW")
print(f"Mean absolute difference: {(net - baseline).abs().mean():.2f} MW")
print(f"Max relative difference: {((net - baseline) / baseline * 100).abs().max():.2f}%")
print(f"Mean relative difference: {((net - baseline) / baseline * 100).abs().mean():.2f}%")

# Check if stores are actually on same buses as loads
print("\n" + "=" * 80)
print("BUS VERIFICATION")
print("=" * 80)
load_buses = set(n.loads.loc[industry_loads, 'bus'].unique())
store_buses = set(n.stores.loc[industry_stores, 'bus'].unique())
print(f"Load buses: {sorted(load_buses)}")
print(f"Store buses: {sorted(store_buses)}")
print(f"Match: {load_buses == store_buses}")

# Check actual load values after solve
print("\n" + "=" * 80)
print("LOAD VALUES AFTER SOLVE")
print("=" * 80)
actual_loads = n.loads_t.p[industry_loads].sum(axis=1)
print(f"Actual loads (after solve) range: {actual_loads.min():.2f} - {actual_loads.max():.2f} MW")
print(f"Baseline (p_set) range: {baseline.min():.2f} - {baseline.max():.2f} MW")
print(f"Difference (actual - baseline): {(actual_loads - baseline).abs().max():.2f} MW")
print(f"Store dispatch range: {store_dispatch.min():.2f} - {store_dispatch.max():.2f} MW")
print(f"\nDoes actual_loads ≈ baseline + store_dispatch?")
print(f"Max difference: {(actual_loads - net).abs().max():.2f} MW")
