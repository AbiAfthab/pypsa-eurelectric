#!/usr/bin/env python3
"""Quick diagnostic script to check industry DSR store connections and dispatch."""

import pypsa
import pandas as pd

# Load the network
network_path = "results/Test_2030/networks/base_s_5___2030.nc"
n = pypsa.Network(network_path)

print("=" * 60)
print("INDUSTRY DSR DIAGNOSTIC")
print("=" * 60)

# Check industry loads
industry_loads = n.loads.index[n.loads.carrier == "industry electricity"]
print(f"\n1. Industry electricity loads found: {len(industry_loads)}")
if len(industry_loads) > 0:
    print(f"   Sample loads: {list(industry_loads[:3])}")
    print(f"   Load buses: {n.loads.loc[industry_loads, 'bus'].unique()[:5]}")
    baseline = n.loads_t.p_set[industry_loads].sum(axis=1)
    print(f"   Baseline demand range: {baseline.min():.2f} - {baseline.max():.2f} MW")
    print(f"   Baseline demand mean: {baseline.mean():.2f} MW")

# Check industry DSR stores
industry_stores = n.stores.index[n.stores.carrier == "industry dsr"]
print(f"\n2. Industry DSR stores found: {len(industry_stores)}")
if len(industry_stores) > 0:
    print(f"   Sample stores: {list(industry_stores[:3])}")
    print(f"   Store buses: {n.stores.loc[industry_stores, 'bus'].unique()[:5]}")
    
    # Check if stores are on same buses as loads
    load_buses = set(n.loads.loc[industry_loads, 'bus'].unique())
    store_buses = set(n.stores.loc[industry_stores, 'bus'].unique())
    print(f"   Load buses: {len(load_buses)} unique buses")
    print(f"   Store buses: {len(store_buses)} unique buses")
    print(f"   Common buses: {len(load_buses & store_buses)}")
    if load_buses != store_buses:
        print(f"   WARNING: Store buses differ from load buses!")
        print(f"   Only in loads: {load_buses - store_buses}")
        print(f"   Only in stores: {store_buses - load_buses}")
    
    # Check store dispatch
    store_dispatch = n.stores_t.p[industry_stores].sum(axis=1)
    print(f"\n3. Store dispatch statistics:")
    print(f"   Dispatch range: {store_dispatch.min():.2f} - {store_dispatch.max():.2f} MW")
    print(f"   Dispatch mean: {store_dispatch.mean():.2f} MW")
    print(f"   Dispatch std: {store_dispatch.std():.2f} MW")
    print(f"   Non-zero dispatch hours: {(store_dispatch.abs() > 0.01).sum()} / {len(store_dispatch)}")
    
    # Calculate net demand
    baseline = n.loads_t.p_set[industry_loads].sum(axis=1)
    net = baseline + store_dispatch
    print(f"\n4. Net demand (baseline + store dispatch):")
    print(f"   Net range: {net.min():.2f} - {net.max():.2f} MW")
    print(f"   Net mean: {net.mean():.2f} MW")
    print(f"   Difference from baseline (max): {(net - baseline).abs().max():.2f} MW")
    print(f"   Difference from baseline (mean): {(net - baseline).abs().mean():.2f} MW")
    
    # Show first few hours
    print(f"\n5. First 10 hours comparison:")
    comparison = pd.DataFrame({
        'baseline': baseline.iloc[:10],
        'store_dispatch': store_dispatch.iloc[:10],
        'net': net.iloc[:10],
        'difference': (net - baseline).iloc[:10]
    })
    print(comparison.to_string())
    
else:
    print("   WARNING: No industry DSR stores found!")

print("\n" + "=" * 60)
