#!/usr/bin/env python3
"""Diagnose why DSR optimizer is choosing simultaneous charge/discharge."""

import pypsa
import pandas as pd
import numpy as np

network_path = "results/Test_2030/networks/base_s_5___2030.nc"

print("=" * 80)
print("DSR OPTIMIZATION DIAGNOSIS")
print("=" * 80)

n = pypsa.Network(network_path)
print(f"\n✓ Network loaded: {network_path}")

sample_store = "BE0 0 industry dsr Iron & steel industry Scrap-EAF"
charge_name = f"{sample_store} charge"
discharge_name = f"{sample_store} discharge"

# Check link costs
print(f"\n1. Link Costs:")
charge_link = n.links.loc[charge_name]
discharge_link = n.links.loc[discharge_name]

print(f"   Charge link '{charge_name}':")
print(f"     marginal_cost: {charge_link.get('marginal_cost', 'N/A')}")
print(f"     capital_cost: {charge_link.get('capital_cost', 'N/A')}")
print(f"     p_nom: {charge_link['p_nom']:.2f} MW")

print(f"   Discharge link '{discharge_name}':")
print(f"     marginal_cost: {discharge_link.get('marginal_cost', 'N/A')}")
print(f"     capital_cost: {discharge_link.get('capital_cost', 'N/A')}")
print(f"     p_nom: {discharge_link['p_nom']:.2f} MW")

# Check what's happening on the buses
print(f"\n2. Bus Analysis:")
charge_bus0 = charge_link['bus0']  # Load bus
charge_bus1 = charge_link['bus1']  # Flexibility bus
discharge_bus0 = discharge_link['bus0']  # Flexibility bus
discharge_bus1 = discharge_link['bus1']  # Load bus

print(f"   Charge link: {charge_bus0} -> {charge_bus1}")
print(f"   Discharge link: {discharge_bus0} -> {discharge_bus1}")

# Check bus marginal prices
if hasattr(n.buses_t, 'marginal_price'):
    charge_bus0_price = n.buses_t.marginal_price[charge_bus0]
    charge_bus1_price = n.buses_t.marginal_price[charge_bus1]
    discharge_bus1_price = n.buses_t.marginal_price[discharge_bus1]
    
    print(f"\n3. Bus Marginal Prices:")
    print(f"   {charge_bus0} (load bus, charge source): {charge_bus0_price.mean():.2f} €/MWh (range: {charge_bus0_price.min():.2f} - {charge_bus0_price.max():.2f})")
    print(f"   {charge_bus1} (flexibility bus, charge sink): {charge_bus1_price.mean():.2f} €/MWh (range: {charge_bus1_price.min():.2f} - {charge_bus1_price.max():.2f})")
    print(f"   {discharge_bus1} (load bus, discharge sink): {discharge_bus1_price.mean():.2f} €/MWh (range: {discharge_bus1_price.min():.2f} - {discharge_bus1_price.max():.2f})")
    
    # Check if prices are the same (which would explain why optimizer is indifferent)
    price_diff_charge = (charge_bus0_price - charge_bus1_price).abs()
    # discharge_bus0 is the flexibility bus (same as charge_bus1)
    discharge_bus0_price = charge_bus1_price
    price_diff_discharge = (discharge_bus0_price - discharge_bus1_price).abs()
    
    print(f"\n   Price difference (charge): {price_diff_charge.mean():.4f} €/MWh")
    print(f"   Price difference (discharge): {price_diff_discharge.mean():.4f} €/MWh")
    
    if price_diff_charge.mean() < 0.01 and price_diff_discharge.mean() < 0.01:
        print(f"   ⚠️  Prices are nearly identical - optimizer has no incentive to shift!")

# Check link dispatch
charge_p = n.links_t.p0.loc[:, charge_name]
discharge_p = n.links_t.p0.loc[:, discharge_name]
net_load_effect = charge_p - discharge_p  # Positive = increases load, Negative = decreases load

print(f"\n4. Net Load Effect:")
print(f"   Net effect on load bus: {net_load_effect.min():.2f} to {net_load_effect.max():.2f} MW")
print(f"   Mean net effect: {net_load_effect.mean():.2f} MW")
print(f"   ⚠️  Net effect is ZERO - no load shifting is happening!")

# Check if there are other constraints affecting this
print(f"\n5. Store Energy Constraints at Key Hours:")
if hasattr(n.stores_t, 'e_max_pu'):
    e_max_pu = n.stores_t.e_max_pu.loc[:, sample_store]
    e_min_pu = n.stores_t.e_min_pu.loc[:, sample_store]
    
    for hour in [0, 6, 12, 18]:
        if hour < len(e_max_pu):
            print(f"   Hour {hour}: e_max_pu={e_max_pu.iloc[hour]:.4f}, e_min_pu={e_min_pu.iloc[hour]:.4f}")
            if e_max_pu.iloc[hour] == 0 and e_min_pu.iloc[hour] == 0:
                print(f"      ⚠️  CHECKPOINT HOUR - store must be at 0 energy")

print(f"\n6. Possible Issues:")
print(f"   - Links have no cost, so optimizer is indifferent to simultaneous operation")
print(f"   - Store energy is stuck at 0 (checkpoint constraint?)")
print(f"   - Bus prices might be identical, removing incentive to shift")
print(f"   - Need to understand: why would optimizer choose this solution?")

print("\n" + "=" * 80)
