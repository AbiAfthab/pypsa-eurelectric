#!/usr/bin/env python3
"""Check industry DSR store constraints and checkpoint profile."""

import pypsa
import pandas as pd
import numpy as np

# Load the network
network_path = "results/Test_2030/networks/base_s_5___2030.nc"
n = pypsa.Network(network_path)

print("=" * 80)
print("INDUSTRY DSR CONSTRAINT CHECK")
print("=" * 80)

# Get industry DSR stores
industry_stores = n.stores.index[n.stores.carrier == "industry dsr"]
print(f"\n1. Industry DSR stores: {len(industry_stores)}")

if len(industry_stores) > 0:
    # Check e_max_pu and e_min_pu
    print(f"\n2. Store constraints (e_max_pu / e_min_pu):")
    
    # Check if time-varying or constant
    if hasattr(n.stores_t, 'e_max_pu'):
        e_max_pu = n.stores_t.e_max_pu[industry_stores]
        e_min_pu = n.stores_t.e_min_pu[industry_stores]
        
        print(f"   Time-varying constraints: YES")
        print(f"   e_max_pu shape: {e_max_pu.shape}")
        print(f"   e_min_pu shape: {e_min_pu.shape}")
        
        # Check for checkpoint hours (where e_max_pu = 0)
        zero_hours = (e_max_pu.abs() < 0.001).sum(axis=1)
        print(f"\n3. Checkpoint hours (where e_max_pu ≈ 0):")
        print(f"   Stores with zero constraints at some hours: {(zero_hours > 0).sum()} / {len(industry_stores)}")
        print(f"   Total zero-constraint hours: {zero_hours.sum()}")
        
        # Check specific hours for checkpoint
        sample_store = industry_stores[0]
        print(f"\n4. Sample store '{sample_store}' constraints at key hours:")
        key_hours = [0, 6, 12, 18]
        for h in key_hours:
            if h < len(e_max_pu):
                print(f"   Hour {h}: e_max_pu={e_max_pu.iloc[h, 0]:.4f}, e_min_pu={e_min_pu.iloc[h, 0]:.4f}")
        
        # Check store states vs constraints
        if hasattr(n.stores_t, 'e'):
            store_energy = n.stores_t.e[industry_stores]
            e_nom = n.stores.loc[industry_stores, 'e_nom']
            
            print(f"\n5. Store states vs constraints:")
            for h in key_hours:
                if h < len(store_energy):
                    state_pu = store_energy.iloc[h, 0] / e_nom.iloc[0]
                    max_pu = e_max_pu.iloc[h, 0]
                    min_pu = e_min_pu.iloc[h, 0]
                    print(f"   Hour {h}: state_pu={state_pu:.4f}, should be in [{min_pu:.4f}, {max_pu:.4f}]")
                    if state_pu > max_pu + 0.001 or state_pu < min_pu - 0.001:
                        print(f"      ⚠️  CONSTRAINT VIOLATION!")
    else:
        # Constant constraints
        e_max_pu_const = n.stores.loc[industry_stores, 'e_max_pu']
        e_min_pu_const = n.stores.loc[industry_stores, 'e_min_pu']
        print(f"   Time-varying constraints: NO (constant)")
        print(f"   e_max_pu: {e_max_pu_const.unique()}")
        print(f"   e_min_pu: {e_min_pu_const.unique()}")
    
    # Check e_cyclic and e_initial
    print(f"\n6. Store cyclic properties:")
    print(f"   e_cyclic: {n.stores.loc[industry_stores, 'e_cyclic'].unique()}")
    print(f"   e_initial: {n.stores.loc[industry_stores, 'e_initial'].unique()}")
    
    # Check if stores actually start/end at same state
    if hasattr(n.stores_t, 'e'):
        store_energy = n.stores_t.e[industry_stores]
        initial_total = store_energy.iloc[0].sum()
        final_total = store_energy.iloc[-1].sum()
        print(f"\n7. Store state at start vs end:")
        print(f"   Initial total state: {initial_total:.2f} MWh")
        print(f"   Final total state: {final_total:.2f} MWh")
        print(f"   Difference: {final_total - initial_total:.2f} MWh")
        print(f"   With e_cyclic=True, should be 0.0 MWh")
        
        if abs(final_total - initial_total) > 0.1:
            print(f"   ⚠️  WARNING: Stores are NOT cyclic! e_cyclic constraint may not be working.")

print("\n" + "=" * 80)
