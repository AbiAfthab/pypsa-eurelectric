#!/usr/bin/env python3
"""Investigate the unrealistic electricity prices issue."""

import pypsa
import pandas as pd
import numpy as np

network_path = "results/Test_2030/networks/base_s_5___2030.nc"

print("=" * 80)
print("ELECTRICITY PRICE INVESTIGATION")
print("=" * 80)

n = pypsa.Network(network_path)
print(f"\n✓ Network loaded: {network_path}")

# Check if network is solved
if not hasattr(n, 'objective') or n.objective is None:
    print("\n⚠️  Network not solved")
    exit(1)

print(f"✓ Network solved (objective: {n.objective:.2e})")

# 1. Check bus prices
print(f"\n1. Bus Marginal Prices:")
if hasattr(n.buses_t, 'marginal_price'):
    # Get AC bus prices (main electricity buses)
    ac_buses = n.buses.index[n.buses.carrier == "AC"]
    if len(ac_buses) > 0:
        ac_prices = n.buses_t.marginal_price[ac_buses]
        print(f"   AC buses ({len(ac_buses)}):")
        print(f"     Mean price: {ac_prices.mean().mean():.2f} €/MWh")
        print(f"     Min price: {ac_prices.min().min():.2f} €/MWh")
        print(f"     Max price: {ac_prices.max().max():.2f} €/MWh")
        
        if ac_prices.mean().mean() > 1000:
            print(f"     ⚠️  PRICES ARE UNREALISTICALLY HIGH!")
            print(f"        Expected: ~30-100 €/MWh")
            print(f"        Actual: {ac_prices.mean().mean():.0f} €/MWh")
    
    # Check low voltage bus prices
    lv_buses = n.buses.index[n.buses.index.str.contains("low voltage", case=False, na=False)]
    if len(lv_buses) > 0:
        lv_prices = n.buses_t.marginal_price[lv_buses]
        print(f"\n   Low voltage buses ({len(lv_buses)}):")
        print(f"     Mean price: {lv_prices.mean().mean():.2f} €/MWh")
        print(f"     Min price: {lv_prices.min().min():.2f} €/MWh")
        print(f"     Max price: {lv_prices.max().max():.2f} €/MWh")

# 2. Check global constraints and shadow prices
print(f"\n2. Global Constraints:")
if hasattr(n, 'global_constraints') and len(n.global_constraints) > 0:
    print(f"   Found {len(n.global_constraints)} global constraints:")
    for gc_name in n.global_constraints.index:
        gc = n.global_constraints.loc[gc_name]
        print(f"\n   {gc_name}:")
        print(f"     type: {gc.get('type', 'N/A')}")
        print(f"     sense: {gc.get('sense', 'N/A')}")
        print(f"     constant: {gc.get('constant', 'N/A')}")
        
        # Check shadow price (mu)
        if hasattr(n, 'global_constraints_t') and hasattr(n.global_constraints_t, 'mu'):
            mu = n.global_constraints_t.mu.loc[:, gc_name]
            print(f"     Shadow price (mu):")
            print(f"       Mean: {mu.mean():.2f}")
            print(f"       Min: {mu.min():.2f}")
            print(f"       Max: {mu.max():.2f}")
            
            if abs(mu.mean()) > 1000:
                print(f"       ⚠️  VERY HIGH SHADOW PRICE - constraint is very binding!")
                print(f"          This could be causing the high electricity prices")

# 3. Check generator marginal costs
print(f"\n3. Generator Marginal Costs:")
generators = n.generators.index
if len(generators) > 0:
    # Get marginal costs from generators
    if 'marginal_cost' in n.generators.columns:
        gen_mc = n.generators['marginal_cost']
        print(f"   Generator marginal costs:")
        print(f"     Mean: {gen_mc.mean():.2f} €/MWh")
        print(f"     Min: {gen_mc.min():.2f} €/MWh")
        print(f"     Max: {gen_mc.max():.2f} €/MWh")
        
        # Compare to bus prices
        if hasattr(n.buses_t, 'marginal_price'):
            ac_prices_mean = ac_prices.mean().mean() if len(ac_buses) > 0 else 0
            gen_mc_mean = gen_mc.mean()
            ratio = ac_prices_mean / gen_mc_mean if gen_mc_mean > 0 else 0
            print(f"\n   Price vs Marginal Cost Ratio:")
            print(f"     Bus price / Generator MC: {ratio:.1f}x")
            if ratio > 10:
                print(f"     ⚠️  Bus prices are {ratio:.0f}x higher than generator marginal costs!")
                print(f"        This suggests prices are driven by binding constraints, not generator costs")

# 4. Check CO2 constraint specifically
print(f"\n4. CO2 Constraint Check:")
co2_constraints = n.global_constraints.index[n.global_constraints.index.str.contains("CO2", case=False, na=False)]
if len(co2_constraints) > 0:
    for co2_name in co2_constraints:
        print(f"   {co2_name}:")
        gc = n.global_constraints.loc[co2_name]
        print(f"     constant: {gc.get('constant', 'N/A')}")
        print(f"     sense: {gc.get('sense', 'N/A')}")
        
        if hasattr(n, 'global_constraints_t') and hasattr(n.global_constraints_t, 'mu'):
            mu = n.global_constraints_t.mu.loc[:, co2_name]
            print(f"     Shadow price: {mu.mean():.2f} (range: {mu.min():.2f} to {mu.max():.2f})")
            
            if abs(mu.mean()) > 10000:
                print(f"     ⚠️  EXTREMELY HIGH CO2 SHADOW PRICE!")
                print(f"        This is likely the cause of unrealistic electricity prices")
                print(f"        The CO2 limit is so tight that it's driving prices up")

# 5. Check config for CO2 settings
print(f"\n5. Configuration Check:")
if hasattr(n, 'config'):
    costs_config = n.config.get('costs', {})
    emission_prices = costs_config.get('emission_prices', {})
    if emission_prices.get('enable', False):
        co2_price = emission_prices.get('co2', 0)
        print(f"   CO2 emission price: {co2_price} €/tCO2")
    else:
        print(f"   CO2 emission prices: disabled")
    
    # Check for CO2 limit
    if hasattr(n, 'global_constraints'):
        co2_limits = n.global_constraints.index[n.global_constraints.index.str.contains("CO2", case=False, na=False)]
        if len(co2_limits) > 0:
            print(f"   CO2 limit constraints found: {list(co2_limits)}")

print("\n" + "=" * 80)
print("RECOMMENDATIONS:")
print("=" * 80)
print("If prices are unrealistic (>1000 €/MWh):")
print("1. Check CO2Limit constraint - it may be too tight")
print("2. Check emission prices in config - they may be too high")
print("3. Check if CO2 constraint is binding (high shadow price)")
print("4. Consider relaxing CO2 limit or adjusting emission prices")
print("=" * 80)
