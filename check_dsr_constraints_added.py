#!/usr/bin/env python3
"""Check if DSR constraints (store-link coupling and ramp) were added during solve."""

import pypsa
import pandas as pd

network_path = "results/Test_2030/networks/base_s_5___2030.nc"

print("=" * 80)
print("DSR CONSTRAINTS VERIFICATION")
print("=" * 80)

n = pypsa.Network(network_path)
print(f"\n✓ Network loaded: {network_path}")

# Check if network was solved
if not hasattr(n, 'objective') or n.objective is None:
    print("\n⚠️  Network appears not to be solved (no objective value)")
    print("   Constraints are only added during the solve step")
    exit(0)

print(f"\n✓ Network is solved (objective: {n.objective:.2e})")

# Check for DSR links
charge_links = n.links.index[n.links.carrier == "industry dsr charge"]
discharge_links = n.links.index[n.links.carrier == "industry dsr discharge"]
dsr_stores = n.stores.index[n.stores.carrier == "industry dsr"]

print(f"\n1. DSR Components:")
print(f"   Stores: {len(dsr_stores)}")
print(f"   Charge links: {len(charge_links)}")
print(f"   Discharge links: {len(discharge_links)}")

# Check link dispatch (to see if they're being used)
if len(charge_links) > 0 and hasattr(n.links_t, 'p0'):
    charge_dispatch = n.links_t.p0[charge_links]
    print(f"\n2. Charge Link Dispatch:")
    print(f"   Total charge link dispatch range: {charge_dispatch.sum(axis=1).min():.2f} to {charge_dispatch.sum(axis=1).max():.2f} MW")
    print(f"   Mean charge link dispatch: {charge_dispatch.sum(axis=1).mean():.2f} MW")
    print(f"   Hours with charging: {(charge_dispatch.sum(axis=1) > 0.01).sum()} / {len(charge_dispatch)}")

if len(discharge_links) > 0 and hasattr(n.links_t, 'p0'):
    discharge_dispatch = n.links_t.p0[discharge_links]
    print(f"\n3. Discharge Link Dispatch:")
    print(f"   Total discharge link dispatch range: {discharge_dispatch.sum(axis=1).min():.2f} to {discharge_dispatch.sum(axis=1).max():.2f} MW")
    print(f"   Mean discharge link dispatch: {discharge_dispatch.sum(axis=1).mean():.2f} MW")
    print(f"   Hours with discharging: {(discharge_dispatch.sum(axis=1) > 0.01).sum()} / {len(discharge_dispatch)}")

# Check store dispatch
if len(dsr_stores) > 0 and hasattr(n.stores_t, 'p'):
    store_dispatch = n.stores_t.p[dsr_stores]
    print(f"\n4. Store Dispatch:")
    print(f"   Total store dispatch range: {store_dispatch.sum(axis=1).min():.2f} to {store_dispatch.sum(axis=1).max():.2f} MW")
    print(f"   Mean store dispatch: {store_dispatch.sum(axis=1).mean():.2f} MW")
    
    # Check energy balance (should be ~0 with e_cyclic=True)
    total_store_energy = store_dispatch.sum().sum()
    print(f"   Total energy dispatched: {total_store_energy:.2f} MWh (should be ~0 for cyclic)")

# Check for rapid cycling (if ramp constraints are working)
if len(charge_links) > 0 and hasattr(n.links_t, 'p0'):
    # Calculate hourly changes in link dispatch
    charge_changes = charge_dispatch.sum(axis=1).diff().abs()
    discharge_changes = discharge_dispatch.sum(axis=1).diff().abs() if len(discharge_links) > 0 else pd.Series()
    
    print(f"\n5. Ramp Constraint Check (Rapid Cycling Prevention):")
    if len(charge_changes) > 0:
        print(f"   Charge link hourly changes:")
        print(f"     Max change: {charge_changes.max():.2f} MW")
        print(f"     Mean change: {charge_changes.mean():.2f} MW")
        print(f"     Std change: {charge_changes.std():.2f} MW")
    
    if len(discharge_changes) > 0:
        print(f"   Discharge link hourly changes:")
        print(f"     Max change: {discharge_changes.max():.2f} MW")
        print(f"     Mean change: {discharge_changes.mean():.2f} MW")
        print(f"     Std change: {discharge_changes.std():.2f} MW")
    
    # Check if changes are reasonable (should be limited by ramp_rate * p_nom)
    # Default ramp_rate is 0.5, so max change should be ~50% of p_nom per hour
    sample_p_nom = n.links.loc[charge_links[0], "p_nom"]
    expected_max_ramp = sample_p_nom * 0.5  # 50% per hour default
    print(f"\n   Expected max ramp (50% of p_nom): {expected_max_ramp:.2f} MW")
    if len(charge_changes) > 0:
        actual_max_change = charge_changes.max()
        if actual_max_change > expected_max_ramp * 1.1:  # Allow 10% tolerance
            print(f"   ⚠️  Max change ({actual_max_change:.2f} MW) exceeds expected ramp limit!")
        else:
            print(f"   ✓ Max change ({actual_max_change:.2f} MW) is within ramp limit")

# Verify store-link coupling (store_p = charge_link - discharge_link)
if len(dsr_stores) > 0 and len(charge_links) > 0 and len(discharge_links) > 0:
    print(f"\n6. Store-Link Coupling Verification:")
    sample_store = dsr_stores[0]
    charge_name = f"{sample_store} charge"
    discharge_name = f"{sample_store} discharge"
    
    if charge_name in charge_links and discharge_name in discharge_links:
        store_p = n.stores_t.p.loc[:, sample_store]
        charge_p = n.links_t.p0.loc[:, charge_name]
        discharge_p = n.links_t.p0.loc[:, discharge_name]
        
        # Constraint: store_p = charge_p - discharge_p
        coupling_error = (store_p - (charge_p - discharge_p)).abs()
        max_error = coupling_error.max()
        mean_error = coupling_error.mean()
        
        print(f"   Sample store: {sample_store}")
        print(f"   Max coupling error: {max_error:.6f} MW")
        print(f"   Mean coupling error: {mean_error:.6f} MW")
        
        if max_error < 0.01:  # Should be very close to 0
            print(f"   ✓ Store-link coupling constraint is working correctly!")
        else:
            print(f"   ⚠️  Store-link coupling error is larger than expected")
            print(f"      This might indicate the constraint wasn't added or isn't being enforced")

print("\n" + "=" * 80)
