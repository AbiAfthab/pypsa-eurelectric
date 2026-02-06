#!/usr/bin/env python3
"""Check if CO2 constraint shadow price is affecting electricity prices."""

import pypsa
import pandas as pd

network_path = "results/Test_2030/networks/base_s_5___2030.nc"
n = pypsa.Network(network_path)

print("=" * 80)
print("CHECKING CO2 CONSTRAINT IMPACT ON PRICES")
print("=" * 80)

# Get CO2 shadow price
if "CO2Limit" in n.global_constraints.index:
    co2_shadow = n.global_constraints.loc["CO2Limit", "mu"]
    print(f"\nCO2Limit shadow price (mu): {co2_shadow:.2e}")
    print(f"  (This is the cost per ton of CO2)")
    
    # Check if this is reasonable
    # Typical CO2 prices: 50-200 €/tCO2
    if abs(co2_shadow) > 10000:
        print(f"  ⚠️  WARNING: Shadow price is extremely high!")
        print(f"     Expected range: 50-200 €/tCO2")
        print(f"     This might indicate:")
        print(f"     1. CO2 limit is too strict (very binding)")
        print(f"     2. Unit conversion issue")
        print(f"     3. Optimization problem")

# Get electricity prices
ac_buses = n.buses.index[n.buses.carrier == "AC"]
if len(ac_buses) > 0:
    prices = n.buses_t.marginal_price[ac_buses].mean(axis=1).mean()
    print(f"\nAverage electricity price: {prices:.2f} €/MWh")
    
    # Check generator CO2 emissions
    if len(n.generators) > 0:
        # Get average CO2 emissions per MWh for generators
        if 'co2_emissions' in n.carriers.columns:
            gen_carriers = n.generators.carrier.unique()
            co2_emissions = n.carriers.loc[gen_carriers, 'co2_emissions'].fillna(0)
            
            # Weight by capacity
            gen_caps = n.generators.groupby('carrier')['p_nom'].sum()
            weighted_co2 = (co2_emissions * gen_caps).sum() / gen_caps.sum()
            
            print(f"\nAverage generator CO2 emissions: {weighted_co2:.4f} tCO2/MWh")
            
            # Calculate expected price impact
            if "CO2Limit" in n.global_constraints.index:
                co2_cost_impact = weighted_co2 * abs(co2_shadow)
                print(f"\nExpected CO2 cost impact on price: {co2_cost_impact:.2f} €/MWh")
                print(f"  (CO2_emissions * |CO2_shadow_price|)")
                
                # Check generator marginal costs
                if 'marginal_cost' in n.generators.columns:
                    mc_mean = n.generators.marginal_cost.mean()
                    expected_price = mc_mean + co2_cost_impact
                    print(f"\nExpected total price: {expected_price:.2f} €/MWh")
                    print(f"  (marginal_cost + CO2_cost_impact)")
                    print(f"Actual price: {prices:.2f} €/MWh")
                    print(f"Difference: {prices - expected_price:.2f} €/MWh")
                    
                    if abs(prices - expected_price) > 1000:
                        print(f"\n⚠️  Price doesn't match expected calculation!")
                        print(f"   This suggests a unit conversion or calculation issue")

# Check CO2 limit value
if "CO2Limit" in n.global_constraints.index:
    co2_limit = n.global_constraints.loc["CO2Limit", "constant"]
    print(f"\nCO2Limit constant: {co2_limit:.2e} tCO2")
    print(f"  (Total CO2 budget for the optimization period)")
    
    # Check if limit is reasonable
    # For Belgium, annual CO2 emissions are ~100 MtCO2
    # With 1 week (168 hours), that's ~100e6 / 8760 * 168 ≈ 1.9 MtCO2
    if co2_limit < 1e6:
        print(f"  ⚠️  CO2 limit seems very low (< 1 MtCO2)")
    elif co2_limit > 1e9:
        print(f"  ⚠️  CO2 limit seems very high (> 1 GtCO2)")

print("\n" + "=" * 80)
