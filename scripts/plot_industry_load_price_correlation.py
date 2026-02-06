# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Plot correlation between electricity prices and industry load (baseline vs net with DSR).

Shows how industry load shifts in response to price signals:
- Net demand should be lower than baseline when prices are high (load shifted away)
- Net demand should be higher than baseline when prices are low (load shifted to)
"""

import argparse
import logging
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pypsa
from scipy import stats

from scripts._helpers import configure_logging

logger = logging.getLogger(__name__)

INDUSTRY_LOAD_CARRIER = "industry electricity"
INDUSTRY_DSR_CARRIER = "industry dsr"


def get_bus_prices(n, bus_carrier="AC"):
    """
    Get electricity prices from buses (marginal prices).
    
    Parameters
    ----------
    n : pypsa.Network
        Solved network
    bus_carrier : str
        Bus carrier to get prices for (default: "AC" for AC buses)
    
    Returns
    -------
    pd.Series
        Average price across all buses of the specified carrier, per snapshot
    """
    # Get AC buses (or specified carrier)
    buses = n.buses.index[n.buses.carrier == bus_carrier]
    
    if len(buses) == 0:
        # Try low voltage buses if AC buses not found
        buses = n.buses.index[n.buses.carrier == "low voltage"]
    
    if len(buses) == 0:
        logger.warning(f"No buses found with carrier '{bus_carrier}'")
        return pd.Series(dtype=float, index=n.snapshots)
    
    # Get marginal prices
    if hasattr(n.buses_t, 'marginal_price'):
        prices = n.buses_t.marginal_price[buses]
    else:
        logger.warning("marginal_price not available")
        return pd.Series(np.nan, index=n.snapshots)
    
    # Average across all buses
    if len(buses) == 1:
        price_series = prices.iloc[:, 0]
    else:
        price_series = prices.mean(axis=1)
    
    return price_series


def get_industry_loads(n):
    """
    Get baseline and net industry electricity demand.
    
    Parameters
    ----------
    n : pypsa.Network
        Solved network
    
    Returns
    -------
    baseline : pd.Series
        Baseline industry electricity load (MW) per snapshot
    net : pd.Series
        Net industry electricity load with DSR (MW) per snapshot
    store_dispatch : pd.Series
        Industry DSR store dispatch (MW) per snapshot
    """
    # Industry electricity loads
    industry_loads = n.loads.index[n.loads.carrier == INDUSTRY_LOAD_CARRIER]
    if industry_loads.empty:
        logger.warning("No industry electricity loads found")
        baseline = pd.Series(0.0, index=n.snapshots)
    else:
        baseline = n.loads_t.p_set[industry_loads].reindex(n.snapshots).fillna(0).sum(axis=1)
    
    # Industry DSR stores
    industry_stores = n.stores.index[n.stores.carrier == INDUSTRY_DSR_CARRIER]
    if industry_stores.empty:
        store_dispatch = pd.Series(0.0, index=n.snapshots)
        net = baseline
    else:
        store_dispatch = n.stores_t.p[industry_stores].reindex(n.snapshots).fillna(0).sum(axis=1)
        net = baseline + store_dispatch
    
    return baseline, net, store_dispatch


def plot_load_price_correlation(
    n,
    output_path=None,
    days=None,
    bus_carrier="AC",
    title=None,
):
    """
    Plot correlation between electricity prices and industry load (baseline vs net).
    
    Parameters
    ----------
    n : pypsa.Network
        Solved network with industry DSR
    output_path : str or None
        Path to save figure
    days : int or None
        Number of days to plot (None = all)
    bus_carrier : str
        Bus carrier to get prices from
    title : str or None
        Plot title
    """
    # Get prices and loads
    prices = get_bus_prices(n, bus_carrier=bus_carrier)
    baseline, net, store_dispatch = get_industry_loads(n)
    
    # Align indices
    common_snapshots = prices.index.intersection(net.index)
    prices = prices.reindex(common_snapshots)
    baseline = baseline.reindex(common_snapshots)
    net = net.reindex(common_snapshots)
    store_dispatch = store_dispatch.reindex(common_snapshots)
    
    # Filter by days if specified
    if days and days > 0:
        max_snapshots = min(days * 24, len(common_snapshots))
        prices = prices.iloc[:max_snapshots]
        baseline = baseline.iloc[:max_snapshots]
        net = net.iloc[:max_snapshots]
        store_dispatch = store_dispatch.iloc[:max_snapshots]
        snapshots = prices.index
    else:
        snapshots = prices.index
    
    # Remove NaN values for correlation
    valid_mask = ~(prices.isna() | net.isna() | baseline.isna())
    prices_clean = prices[valid_mask]
    baseline_clean = baseline[valid_mask]
    net_clean = net[valid_mask]
    load_shift = net_clean - baseline_clean  # Positive = increased demand, Negative = decreased demand
    
    if len(prices_clean) == 0:
        logger.error("No valid price data found")
        return None
    
    # Calculate correlations
    corr_baseline, p_baseline = stats.pearsonr(prices_clean.values, baseline_clean.values)
    corr_net, p_net = stats.pearsonr(prices_clean.values, net_clean.values)
    corr_shift, p_shift = stats.pearsonr(prices_clean.values, load_shift.values)
    
    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Top left: Scatter plot - Price vs Net demand (with DSR)
    ax0 = axes[0, 0]
    ax0.scatter(prices_clean, baseline_clean, alpha=0.5, s=20, label='Baseline', color='C0', marker='o')
    ax0.scatter(prices_clean, net_clean, alpha=0.6, s=20, label='Net (with DSR)', color='C1', marker='s')
    ax0.set_xlabel("Electricity price (EUR/MWh)")
    ax0.set_ylabel("Industry load (MW)")
    ax0.set_title(f"Price vs Industry Load\nBaseline corr: {corr_baseline:.3f}, Net corr: {corr_net:.3f}")
    ax0.legend()
    ax0.grid(True, alpha=0.3)
    
    # Add trend lines
    if len(prices_clean) > 1:
        z_baseline = np.polyfit(prices_clean.values, baseline_clean.values, 1)
        z_net = np.polyfit(prices_clean.values, net_clean.values, 1)
        x_trend = np.linspace(prices_clean.min(), prices_clean.max(), 100)
        ax0.plot(x_trend, np.poly1d(z_baseline)(x_trend), "C0--", alpha=0.8, linewidth=2)
        ax0.plot(x_trend, np.poly1d(z_net)(x_trend), "C1--", alpha=0.8, linewidth=2)
    
    # Top right: Scatter plot - Price vs Load shift (net - baseline)
    ax1 = axes[0, 1]
    scatter = ax1.scatter(prices_clean, load_shift, alpha=0.6, s=30, c=range(len(prices_clean)), cmap='coolwarm')
    ax1.set_xlabel("Electricity price (EUR/MWh)")
    ax1.set_ylabel("Load shift (MW)\n(Net - Baseline)")
    ax1.set_title(f"Price vs Load Shift\nCorrelation: {corr_shift:.3f} (p={p_shift:.3f})")
    ax1.grid(True, alpha=0.3)
    ax1.axhline(0, color='k', linestyle='--', linewidth=0.5)
    ax1.axvline(prices_clean.mean(), color='r', linestyle='--', linewidth=0.5, alpha=0.5)
    
    # Add trend line
    if len(prices_clean) > 1:
        z_shift = np.polyfit(prices_clean.values, load_shift.values, 1)
        x_trend = np.linspace(prices_clean.min(), prices_clean.max(), 100)
        ax1.plot(x_trend, np.poly1d(z_shift)(x_trend), "r--", alpha=0.8, linewidth=2, 
                label=f'Trend: y={z_shift[0]:.2f}x+{z_shift[1]:.2f}')
        ax1.legend()
    
    # Bottom left: Time series overlay - Prices and loads
    ax2 = axes[1, 0]
    ax2_twin = ax2.twinx()
    
    line1 = ax2.plot(snapshots, prices, color='C0', linewidth=1.5, label='Price', alpha=0.7)
    line2 = ax2.plot(snapshots, baseline, color='C2', linewidth=1.5, linestyle='--', label='Baseline load', alpha=0.7)
    line3 = ax2_twin.plot(snapshots, net, color='C1', linewidth=1.5, label='Net load (with DSR)', alpha=0.7)
    
    ax2.set_xlabel("Time")
    ax2.set_ylabel("Electricity price (EUR/MWh)", color='C0')
    ax2_twin.set_ylabel("Industry load (MW)", color='C1')
    ax2.set_title("Price and Industry Load Over Time")
    ax2.tick_params(axis='y', labelcolor='C0')
    ax2_twin.tick_params(axis='y', labelcolor='C1')
    ax2.grid(True, alpha=0.3)
    
    # Combine legends
    lines = line1 + line2 + line3
    labels = [l.get_label() for l in lines]
    ax2.legend(lines, labels, loc='upper left')
    
    # Bottom right: Net load by price quartiles
    ax3 = axes[1, 1]
    price_quartiles = pd.qcut(prices_clean, q=4, labels=['Q1 (lowest)', 'Q2', 'Q3', 'Q4 (highest)'])
    
    quartile_data_baseline = []
    quartile_data_net = []
    quartile_labels = []
    for q in ['Q1 (lowest)', 'Q2', 'Q3', 'Q4 (highest)']:
        mask = price_quartiles == q
        if mask.sum() > 0:
            quartile_data_baseline.append(baseline_clean[mask].values)
            quartile_data_net.append(net_clean[mask].values)
            quartile_labels.append(f'{q}\n(n={mask.sum()})')
    
    if quartile_data_baseline:
        x_pos = np.arange(len(quartile_labels))
        width = 0.35
        
        # Calculate means for bar plot
        baseline_means = [np.mean(d) for d in quartile_data_baseline]
        net_means = [np.mean(d) for d in quartile_data_net]
        baseline_stds = [np.std(d) for d in quartile_data_baseline]
        net_stds = [np.std(d) for d in quartile_data_net]
        
        ax3.bar(x_pos - width/2, baseline_means, width, yerr=baseline_stds, 
               label='Baseline', alpha=0.7, color='C2', capsize=5)
        ax3.bar(x_pos + width/2, net_means, width, yerr=net_stds, 
               label='Net (with DSR)', alpha=0.7, color='C1', capsize=5)
        
        ax3.set_ylabel("Average industry load (MW)")
        ax3.set_xlabel("Price quartile")
        ax3.set_xticks(x_pos)
        ax3.set_xticklabels(quartile_labels)
        ax3.set_title("Average Load by Price Quartile")
        ax3.legend()
        ax3.grid(True, alpha=0.3, axis='y')
    
    # Format x-axis for time series
    import matplotlib.dates as mdates
    ax2.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, (snapshots[-1] - snapshots[0]).days // 7)))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d\n%H:%M"))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    fig.suptitle(title or "Industry Load Response to Electricity Prices (with DSR)", fontsize=14, fontweight='bold')
    fig.tight_layout()
    
    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        fig.savefig(output_path, bbox_inches="tight", dpi=150)
        logger.info(f"Saved load-price correlation plot to {output_path}")
        logger.info(f"Baseline correlation: {corr_baseline:.3f} (p={p_baseline:.3f})")
        logger.info(f"Net load correlation: {corr_net:.3f} (p={p_net:.3f})")
        logger.info(f"Load shift correlation: {corr_shift:.3f} (p={p_shift:.3f})")
        logger.info(f"Expected: Net load should have weaker correlation than baseline (load shifted away from high prices)")
    
    return fig


if __name__ == "__main__":
    # Snakemake: use inputs/outputs from rule
    if "snakemake" in globals():
        network_path = snakemake.input.network
        output_path = getattr(snakemake.output, "plot", None) or (snakemake.output[0] if hasattr(snakemake.output, "__getitem__") else None)
        days = getattr(snakemake.params, "days", None)
        if days is not None and days == 0:
            days = None
        bus_carrier = getattr(snakemake.params, "bus_carrier", "AC")
        title = None
        configure_logging(snakemake)
    else:
        parser = argparse.ArgumentParser(description="Plot correlation between electricity prices and industry load")
        parser.add_argument("--network", required=True, help="Path to solved network with industry DSR")
        parser.add_argument("--output", "-o", default=None, help="Output figure path")
        parser.add_argument("--days", type=int, default=None, help="Number of days to plot (None = all)")
        parser.add_argument("--bus-carrier", default="AC", help="Bus carrier for prices (default: AC)")
        parser.add_argument("--title", default=None, help="Plot title")
        parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
        args = parser.parse_args()
        
        network_path = args.network
        output_path = args.output
        days = args.days
        bus_carrier = args.bus_carrier
        title = args.title
        configure_logging(verbose=args.verbose)
    
    n = pypsa.Network(network_path)
    
    plot_load_price_correlation(
        n,
        output_path=output_path,
        days=days,
        bus_carrier=bus_carrier,
        title=title,
    )
