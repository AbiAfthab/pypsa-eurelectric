#!/usr/bin/env python3
"""Check if industry DSR stores are energy-neutral and working correctly."""

import pypsa
import pandas as pd
import numpy as np

# Load the network
network_path = "results/Test_2030/networks/base_s_5___2030.nc"
n = pypsa.Network(network_path)

print("=" * 80)
print("INDUSTRY DSR ENERGY BALANCE CHECK")
print("=" * 80)

# Get industry loads
industry_loads = n.loads.index[n.loads.carrier == "industry electricity"]
baseline = n.loads_t.p_set[industry_loads].sum(axis=1)

# Get industry DSR stores
industry_stores = n.stores.index[n.stores.carrier == "industry dsr"]
print(f"\n1. Industry DSR stores: {len(industry_stores)}")

if len(industry_stores) > 0:
    # Check store properties
    print(f"\n2. Store properties:")
    print(f"   e_cyclic: {n.stores.loc[industry_stores, 'e_cyclic'].unique()}")
    print(f"   e_initial: {n.stores.loc[industry_stores, 'e_initial'].unique()}")
    print(f"   standing_loss: {n.stores.loc[industry_stores, 'standing_loss'].unique()}")
    
    # Check store state (energy)
    if hasattr(n.stores_t, 'e'):
        store_energy = n.stores_t.e[industry_stores]
        print(f"\n3. Store energy (state):")
        print(f"   Initial state (first hour): {store_energy.iloc[0].sum():.2f} MWh")
        print(f"   Final state (last hour): {store_energy.iloc[-1].sum():.2f} MWh")
        print(f"   Difference: {store_energy.iloc[-1].sum() - store_energy.iloc[0].sum():.2f} MWh")
        print(f"   Max state: {store_energy.max().max():.2f} MWh")
        print(f"   Min state: {store_energy.min().min():.2f} MWh")
        
        # Check if stores are empty at checkpoint hours (if restriction_time is set)
        # This would require checking the DSR profile, but let's check if states are near zero at certain hours
        print(f"\n4. Store state at specific hours:")
        print(f"   Hour 0 (midnight): {store_energy.iloc[0].sum():.2f} MWh")
        print(f"   Hour 6: {store_energy.iloc[6].sum():.2f} MWh")
        print(f"   Hour 12: {store_energy.iloc[12].sum():.2f} MWh")
        print(f"   Hour 18: {store_energy.iloc[18].sum():.2f} MWh")
    
    # Check store dispatch (power)
    store_dispatch = n.stores_t.p[industry_stores].sum(axis=1)
    print(f"\n5. Store dispatch (power):")
    print(f"   Total dispatch (sum over all hours): {store_dispatch.sum():.2f} MWh")
    print(f"   Should be ~0 for energy-neutral (with e_cyclic=True)")
    print(f"   Positive dispatch (charging) hours: {(store_dispatch > 0.01).sum()}")
    print(f"   Negative dispatch (discharging) hours: {(store_dispatch < -0.01).sum()}")
    print(f"   Near-zero dispatch hours: {(store_dispatch.abs() < 0.01).sum()}")
    
    # Calculate cumulative dispatch
    cumulative_dispatch = store_dispatch.cumsum()
    print(f"\n6. Cumulative dispatch:")
    print(f"   Final cumulative: {cumulative_dispatch.iloc[-1]:.2f} MWh")
    print(f"   Max cumulative: {cumulative_dispatch.max():.2f} MWh")
    print(f"   Min cumulative: {cumulative_dispatch.min():.2f} MWh")
    
    # Check net demand
    net = baseline + store_dispatch
    print(f"\n7. Load comparison:")
    print(f"   Baseline total: {baseline.sum():.2f} MWh")
    print(f"   Net total: {net.sum():.2f} MWh")
    print(f"   Difference: {(net.sum() - baseline.sum()):.2f} MWh")
    print(f"   Should be ~0 for energy-neutral shifting")
    
    print(f"\n8. Hourly averages:")
    print(f"   Baseline mean: {baseline.mean():.2f} MW")
    print(f"   Net mean: {net.mean():.2f} MW")
    print(f"   Store dispatch mean: {store_dispatch.mean():.2f} MW")
    
    print(f"\n9. First 24 hours detail:")
    comparison = pd.DataFrame({
        'baseline_MW': baseline.iloc[:24],
        'store_dispatch_MW': store_dispatch.iloc[:24],
        'net_MW': net.iloc[:24],
        'cumulative_MWh': cumulative_dispatch.iloc[:24]
    })
    print(comparison.to_string())
    
    # Check if stores are mostly charging
    charging_hours = (store_dispatch > 0.01).sum()
    discharging_hours = (store_dispatch < -0.01).sum()
    total_charging = store_dispatch[store_dispatch > 0].sum()
    total_discharging = abs(store_dispatch[store_dispatch < 0].sum())
    
    print(f"\n10. Charging vs Discharging:")
    print(f"    Charging hours: {charging_hours} ({charging_hours/len(store_dispatch)*100:.1f}%)")
    print(f"    Discharging hours: {discharging_hours} ({discharging_hours/len(store_dispatch)*100:.1f}%)")
    print(f"    Total charging: {total_charging:.2f} MWh")
    print(f"    Total discharging: {total_discharging:.2f} MWh")
    print(f"    Balance: {total_charging - total_discharging:.2f} MWh (should be ~0)")

print("\n" + "=" * 80)
