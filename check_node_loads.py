#!/usr/bin/env python3
"""Check which profiles each node has load for."""

import pypsa
import pandas as pd

# Load the network
network_path = "results/Test_2030/networks/base_s_5___2030.nc"
n = pypsa.Network(network_path)

print("=" * 80)
print("NODE LOAD PROFILE CHECK")
print("=" * 80)

# Get industry loads
industry_loads = n.loads[n.loads.carrier == "industry electricity"]
print(f"\n1. Industry loads: {len(industry_loads)}")
print(f"   Load names: {list(industry_loads.index)}")

# Check per-profile temporal file to see which profiles each node has
try:
    import os
    per_profile_file = "results/Test_2030/industrial_electricity_demand_per_profile_temporal_base_s_5_2030.csv"
    if os.path.exists(per_profile_file):
        per_profile = pd.read_csv(per_profile_file, index_col=0, parse_dates=True)
        print(f"\n2. Per-profile temporal file found: {per_profile_file}")
        print(f"   Shape: {per_profile.shape}")
        print(f"   Columns (first 20): {list(per_profile.columns[:20])}")
        
        # Extract node and profile from column names "node|profile"
        node_profiles = {}
        for col in per_profile.columns:
            if "|" in col:
                node, profile = col.split("|", 1)
                if node not in node_profiles:
                    node_profiles[node] = []
                node_profiles[node].append(profile)
        
        print(f"\n3. Profiles per node:")
        for node in sorted(node_profiles.keys()):
            profiles = sorted(set(node_profiles[node]))
            print(f"   {node}: {len(profiles)} profiles")
            print(f"      {', '.join(profiles)}")
            
            # Check if "Iron & steel industry" is in profiles
            if "Iron & steel industry" in profiles:
                load_col = f"{node}|Iron & steel industry"
                if load_col in per_profile.columns:
                    max_load = per_profile[load_col].max()
                    mean_load = per_profile[load_col].mean()
                    print(f"      'Iron & steel industry' load: max={max_load:.2f} MW, mean={mean_load:.2f} MW")
            else:
                print(f"      ⚠️  No 'Iron & steel industry' profile")
    else:
        print(f"\n2. Per-profile temporal file not found: {per_profile_file}")
except Exception as e:
    print(f"\n2. Error reading per-profile file: {e}")

print("\n" + "=" * 80)
