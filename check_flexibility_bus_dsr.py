#!/usr/bin/env python3
"""Check the new flexibility bus DSR architecture."""

import pypsa
import pandas as pd
import numpy as np

network_path = "results/Test_2030/networks/base_s_5___2030.nc"

print("=" * 80)
print("FLEXIBILITY BUS DSR ARCHITECTURE CHECK")
print("=" * 80)

try:
    n = pypsa.Network(network_path)
    print(f"\n✓ Network loaded: {network_path}")
except FileNotFoundError:
    print(f"\n✗ Network file not found: {network_path}")
    print("   Please build the network first:")
    print("   snakemake -j 1 results/Test_2030/networks/base_s_5___2030.nc --configfile config/test/config.industry.flex.yaml")
    exit(1)

# 1. Check flexibility buses
flexibility_buses = n.buses.index[n.buses.carrier == "industry dsr flexibility"]
print(f"\n1. Flexibility buses: {len(flexibility_buses)}")
if len(flexibility_buses) > 0:
    print(f"   Sample buses: {list(flexibility_buses[:3])}")
else:
    print("   ✗ No flexibility buses found!")

# 2. Check DSR stores
dsr_stores = n.stores.index[n.stores.carrier == "industry dsr"]
print(f"\n2. DSR stores: {len(dsr_stores)}")
if len(dsr_stores) > 0:
    print(f"   Sample stores: {list(dsr_stores[:3])}")
    # Check if stores are on flexibility buses
    store_buses = n.stores.loc[dsr_stores, "bus"]
    flexibility_store_buses = store_buses[store_buses.isin(flexibility_buses)]
    print(f"   Stores on flexibility buses: {len(flexibility_store_buses)}/{len(dsr_stores)}")
    if len(flexibility_store_buses) < len(dsr_stores):
        print(f"   ⚠️  Some stores are NOT on flexibility buses!")
        print(f"   Stores on other buses: {set(store_buses) - set(flexibility_buses)}")
else:
    print("   ✗ No DSR stores found!")

# 3. Check charge links
charge_links = n.links.index[n.links.carrier == "industry dsr charge"]
print(f"\n3. Charge links: {len(charge_links)}")
if len(charge_links) > 0:
    print(f"   Sample links: {list(charge_links[:3])}")
    # Check link properties
    sample_link = charge_links[0]
    print(f"   Sample link '{sample_link}':")
    print(f"     bus0 (load bus): {n.links.loc[sample_link, 'bus0']}")
    print(f"     bus1 (flexibility bus): {n.links.loc[sample_link, 'bus1']}")
    print(f"     p_nom: {n.links.loc[sample_link, 'p_nom']:.2f} MW")
    print(f"     p_min_pu: {n.links.loc[sample_link, 'p_min_pu']}")
    print(f"     p_max_pu: {n.links.loc[sample_link, 'p_max_pu']}")
    
    # Check if bus1 is a flexibility bus
    charge_bus1 = n.links.loc[charge_links, "bus1"]
    charge_on_flex_buses = charge_bus1.isin(flexibility_buses)
    print(f"   Links connected to flexibility buses: {charge_on_flex_buses.sum()}/{len(charge_links)}")
    
    # Check for negative_only (p_nom = 0)
    zero_capacity_charge = (n.links.loc[charge_links, "p_nom"] == 0).sum()
    if zero_capacity_charge > 0:
        print(f"   Charge links with p_nom=0 (negative_only): {zero_capacity_charge}")
else:
    print("   ✗ No charge links found!")

# 4. Check discharge links
discharge_links = n.links.index[n.links.carrier == "industry dsr discharge"]
print(f"\n4. Discharge links: {len(discharge_links)}")
if len(discharge_links) > 0:
    print(f"   Sample links: {list(discharge_links[:3])}")
    # Check link properties
    sample_link = discharge_links[0]
    print(f"   Sample link '{sample_link}':")
    print(f"     bus0 (flexibility bus): {n.links.loc[sample_link, 'bus0']}")
    print(f"     bus1 (load bus): {n.links.loc[sample_link, 'bus1']}")
    print(f"     p_nom: {n.links.loc[sample_link, 'p_nom']:.2f} MW")
    print(f"     p_min_pu: {n.links.loc[sample_link, 'p_min_pu']}")
    print(f"     p_max_pu: {n.links.loc[sample_link, 'p_max_pu']}")
    
    # Check if bus0 is a flexibility bus
    discharge_bus0 = n.links.loc[discharge_links, "bus0"]
    discharge_on_flex_buses = discharge_bus0.isin(flexibility_buses)
    print(f"   Links connected from flexibility buses: {discharge_on_flex_buses.sum()}/{len(discharge_links)}")
else:
    print("   ✗ No discharge links found!")

# 5. Verify store-link coupling (check naming convention)
print(f"\n5. Store-Link Coupling Verification:")
if len(dsr_stores) > 0 and len(charge_links) > 0 and len(discharge_links) > 0:
    matched_pairs = 0
    for store_name in dsr_stores[:5]:  # Check first 5
        charge_name = f"{store_name} charge"
        discharge_name = f"{store_name} discharge"
        if charge_name in charge_links and discharge_name in discharge_links:
            matched_pairs += 1
            print(f"   ✓ {store_name}: links found")
        else:
            print(f"   ✗ {store_name}: links NOT found")
            if charge_name not in charge_links:
                print(f"      Missing charge link: {charge_name}")
            if discharge_name not in discharge_links:
                print(f"      Missing discharge link: {discharge_name}")
    print(f"   Matched store-link pairs: {matched_pairs}/{min(5, len(dsr_stores))}")

# 6. Check bus connections (low voltage)
print(f"\n6. Bus Connections (Low Voltage):")
if len(charge_links) > 0:
    charge_bus0 = n.links.loc[charge_links, "bus0"]
    charge_low_voltage = charge_bus0.str.contains("low voltage", case=False, na=False).sum()
    print(f"   Charge links bus0 (load bus) with 'low voltage': {charge_low_voltage}/{len(charge_links)}")
    
if len(discharge_links) > 0:
    discharge_bus1 = n.links.loc[discharge_links, "bus1"]
    discharge_low_voltage = discharge_bus1.str.contains("low voltage", case=False, na=False).sum()
    print(f"   Discharge links bus1 (load bus) with 'low voltage': {discharge_low_voltage}/{len(discharge_links)}")

# 7. Summary
print(f"\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Flexibility buses: {len(flexibility_buses)}")
print(f"DSR stores: {len(dsr_stores)}")
print(f"Charge links: {len(charge_links)}")
print(f"Discharge links: {len(discharge_links)}")

if len(flexibility_buses) > 0 and len(dsr_stores) > 0 and len(charge_links) > 0 and len(discharge_links) > 0:
    print("\n✓ Flexibility bus architecture appears to be set up correctly!")
else:
    print("\n✗ Architecture incomplete - some components missing!")

print("\n" + "=" * 80)
