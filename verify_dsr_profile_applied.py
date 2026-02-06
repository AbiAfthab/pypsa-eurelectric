#!/usr/bin/env python3
"""Verify that the DSR profile is being applied correctly to stores."""

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
print("DSR PROFILE APPLICATION VERIFICATION")
print("=" * 80)

# Load network
if not os.path.exists(network_path):
    print(f"\n✗ Network file not found: {network_path}")
    print("   Please rebuild the network first.")
    sys.exit(1)

n = pypsa.Network(network_path)
print(f"\n✓ Network loaded: {network_path}")
print(f"   Snapshots: {len(n.snapshots)} ({n.snapshots[0]} to {n.snapshots[-1]})")

# Load DSR profile file
if not os.path.exists(profile_path):
    print(f"\n✗ DSR profile file not found: {profile_path}")
    sys.exit(1)

dsr_profile = pd.read_csv(profile_path, index_col=0, parse_dates=True)
print(f"\n✓ DSR profile file loaded: {profile_path}")
print(f"   Profile shape: {dsr_profile.shape}")
print(f"   Profile columns: {list(dsr_profile.columns)}")

# Get industry DSR stores
industry_dsr_stores = n.stores.index[n.stores.carrier == "industry dsr"]
if len(industry_dsr_stores) == 0:
    print("\n✗ No industry DSR stores found in network!")
    sys.exit(1)

print(f"\n✓ Found {len(industry_dsr_stores)} industry DSR stores")

# Group stores by profile
stores_by_profile = {}
for store in industry_dsr_stores:
    # Store name format: "BE0 0 industry dsr Iron & steel industry"
    parts = store.split(" industry dsr ")
    if len(parts) == 2:
        profile = parts[1]
        if profile not in stores_by_profile:
            stores_by_profile[profile] = []
        stores_by_profile[profile].append(store)

print(f"\n   Stores grouped by {len(stores_by_profile)} profiles:")
for profile, stores in stores_by_profile.items():
    print(f"     {profile}: {len(stores)} stores")

# Check constraints for each profile
print("\n" + "=" * 80)
print("CONSTRAINT VERIFICATION")
print("=" * 80)

all_time_varying = True
all_checkpoints_correct = True

for profile, stores in stores_by_profile.items():
    if profile not in dsr_profile.columns:
        print(f"\n⚠️  Profile '{profile}' not found in DSR profile file!")
        continue
    
    # Get expected profile values (reindexed to network snapshots)
    expected_profile = dsr_profile[profile].reindex(n.snapshots).ffill().bfill()
    
    # Get a sample store for this profile
    sample_store = stores[0]
    
    # Get actual constraints
    e_max_pu = n.stores_t.e_max_pu[sample_store]
    e_min_pu = n.stores_t.e_min_pu[sample_store]
    
    # Get flexibility_fraction and restriction_value from config
    # We'll infer from the actual values
    max_val = e_max_pu.max()
    min_val = e_min_pu.min()
    
    # Expected values should be: profile_value * flexibility_fraction * restriction_value
    # At checkpoint hours (profile=0): should be 0
    # At other hours (profile=1): should be flexibility_fraction * restriction_value
    
    # Check if constraints are time-varying
    is_time_varying = (e_max_pu.nunique() > 1) or (e_min_pu.nunique() > 1)
    
    if not is_time_varying:
        print(f"\n✗ Profile '{profile}' has CONSTANT constraints (not time-varying)!")
        print(f"   e_max_pu: constant at {e_max_pu.iloc[0]:.4f}")
        print(f"   e_min_pu: constant at {e_min_pu.iloc[0]:.4f}")
        all_time_varying = False
    else:
        print(f"\n✓ Profile '{profile}' has TIME-VARYING constraints")
        print(f"   e_max_pu range: [{e_max_pu.min():.4f}, {e_max_pu.max():.4f}]")
        print(f"   e_min_pu range: [{e_min_pu.min():.4f}, {e_min_pu.max():.4f}]")
        
        # Check checkpoint hours
        checkpoint_hours_in_profile = expected_profile[expected_profile == 0.0].index
        if len(checkpoint_hours_in_profile) > 0:
            print(f"   Expected checkpoint hours: {len(checkpoint_hours_in_profile)}")
            
            # Check if constraints are 0 at checkpoint hours
            checkpoint_constraints_max = e_max_pu.loc[checkpoint_hours_in_profile]
            checkpoint_constraints_min = e_min_pu.loc[checkpoint_hours_in_profile]
            
            max_at_checkpoints = checkpoint_constraints_max.max()
            min_at_checkpoints = checkpoint_constraints_min.min()
            
            # Allow small numerical tolerance
            tolerance = 1e-6
            if abs(max_at_checkpoints) > tolerance or abs(min_at_checkpoints) > tolerance:
                print(f"   ✗ Constraints NOT zero at checkpoint hours!")
                print(f"     Max at checkpoints: {max_at_checkpoints:.6f} (should be ~0)")
                print(f"     Min at checkpoints: {min_at_checkpoints:.6f} (should be ~0)")
                all_checkpoints_correct = False
            else:
                print(f"   ✓ Constraints are zero at checkpoint hours")
                print(f"     Max at checkpoints: {max_at_checkpoints:.6f}")
                print(f"     Min at checkpoints: {min_at_checkpoints:.6f}")
        
        # Show sample values at key hours
        print(f"\n   Sample constraints at key hours:")
        key_hours = [0, 6, 12, 18]
        for h in key_hours:
            if h < len(n.snapshots):
                snapshot = n.snapshots[h]
                expected_val = expected_profile.loc[snapshot]
                actual_max = e_max_pu.loc[snapshot]
                actual_min = e_min_pu.loc[snapshot]
                hour_of_day = snapshot.hour
                is_checkpoint = expected_val == 0.0
                marker = " [CHECKPOINT]" if is_checkpoint else ""
                print(f"     Hour {h:2d} ({hour_of_day:2d}:00): "
                      f"profile={expected_val:.1f}, "
                      f"e_max_pu={actual_max:.4f}, "
                      f"e_min_pu={actual_min:.4f}{marker}")

