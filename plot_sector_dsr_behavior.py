#!/usr/bin/env python3
"""Plot DSR behavior for a specific industry sector/profile."""

import argparse
import sys
import os

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import pypsa
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def get_sector_loads(n, profile_name):
    """
    Get baseline and net loads for a specific industry profile.
    
    Parameters
    ----------
    n : pypsa.Network
        Solved network
    profile_name : str
        FfE profile name (e.g., "Iron & steel industry", "Non-metallic Minerals")
    
    Returns
    -------
    baseline : pd.Series
        Baseline load for this profile (MW) - NOTE: This is total industry load at nodes with this profile
    net : pd.Series
        Net load (baseline + DSR dispatch) for this profile (MW)
    dsr_dispatch : pd.Series
        DSR dispatch for this profile (MW)
    profile_stores : list
        List of store names for this profile
    """
    # Find DSR stores for this profile
    industry_stores = n.stores.index[n.stores.carrier == "industry dsr"]
    profile_stores = [s for s in industry_stores if profile_name in s]
    
    if not profile_stores:
        print(f"Warning: No DSR stores found for profile '{profile_name}'")
        return None, None, None, None
    
    # Extract nodes from store names
    # Format: "BE0 0 industry dsr Iron & steel industry Scrap-EAF"
    nodes = set()
    store_buses = set()
    for store in profile_stores:
        parts = store.split(" industry dsr ")
        if len(parts) == 2:
            node = parts[0]
            nodes.add(node)
            # Also get the bus where the store is connected
            bus = n.stores.loc[store, "bus"]
            store_buses.add(bus)
    
    print(f"Found {len(profile_stores)} DSR stores for profile '{profile_name}'")
    print(f"Stores at nodes: {sorted(nodes)}")
    
    # Find loads at buses where stores are connected
    # Store buses are like "BE0 0 low voltage"
    # Load buses should match
    industry_loads = n.loads.index[n.loads.carrier == "industry electricity"]
    profile_loads = []
    for load in industry_loads:
        load_bus = n.loads.loc[load, "bus"]
        # Check if this load is at a bus where we have stores
        # Or check if the node matches
        load_node = load.replace(" industry electricity", "")
        if load_node in nodes or load_bus in store_buses:
            profile_loads.append(load)
    
    if not profile_loads:
        print(f"Warning: No loads found for nodes with profile '{profile_name}'")
        print(f"  Store buses: {sorted(store_buses)}")
        print(f"  Available load buses: {sorted(n.loads.loc[industry_loads, 'bus'].unique())}")
        return None, None, None, None
    
    print(f"Found {len(profile_loads)} loads at nodes with profile '{profile_name}'")
    
    # Get baseline load (p_set)
    # NOTE: This is the TOTAL industry load at these nodes, not just this profile's load
    # because loads are aggregated per node, not per profile
    baseline = n.loads_t.p_set[profile_loads].reindex(n.snapshots).fillna(0).sum(axis=1)
    
    # Get DSR dispatch for this profile
    dsr_dispatch = n.stores_t.p[profile_stores].reindex(n.snapshots).fillna(0).sum(axis=1)
    
    # Net load (baseline + DSR dispatch for this profile)
    # NOTE: This shows the effect of this profile's DSR on the total industry load at these nodes
    net = baseline + dsr_dispatch
    
    return baseline, net, dsr_dispatch, profile_stores


def get_bus_prices(n, store_buses=None, bus_carrier="AC"):
    """
    Get average electricity prices from buses.
    
    Parameters
    ----------
    n : pypsa.Network
        Solved network
    store_buses : list, optional
        Specific buses to get prices for (e.g., where stores are connected)
    bus_carrier : str
        Bus carrier to use if store_buses not provided
    
    Returns
    -------
    pd.Series
        Average price per snapshot
    """
    # If specific buses provided (e.g., where stores are), use those
    if store_buses is not None and len(store_buses) > 0:
        buses = [b for b in store_buses if b in n.buses.index]
        if len(buses) == 0:
            print(f"Warning: None of the specified buses found in network")
            buses = n.buses.index[n.buses.carrier == bus_carrier]
    else:
        # Get AC buses (or specified carrier)
        buses = n.buses.index[n.buses.carrier == bus_carrier]
    
    if len(buses) == 0:
        # Try low voltage buses if AC buses not found
        buses = n.buses.index[n.buses.carrier == "low voltage"]
    
    if len(buses) == 0:
        print(f"Warning: No buses found with carrier '{bus_carrier}'")
        return pd.Series(dtype=float, index=n.snapshots)
    
    # Get marginal prices (shadow prices of power balance constraint)
    # In PyPSA, this is stored in buses_t.marginal_price
    # Units should be €/MWh (or currency/MWh)
    if hasattr(n.buses_t, 'marginal_price'):
        prices = n.buses_t.marginal_price[buses]
        # Average across buses
        if len(buses) == 1:
            price_series = prices.iloc[:, 0]
        else:
            price_series = prices.mean(axis=1)
        
        # Check if prices seem reasonable (should be ~30-100 €/MWh typically)
        # If prices are > 1000, there might be a unit/scaling issue
        # With temporal aggregation, snapshot weightings might affect prices
        if price_series.max() > 1000:
            print(f"⚠️  WARNING: Prices seem very high (max: {price_series.max():.2f} €/MWh)")
            print(f"   Expected range: ~30-100 €/MWh")
            
            # Check snapshot weightings
            if hasattr(n, 'snapshot_weightings'):
                weights = n.snapshot_weightings.generators
                print(f"   Snapshot weightings: {weights.iloc[0]:.2f} (each snapshot represents ~{weights.iloc[0]:.1f} hours)")
                
                # The prices are way too high - this is a critical issue
                # Even dividing by weightings gives ~1000 €/MWh which is still wrong
                print(f"   ⚠️  CRITICAL: Prices are unrealistic even after normalization")
                print(f"   This suggests a fundamental issue with the optimization or price calculation")
                print(f"   DSR-price correlation will be unreliable with these prices")
                print(f"   Please check:")
                print(f"   1. Generator costs/marginal costs in the optimization")
                print(f"   2. Whether the network was solved correctly")
                print(f"   3. If there are binding constraints causing unrealistic prices")
    else:
        print("Warning: No marginal prices found. Network may not be solved.")
        print("  Make sure the network was solved with n.optimize()")
        return pd.Series(0.0, index=n.snapshots)
    
    return price_series


