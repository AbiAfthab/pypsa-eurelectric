#!/usr/bin/env python3
"""Check why the baseline model is infeasible."""

import pypsa
import pandas as pd

network_path = "results/Test_2030_baseline/networks/base_s_5___2030.nc"

print("=" * 80)
print("BASELINE MODEL INFEASIBILITY CHECK")
print("=" * 80)

try:
    n = pypsa.Network(network_path)
    print(f"\n✓ Network loaded: {network_path}")
except Exception as e:
    print(f"\n✗ Error loading network: {e}")
    exit(1)

# Check if network was solved
if hasattr(n, 'objective') and n.objective is not None:
    print(f"✓ Network was solved (objective: {n.objective:.2e})")
else:
    print(f"✗ Network was NOT solved (no objective value)")

# Check global constraints
print(f"\n1. Global Constraints:")
if hasattr(n, 'global_constraints') and len(n.global_constraints) > 0:
    print(f"   Found {len(n.global_constraints)} global constraints:")
    for gc_name in n.global_constraints.index:
        gc = n.global_constraints.loc[gc_name]
        print(f"\n   {gc_name}:")
        print(f"     type: {gc.get('type', 'N/A')}")
        print(f"     sense: {gc.get('sense', 'N/A')}")
        print(f"     constant: {gc.get('constant', 'N/A')}")
        
        # Check if it's a CO2 constraint
        if 'CO2' in gc_name or gc.get('type', '') == 'co2_limit':
            print(f"     ⚠️  This is a CO2 constraint - might be too tight!")
else:
    print("   No global constraints found")

# Check CO2 budget from config
print(f"\n2. CO2 Budget Configuration:")
if hasattr(n, 'config'):
    co2_budget = n.config.get('co2_budget', {})
    if 2030 in co2_budget:
        print(f"   CO2 budget for 2030: {co2_budget[2030]} (fraction of 1990 levels)")
        if co2_budget[2030] < 0.5:
            print(f"     ⚠️  Very tight CO2 budget ({co2_budget[2030]*100:.0f}% of 1990)!")

# Check electricity CO2 limit
print(f"\n3. Electricity CO2 Limit:")
if hasattr(n, 'config'):
    elec_config = n.config.get('electricity', {})
    co2limit_enable = elec_config.get('co2limit_enable', False)
    co2limit = elec_config.get('co2limit', None)
    print(f"   co2limit_enable: {co2limit_enable}")
    print(f"   co2limit: {co2limit}")

# Check generators and their capacities
print(f"\n4. Generator Capacities:")
if len(n.generators) > 0:
    print(f"   Total generators: {len(n.generators)}")
    print(f"   Total capacity: {n.generators.p_nom.sum():.2f} MW")
    
    # Check renewable vs conventional
    renewable = n.generators[n.generators.carrier.isin(['solar', 'onwind', 'offwind-ac', 'offwind-dc', 'offwind-float'])]
    conventional = n.generators[~n.generators.carrier.isin(['solar', 'onwind', 'offwind-ac', 'offwind-dc', 'offwind-float', 'hydro', 'ror'])]
    
    print(f"   Renewable capacity: {renewable.p_nom.sum():.2f} MW")
    print(f"   Conventional capacity: {conventional.p_nom.sum():.2f} MW")
    
    if conventional.p_nom.sum() == 0:
        print(f"     ⚠️  No conventional generators - might cause infeasibility if demand is high!")

# Check loads
print(f"\n5. Loads:")
if len(n.loads) > 0:
    total_load = n.loads_t.p_set.sum(axis=1).sum()
    max_load = n.loads_t.p_set.sum(axis=1).max()
    print(f"   Total energy demand: {total_load:.2f} MWh")
    print(f"   Peak demand: {max_load:.2f} MW")
    
    # Check if demand can be met
    total_gen_capacity = n.generators.p_nom.sum()
    if max_load > total_gen_capacity:
        print(f"     ⚠️  Peak demand ({max_load:.2f} MW) exceeds total capacity ({total_gen_capacity:.2f} MW)!")
        print(f"        This would make the model infeasible!")

print("\n" + "=" * 80)
print("RECOMMENDATIONS:")
print("=" * 80)
print("If model is infeasible, check:")
print("1. CO2 constraint might be too tight - try relaxing it")
print("2. Peak demand might exceed available capacity")
print("3. Check solver log for more details:")
print(f"   cat results/Test_2030_baseline/logs/base_s_5___2030_solver.log | tail -50")
print("=" * 80)
