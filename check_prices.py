#!/usr/bin/env python3
"""Check electricity prices in the network."""

import pypsa
import pandas as pd
import numpy as np

network_path = "results/Test_2030/networks/base_s_5___2030.nc"
n = pypsa.Network(network_path)

print("=" * 80)
print("CHECKING ELECTRICITY PRICES")
print("=" * 80)

# Check if marginal prices exist
if hasattr(n.buses_t, 'marginal_price'):
    print("\n✓ marginal_price exists in buses_t")
    
    # Get AC buses
    ac_buses = n.buses.index[n.buses.carrier == "AC"]
    print(f"\nAC buses: {len(ac_buses)}")
    if len(ac_buses) > 0:
        ac_prices = n.buses_t.marginal_price[ac_buses]
        print(f"AC prices shape: {ac_prices.shape}")
        print(f"AC prices range: {ac_prices.min().min():.2f} - {ac_prices.max().max():.2f}")
        print(f"AC prices mean: {ac_prices.mean().mean():.2f}")
        print(f"AC prices median: {ac_prices.median().median():.2f}")
        print(f"\nFirst 10 AC prices (first bus):")
        print(ac_prices.iloc[:10, 0])
        
        # Check if prices seem reasonable (should be ~30-100 €/MWh)
        if ac_prices.min().min() > 1000:
            print(f"\n⚠️  WARNING: Prices seem too high! Expected ~30-100 €/MWh")
            print(f"   Maybe prices are in wrong units? (€/MW instead of €/MWh?)")
            print(f"   Or maybe there's a scaling factor?")
    
    # Get low voltage buses
    lv_buses = n.buses.index[n.buses.carrier == "low voltage"]
    print(f"\nLow voltage buses: {len(lv_buses)}")
    if len(lv_buses) > 0:
        lv_prices = n.buses_t.marginal_price[lv_buses]
        print(f"LV prices shape: {lv_prices.shape}")
        print(f"LV prices range: {lv_prices.min().min():.2f} - {lv_prices.max().max():.2f}")
        print(f"LV prices mean: {lv_prices.mean().mean():.2f}")
        print(f"LV prices median: {lv_prices.median().median():.2f}")
        print(f"\nFirst 10 LV prices (first bus):")
        print(lv_prices.iloc[:10, 0])
        
        # Check stores
        industry_stores = n.stores.index[n.stores.carrier == "industry dsr"]
        if len(industry_stores) > 0:
            store_buses = n.stores.loc[industry_stores[:3], "bus"].unique()
            print(f"\nSample store buses: {store_buses}")
            if len(store_buses) > 0:
                store_prices = n.buses_t.marginal_price[store_buses]
                print(f"Store bus prices range: {store_prices.min().min():.2f} - {store_prices.max().max():.2f}")
                print(f"Store bus prices mean: {store_prices.mean().mean():.2f}")
                print(f"Store bus prices median: {store_prices.median().median():.2f}")
                
                # Check if there's a relationship with snapshot weightings
                if hasattr(n, 'snapshot_weightings'):
                    print(f"\nSnapshot weightings (first 10):")
                    print(n.snapshot_weightings.iloc[:10])
                    print(f"Maybe prices need to be divided by snapshot_weightings?")
else:
    print("\n✗ No marginal_price found in buses_t")
    print("  Available buses_t attributes:", [attr for attr in dir(n.buses_t) if not attr.startswith('_')])

# Check if network was solved
if hasattr(n, 'objective'):
    print(f"\n✓ Network has objective: {n.objective}")
else:
    print("\n✗ Network may not have been solved")

# Check snapshot weightings
if hasattr(n, 'snapshot_weightings'):
    print(f"\nSnapshot weightings info:")
    print(f"  Shape: {n.snapshot_weightings.shape}")
    print(f"  Range: {n.snapshot_weightings.min().min():.2f} - {n.snapshot_weightings.max().max():.2f}")
    print(f"  Mean: {n.snapshot_weightings.mean().mean():.2f}")

print("\n" + "=" * 80)
