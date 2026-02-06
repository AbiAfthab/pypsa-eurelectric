#!/usr/bin/env python3
"""Quick check of industry DSR stores."""

import pypsa
import pandas as pd

network_path = "results/Test_2030/networks/base_s_5___2030.nc"
n = pypsa.Network(network_path)

print("=" * 80)
print("INDUSTRY DSR CHECK")
print("=" * 80)

# Get industry loads
industry_loads = n.loads[n.loads.carrier == "industry electricity"]
print(f"\n1. Industry loads: {len(industry_loads)}")

# Get DSR stores
dsr_stores = n.stores[n.stores.carrier == "industry dsr"]
print(f"\n2. Industry DSR stores: {len(dsr_stores)}")

if len(dsr_stores) > 0:
    # Parse store names to extract technology
    store_info = []
    for store_name in dsr_stores.index:
        parts = store_name.split(" industry dsr ")
        if len(parts) == 2:
            node = parts[0]
            profile_tech = parts[1]
            # Format: "Iron & steel industry Scrap-EAF" or "Non-metallic Minerals Cement mills"
            if " " in profile_tech:
                # Try to split on last space (technology name)
                parts_tech = profile_tech.rsplit(" ", 1)
                if len(parts_tech) == 2:
                    profile, tech = parts_tech
                else:
                    profile = profile_tech
                    tech = None
            else:
                profile = profile_tech
                tech = None
            store_info.append({
                "store": store_name,
                "node": node,
                "profile": profile,
                "technology": tech,
            })
    
    store_df = pd.DataFrame(store_info)
    
    print(f"\n3. Stores by technology:")
    if "technology" in store_df.columns and store_df["technology"].notna().any():
        tech_counts = store_df["technology"].value_counts()
        for tech, count in tech_counts.items():
            print(f"   {tech}: {count} stores")
    else:
        print("   (No technology breakdown found in store names)")
    
    print(f"\n4. Stores by profile:")
    profile_counts = store_df["profile"].value_counts()
    for profile, count in profile_counts.items():
        print(f"   {profile}: {count} stores")
    
    print(f"\n5. Sample stores (first 15):")
    for idx, row in store_df.head(15).iterrows():
        tech_str = f" | {row['technology']}" if row['technology'] else ""
        print(f"   {row['store']}{tech_str}")
    
    # Check store capacities
    print(f"\n6. Store energy capacity (e_nom):")
    e_nom_values = dsr_stores["e_nom"]
    print(f"   Range: {e_nom_values.min():.2f} - {e_nom_values.max():.2f} MWh")
    print(f"   Mean: {e_nom_values.mean():.2f} MWh")
    print(f"   Total: {e_nom_values.sum():.2f} MWh")

print("\n" + "=" * 80)
