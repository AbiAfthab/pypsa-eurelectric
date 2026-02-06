#!/usr/bin/env python3
"""Verify that DSR stores balance energy within each period between checkpoints."""

import pandas as pd
import pypsa
import numpy as np
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

network_path = "results/Test_2030/networks/base_s_5___2030.nc"
profile_path = "resources/Test_2030/industrial_dsr_profile_base_s_5_2030.csv"

print("=" * 80)
print("DSR ENERGY BALANCE PER PERIOD VERIFICATION")
print("=" * 80)

# Load network
n = pypsa.Network(network_path)
print(f"\n✓ Network loaded: {network_path}")
print(f"   Snapshots: {len(n.snapshots)}")

# Load DSR profile
dsr_profile = pd.read_csv(profile_path, index_col=0, parse_dates=True)
dsr_profile = dsr_profile.reindex(n.snapshots).ffill().bfill()

# Get industry DSR stores
industry_dsr_stores = n.stores.index[n.stores.carrier == "industry dsr"]
print(f"\n✓ Found {len(industry_dsr_stores)} industry DSR stores")

# Group stores by profile
stores_by_profile = {}
for store in industry_dsr_stores:
    parts = store.split(" industry dsr ")
    if len(parts) == 2:
        profile = parts[1]
        if profile not in stores_by_profile:
            stores_by_profile[profile] = []
        stores_by_profile[profile].append(store)

# Get store dispatch
store_dispatch = n.stores_t.p[industry_dsr_stores]

print("\n" + "=" * 80)
print("ENERGY BALANCE BETWEEN CHECKPOINTS")
print("=" * 80)

for profile, stores in stores_by_profile.items():
    if profile not in dsr_profile.columns:
        continue
    
    print(f"\n{profile}:")
    
    # Get checkpoint hours for this profile
    profile_vals = dsr_profile[profile]
    checkpoint_mask = profile_vals == 0.0
    checkpoint_hours = profile_vals[checkpoint_mask].index.tolist()
    
    if len(checkpoint_hours) == 0:
        print("   No checkpoint hours defined")
        continue
    
    print(f"   Checkpoint hours: {len(checkpoint_hours)}")
    
    # Get dispatch for stores of this profile
    profile_stores = [s for s in stores if s in store_dispatch.columns]
    if len(profile_stores) == 0:
        continue
    
    profile_dispatch = store_dispatch[profile_stores].sum(axis=1)
    
    # Check energy balance between consecutive checkpoints
    checkpoint_indices = [n.snapshots.get_loc(h) for h in checkpoint_hours if h in n.snapshots]
    checkpoint_indices = sorted(set(checkpoint_indices))
    
    if len(checkpoint_indices) < 2:
        print("   Only one checkpoint in horizon - cannot verify period balance")
        continue
    
    print(f"   Checking {len(checkpoint_indices)-1} periods between checkpoints:")
    
    all_balanced = True
    for i in range(len(checkpoint_indices) - 1):
        start_idx = checkpoint_indices[i]
        end_idx = checkpoint_indices[i + 1]
        
        # Sum dispatch over this period (inclusive of start, exclusive of end)
        period_dispatch = profile_dispatch.iloc[start_idx:end_idx].sum()
        
        # Convert to MWh (assuming hourly snapshots)
        period_energy = period_dispatch  # Already in MWh if p is in MW and snapshots are hourly
        
        start_time = n.snapshots[start_idx]
        end_time = n.snapshots[end_idx]
        period_length = end_idx - start_idx
        
        status = "✓" if abs(period_energy) < 0.1 else "✗"
        if abs(period_energy) >= 0.1:
            all_balanced = False
        
        print(f"     Period {i+1}: {start_time} to {end_time} ({period_length}h)")
        print(f"       Net dispatch: {period_energy:.4f} MWh {status}")
    
    if all_balanced:
        print(f"   ✓ All periods are energy-balanced!")
    else:
        print(f"   ✗ Some periods are NOT energy-balanced")

# Overall summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

total_dispatch = store_dispatch.sum().sum()
print(f"\nTotal dispatch over entire horizon: {total_dispatch:.4f} MWh")
print("(Should be ~0 for e_cyclic=True, but may differ if horizon doesn't end at checkpoint)")

print("\n" + "=" * 80)