def plot_sector_behavior(n, profile_name, output_path=None, days=None):
    """
    Plot load behavior for a specific industry sector.
    
    Parameters
    ----------
    n : pypsa.Network
        Solved network
    profile_name : str
        Industry profile name
    output_path : str, optional
        Output file path
    days : int, optional
        Number of days to plot
    """
    baseline, net, dsr_dispatch, profile_stores = get_sector_loads(n, profile_name)
    
    if baseline is None:
        print(f"Could not find data for profile '{profile_name}'")
        return None
    
    # Get prices from buses where stores are connected (more accurate)
    if profile_stores:
        store_buses = [n.stores.loc[s, "bus"] for s in profile_stores]
        prices = get_bus_prices(n, store_buses=store_buses)
    else:
        prices = get_bus_prices(n)
    
    # Limit to specified days
    if days:
        snapshots = baseline.index[:days*24] if len(baseline.index) >= days*24 else baseline.index
        baseline = baseline.reindex(snapshots)
        net = net.reindex(snapshots)
        dsr_dispatch = dsr_dispatch.reindex(snapshots)
        prices = prices.reindex(snapshots)
    else:
        snapshots = baseline.index
    
    # Create figure with 3 subplots
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    
    # Top: Baseline vs Net load
    ax0 = axes[0]
    ax0.plot(snapshots, baseline.values, label="Baseline load", color="C0", linewidth=2, linestyle="--", alpha=0.7)
    ax0.plot(snapshots, net.values, label="Net load (with DSR)", color="C1", linewidth=2)
    
    # Shade difference
    difference = net.values - baseline.values
    ax0.fill_between(snapshots, baseline.values, net.values, 
                     where=(difference > 0), alpha=0.3, color="C3", label="DSR increase")
    ax0.fill_between(snapshots, baseline.values, net.values, 
                     where=(difference < 0), alpha=0.3, color="C2", label="DSR decrease")
    
    ax0.set_ylabel("Load (MW)")
    ax0.set_title(f"{profile_name}: Baseline vs Net Load")
    ax0.legend(loc="upper right")
    ax0.grid(True, alpha=0.3)
    
    # Middle: DSR dispatch
    ax1 = axes[1]
    ax1.plot(snapshots, dsr_dispatch.values, color="C2", linewidth=1.5)
    ax1.axhline(y=0, color="k", linestyle="--", alpha=0.3)
    ax1.fill_between(snapshots, 0, dsr_dispatch.values, 
                     where=(dsr_dispatch.values > 0), alpha=0.3, color="C3", label="Charging (increase load)")
    ax1.fill_between(snapshots, 0, dsr_dispatch.values, 
                     where=(dsr_dispatch.values < 0), alpha=0.3, color="C2", label="Discharging (decrease load)")
    ax1.set_ylabel("DSR Dispatch (MW)\n(>0 = charge, <0 = discharge)")
    ax1.set_title(f"{profile_name}: DSR Dispatch")
    ax1.legend(loc="upper right")
    ax1.grid(True, alpha=0.3)
    
    # Bottom: Prices
    ax2 = axes[2]
    ax2_twin = ax2.twinx()
    
    # Plot prices on right axis
    ax2_twin.plot(snapshots, prices.values, color="C4", linewidth=1.5, label="Electricity price")
    ax2_twin.set_ylabel("Price (€/MWh)", color="C4")
    ax2_twin.tick_params(axis='y', labelcolor="C4")
    
    # Plot DSR dispatch on left axis for comparison
    ax2.plot(snapshots, dsr_dispatch.values, color="C2", linewidth=1, alpha=0.5, label="DSR dispatch")
    ax2.axhline(y=0, color="k", linestyle="--", alpha=0.3)
    ax2.set_ylabel("DSR Dispatch (MW)", color="C2")
    ax2.tick_params(axis='y', labelcolor="C2")
    ax2.set_xlabel("Time")
    ax2.set_title(f"{profile_name}: DSR Dispatch vs Prices")
    
    # Format x-axis
    ax2.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(snapshots) // (7*24))))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d\n%H:%M"))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    fig.suptitle(f"Industry DSR Behavior: {profile_name}", fontsize=16, fontweight='bold')
    fig.tight_layout()
    
    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        fig.savefig(output_path, bbox_inches="tight", dpi=150)
        print(f"Saved plot to {output_path}")
    
    # Print statistics
    print(f"\n{'='*80}")
    print(f"STATISTICS FOR: {profile_name}")
    print(f"{'='*80}")
    print(f"NOTE: Baseline load shown is TOTAL industry load at nodes with this profile,")
    print(f"      not just this profile's load (loads are aggregated per node)")
    print(f"")
    print(f"Baseline load: {baseline.mean():.2f} MW (mean), {baseline.min():.2f} - {baseline.max():.2f} MW (range)")
    print(f"Net load: {net.mean():.2f} MW (mean), {net.min():.2f} - {net.max():.2f} MW (range)")
    print(f"DSR dispatch: {dsr_dispatch.mean():.2f} MW (mean), {dsr_dispatch.min():.2f} - {dsr_dispatch.max():.2f} MW (range)")
    print(f"Max load increase: {(net - baseline).max():.2f} MW")
    print(f"Max load decrease: {(net - baseline).min():.2f} MW")
    print(f"Total energy shifted: {dsr_dispatch.sum():.2f} MWh (should be ~0 for energy-neutral)")
    
    # Correlation with prices
    if not prices.isna().all() and prices.std() > 0:
        # Align indices and remove NaN
        common_idx = dsr_dispatch.index.intersection(prices.index)
        dsr_aligned = dsr_dispatch.reindex(common_idx)
        prices_aligned = prices.reindex(common_idx)
        
        # Remove NaN values
        valid_mask = ~(dsr_aligned.isna() | prices_aligned.isna())
        dsr_clean = dsr_aligned[valid_mask]
        prices_clean = prices_aligned[valid_mask]
        
        if len(dsr_clean) > 1 and dsr_clean.std() > 0 and prices_clean.std() > 0:
            corr = dsr_clean.corr(prices_clean)
            print(f"DSR-Price correlation: {corr:.3f} (expected: negative, discharge when prices high)")
            print(f"  Price range: {prices_clean.min():.2f} - {prices_clean.max():.2f} €/MWh")
            print(f"  Price mean: {prices_clean.mean():.2f} €/MWh")
            print(f"  Price std: {prices_clean.std():.2f} €/MWh")
            print(f"  DSR dispatch range: {dsr_clean.min():.2f} - {dsr_clean.max():.2f} MW")
            print(f"  DSR dispatch std: {dsr_clean.std():.2f} MW")
            
            # Show sample of high price vs low price behavior
            price_median = prices_clean.median()
            high_price_hours = dsr_clean[prices_clean > price_median]
            low_price_hours = dsr_clean[prices_clean <= price_median]
            print(f"  Average DSR dispatch when prices HIGH (> {price_median:.2f} €/MWh): {high_price_hours.mean():.2f} MW")
            print(f"  Average DSR dispatch when prices LOW (≤ {price_median:.2f} €/MWh): {low_price_hours.mean():.2f} MW")
            print(f"  Expected: High price → negative dispatch (discharge), Low price → positive dispatch (charge)")
        else:
            print("Warning: Cannot calculate correlation (insufficient variation in data)")
    else:
        print("Warning: Prices not available or constant")
        if prices.isna().all():
            print("  All prices are NaN - network may not have been solved with prices")
        elif prices.std() == 0:
            print(f"  Prices are constant: {prices.iloc[0]:.2f} €/MWh")
    
    return fig


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot DSR behavior for a specific industry sector")
    parser.add_argument("--network", required=True, help="Path to solved network")
    parser.add_argument("--profile", required=True, help="Industry profile name (e.g., 'Iron & steel industry', 'Non-metallic Minerals', 'Paper, Pulp and Print')")
    parser.add_argument("--output", "-o", default=None, help="Output figure path")
    parser.add_argument("--days", type=int, default=None, help="Number of days to plot")
    
    args = parser.parse_args()
    
    n = pypsa.Network(args.network)
    
    plot_sector_behavior(
        n,
        profile_name=args.profile,
        output_path=args.output,
        days=args.days,
    )
