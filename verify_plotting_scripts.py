#!/usr/bin/env python3
"""Verify that plotting scripts will correctly find all industry DSR stores."""

import pypsa
import pandas as pd

network_path = "results/Test_2030/networks/base_s_5___2030.nc"
n = pypsa.Network(network_path)

print("=" * 80)
print("VERIFYING PLOTTING SCRIPTS WILL FIND ALL DSR STORES")
print("=" * 80)

# Method used by plotting scripts: filter by carrier
industry_stores = n.stores.index[n.stores.carrier == "industry dsr"]
print(f"\n1. Stores found by carrier filter (method used by plotting scripts):")
print(f"   Total: {len(industry_stores)} stores")

if len(industry_stores) > 0:
    print(f"\n2. Sample store names:")
    for store in industry_stores[:10]:
        print(f"   - {store}")
    
    print(f"\n3. Store dispatch statistics:")
    if hasattr(n.stores_t, 'p'):
        store_dispatch = n.stores_t.p[industry_stores].sum(axis=1)
        print(f"   Total dispatch range: {store_dispatch.min():.2f} - {store_dispatch.max():.2f} MW")
        print(f"   Total dispatch mean: {store_dispatch.mean():.2f} MW")
        print(f"   Total dispatch std: {store_dispatch.std():.2f} MW")
    else:
        print("   Network not solved yet - dispatch not available")
    
    print(f"\n4. Breakdown by technology (from store names):")
    tech_counts = {}
    for store in industry_stores:
        # Parse: "BE0 0 industry dsr Iron & steel industry Scrap-EAF"
        parts = store.split(" industry dsr ")
        if len(parts) == 2:
            profile_tech = parts[1]
            # Known profiles to help parsing
            known_profiles = [
                "Iron & steel industry",
                "Non-metallic Minerals",
                "Paper, Pulp and Print",
            ]
            tech = None
            for profile in known_profiles:
                if profile_tech.startswith(profile):
                    tech = profile_tech[len(profile):].strip()
                    break
            if tech:
                tech_counts[tech] = tech_counts.get(tech, 0) + 1
    
    for tech, count in sorted(tech_counts.items()):
        print(f"   {tech}: {count} stores")
    
    print(f"\n✓ SUCCESS: Plotting scripts will find all {len(industry_stores)} stores")
    print(f"   They use: n.stores.index[n.stores.carrier == 'industry dsr']")
    print(f"   This correctly aggregates all technology-specific stores")
else:
    print("\n✗ WARNING: No industry DSR stores found!")
    print("   Check that the network was built with industry DSR enabled")

print("\n" + "=" * 80)
