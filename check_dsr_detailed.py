#!/usr/bin/env python3
"""Detailed check of industry DSR stores per technology and node."""

import pypsa
import pandas as pd

# Load the network
network_path = "results/Test_2030/networks/base_s_5___2030.nc"
n = pypsa.Network(network_path)

print("=" * 80)
print("DETAILED INDUSTRY DSR CHECK")
print("=" * 80)

# Get industry loads
industry_loads = n.loads[n.loads.carrier == "industry electricity"]
print(f"\n1. Industry loads: {len(industry_loads)}")
print(f"   Load buses: {sorted(industry_loads.bus.unique())}")

# Get DSR stores
dsr_stores = n.stores[n.stores.carrier == "industry dsr"]
print(f"\n2. Industry DSR stores: {len(dsr_stores)}")

if len(dsr_stores) > 0:
    # Parse store names: "BE0 0 industry dsr Iron & steel industry Scrap-EAF"
    # Format: "{node} industry dsr {profile} {technology}"
    # Technology names can have spaces (e.g., "Cement mills", "Pulp production")
    store_info = []
    for store_name in dsr_stores.index:
        parts = store_name.split(" industry dsr ")
        if len(parts) == 2:
            node = parts[0]
            profile_tech = parts[1]
            
            # Known profile names (to help with parsing)
            known_profiles = [
                "Iron & steel industry",
                "Non-metallic Minerals",
                "Paper, Pulp and Print",
                "Food and Tobacco",
                "Non-specified (Industry)",
                "Textile and Leather",
                "Wood and Wood Products",
                "Transport Equipment",
                "Machinery",
            ]
            
            # Try to match known profiles first
            tech = None
            profile = None
            for known_profile in known_profiles:
                if profile_tech.startswith(known_profile):
                    profile = known_profile
                    tech = profile_tech[len(known_profile):].strip()
                    break
            
            # If no match found, try to split on last space (fallback)
            if profile is None:
                if " " in profile_tech:
                    profile, tech = profile_tech.rsplit(" ", 1)
                else:
                    profile = profile_tech
                    tech = None
            
            store_info.append({
                "store": store_name,
                "node": node,
                "profile": profile,
                "technology": tech if tech else None,
                "bus": dsr_stores.loc[store_name, "bus"],
                "e_nom": dsr_stores.loc[store_name, "e_nom"],
            })
    
    store_df = pd.DataFrame(store_info)
    
    print(f"\n3. Stores by technology:")
    if "technology" in store_df.columns:
        tech_counts = store_df["technology"].value_counts()
        for tech, count in tech_counts.items():
            print(f"   {tech}: {count} stores")
    
    print(f"\n4. Stores by node:")
    node_counts = store_df["node"].value_counts()
    for node, count in node_counts.items():
        print(f"   {node}: {count} stores")
        node_stores = store_df[store_df["node"] == node]
        if "technology" in node_stores.columns:
            techs = node_stores["technology"].unique()
            print(f"      Technologies: {', '.join(techs)}")
    
    print(f"\n5. Nodes with loads but no stores:")
    load_nodes = set(industry_loads.bus.str.replace(" low voltage", "").unique())
    store_nodes = set(store_df["node"].unique())
    missing_nodes = load_nodes - store_nodes
    if missing_nodes:
        print(f"   {sorted(missing_nodes)}")
        for node in sorted(missing_nodes):
            node_loads = industry_loads[industry_loads.bus == f"{node} low voltage"]
            print(f"   {node}: {len(node_loads)} loads")
            for load in node_loads.index:
                print(f"      - {load}")
    else:
        print("   None (all nodes with loads have stores)")
    
    print(f"\n6. Store energy capacity (e_nom):")
    print(f"   Range: {store_df['e_nom'].min():.2f} - {store_df['e_nom'].max():.2f} MWh")
    print(f"   Mean: {store_df['e_nom'].mean():.2f} MWh")
    print(f"   Total: {store_df['e_nom'].sum():.2f} MWh")
    
    print(f"\n7. Sample stores:")
    for idx, row in store_df.head(10).iterrows():
        print(f"   {row['store']}")
        print(f"      Node: {row['node']}, Bus: {row['bus']}, e_nom: {row['e_nom']:.2f} MWh")

print("\n" + "=" * 80)
