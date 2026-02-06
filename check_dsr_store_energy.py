#!/usr/bin/env python3
"""Check DSR store energy states to understand why both links are operating."""

import pypsa
import pandas as pd
import numpy as np

network_path = "results/Test_2030/networks/base_s_5___2030.nc"

print("=" * 80)
print("DSR STORE ENERGY STATE CHECK")
print("=" * 80)

n = pypsa.Network(network_path)
print(f"\n✓ Network loaded: {network_path}")

dsr_stores = n.stores.index[n.stores.carrier == "industry dsr"]
if len(dsr_stores) == 0:
    print("No DSR stores found!")
    exit(1)

sample_store = dsr_stores[0]
print(f"\nSample store: {sample_store}")

# Check store properties
print(f"\n1. Store Properties:")
print(f"   e_nom: {n.stores.loc[sample_store, 'e_nom']:.2f} MWh")
print(f"   e_cyclic: {n.stores.loc[sample_store, 'e_cyclic']}")
print(f"   e_initial: {n.stores.loc[sample_store, 'e_initial']}")

# Check store energy state
if hasattr(n.stores_t, 'e'):
    store_energy = n.stores_t.e.loc[:, sample_store]
    print(f"\n2. Store Energy State:")
    print(f"   Initial energy: {store_energy.iloc[0]:.2f} MWh")
    print(f"   Final energy: {store_energy.iloc[-1]:.2f} MWh")
    print(f"   Min energy: {store_energy.min():.2f} MWh")
    print(f"   Max energy: {store_energy.max():.2f} MWh")
    print(f"   Mean energy: {store_energy.mean():.2f} MWh")
    
    # Check if energy is constant
    if store_energy.nunique() == 1:
        print(f"   ⚠️  Energy is constant at {store_energy.iloc[0]:.2f} MWh (no charging/discharging happening)")
    else:
        print(f"   ✓ Energy is varying (store is being used)")

# Check e_max_pu and e_min_pu constraints
if hasattr(n.stores_t, 'e_max_pu'):
    e_max_pu = n.stores_t.e_max_pu.loc[:, sample_store]
    e_min_pu = n.stores_t.e_min_pu.loc[:, sample_store]
    
    print(f"\n3. Store Energy Constraints (e_max_pu / e_min_pu):")
    print(f"   e_max_pu range: {e_max_pu.min():.4f} to {e_max_pu.max():.4f}")
    print(f"   e_min_pu range: {e_min_pu.min():.4f} to {e_min_pu.max():.4f}")
    
    # Check if constraints are time-varying
    if e_max_pu.nunique() == 1:
        print(f"   ⚠️  e_max_pu is constant ({e_max_pu.iloc[0]:.4f})")
    else:
        print(f"   ✓ e_max_pu is time-varying")
    
    if e_min_pu.nunique() == 1:
        print(f"   ⚠️  e_min_pu is constant ({e_min_pu.iloc[0]:.4f})")
    else:
        print(f"   ✓ e_min_pu is time-varying")
    
    # Check if store energy is within bounds
    if hasattr(n.stores_t, 'e'):
        e_nom = n.stores.loc[sample_store, 'e_nom']
        e_state_pu = store_energy / e_nom
        max_violation = (e_state_pu - e_max_pu).max()
        min_violation = (e_min_pu - e_state_pu).max()
        
        print(f"\n4. Constraint Violations:")
        print(f"   Max violation (e_state > e_max_pu): {max_violation:.6f}")
        print(f"   Min violation (e_state < e_min_pu): {min_violation:.6f}")
        
        if max_violation > 0.001 or min_violation > 0.001:
            print(f"   ⚠️  Constraint violations detected!")
        else:
            print(f"   ✓ No constraint violations")

# Check link dispatch
charge_links = n.links.index[n.links.carrier == "industry dsr charge"]
discharge_links = n.links.index[n.links.carrier == "industry dsr discharge"]

charge_name = f"{sample_store} charge"
discharge_name = f"{sample_store} discharge"

if charge_name in charge_links and discharge_name in discharge_links:
    charge_p = n.links_t.p0.loc[:, charge_name]
    discharge_p = n.links_t.p0.loc[:, discharge_name]
    
    print(f"\n5. Link Dispatch Analysis:")
    print(f"   Charge link: constant at {charge_p.iloc[0]:.2f} MW")
    print(f"   Discharge link: constant at {discharge_p.iloc[0]:.2f} MW")
    print(f"   Net store dispatch: {(charge_p - discharge_p).iloc[0]:.2f} MW")
    
    # Check if both are operating simultaneously
    simultaneous_hours = ((charge_p > 0.01) & (discharge_p > 0.01)).sum()
    print(f"\n   Hours with both links operating: {simultaneous_hours} / {len(charge_p)}")
    
    if simultaneous_hours > 0:
        print(f"   ⚠️  Both links are operating simultaneously!")
        print(f"      This is unrealistic - we need a constraint to prevent this")
        print(f"      Possible fix: Add constraint that charge_link * discharge_link = 0")

print("\n" + "=" * 80)