# Check e_cyclic and e_initial
print("\n" + "=" * 80)
print("CYCLIC CONSTRAINT VERIFICATION")
print("=" * 80)

e_cyclic_vals = n.stores.loc[industry_dsr_stores, "e_cyclic"].unique()
e_initial_vals = n.stores.loc[industry_dsr_stores, "e_initial"].unique()

print(f"\nStore properties:")
print(f"   e_cyclic: {e_cyclic_vals}")
print(f"   e_initial: {e_initial_vals}")

if len(e_cyclic_vals) == 1 and e_cyclic_vals[0] == True:
    print("   ✓ e_cyclic is True for all stores")
else:
    print("   ✗ e_cyclic is NOT True for all stores!")

if len(e_initial_vals) == 1 and abs(e_initial_vals[0]) < 1e-6:
    print("   ✓ e_initial is 0.0 for all stores")
else:
    print(f"   ⚠️  e_initial is {e_initial_vals[0]} (expected 0.0)")

# Check actual store states at start and end
print("\n" + "=" * 80)
print("STORE STATE VERIFICATION")
print("=" * 80)

store_states = n.stores_t.e[industry_dsr_stores]
initial_states = store_states.iloc[0].sum()
final_states = store_states.iloc[-1].sum()

print(f"\nTotal store energy states:")
print(f"   Initial (first hour): {initial_states:.2f} MWh")
print(f"   Final (last hour): {final_states:.2f} MWh")
print(f"   Difference: {final_states - initial_states:.2f} MWh")

if abs(final_states - initial_states) < 1.0:
    print("   ✓ Initial and final states are approximately equal (e_cyclic working)")
else:
    print("   ✗ Initial and final states differ significantly (e_cyclic may not be enforced)")

# Check states at checkpoint hours
print(f"\nStore states at checkpoint hours:")
for profile, stores in list(stores_by_profile.items())[:3]:  # Check first 3 profiles
    if profile not in dsr_profile.columns:
        continue
    
    expected_profile = dsr_profile[profile].reindex(n.snapshots).ffill().bfill()
    checkpoint_hours = expected_profile[expected_profile == 0.0].index
    
    if len(checkpoint_hours) > 0:
        # Get states for stores of this profile at checkpoint hours
        profile_stores = [s for s in stores if s in store_states.columns]
        if len(profile_stores) > 0:
            checkpoint_states = store_states.loc[checkpoint_hours, profile_stores].sum(axis=1)
            max_at_checkpoint = checkpoint_states.max()
            min_at_checkpoint = checkpoint_states.min()
            
            print(f"   {profile}:")
            print(f"     Checkpoint hours: {len(checkpoint_hours)}")
            print(f"     State range at checkpoints: [{min_at_checkpoint:.2f}, {max_at_checkpoint:.2f}] MWh")
            
            if abs(max_at_checkpoint) < 10.0 and abs(min_at_checkpoint) < 10.0:
                print(f"     ✓ States are near zero at checkpoints")
            else:
                print(f"     ⚠️  States are NOT near zero at checkpoints")

# Final summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

if all_time_varying and all_checkpoints_correct:
    print("\n✓ SUCCESS: DSR profile is being applied correctly!")
    print("   - Constraints are time-varying")
    print("   - Checkpoint hours have zero constraints")
    print("   - Stores should balance energy within each period")
else:
    print("\n✗ ISSUES FOUND:")
    if not all_time_varying:
        print("   - Some profiles have constant constraints (DSR profile not applied)")
    if not all_checkpoints_correct:
        print("   - Checkpoint hours do not have zero constraints")

print("\n" + "=" * 80)
