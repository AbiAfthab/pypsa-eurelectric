# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Plot correlation between electricity prices and industry DSR dispatch.

Shows how industry DSR responds to price signals:
- Negative correlation: stores discharge (reduce demand) when prices are high
- Positive correlation: stores charge (increase demand) when prices are low
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

INDUSTRY_DSR_CARRIER = "industry dsr"


def get_bus_prices(n, bus_carrier="AC"):
    """
    Get electricity prices from buses (marginal prices or shadow prices).
    
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
    
    # Get marginal prices (shadow prices of power balance constraint)
    # In PyPSA, this is stored in buses_t.marginal_price
    if hasattr(n.buses_t, 'marginal_price'):
        prices = n.buses_t.marginal_price[buses]
    else:
        # Fallback: try to get from bus balance constraint shadow prices
        # This might not be available depending on PyPSA version
        logger.warning("marginal_price not available, trying alternative method")
        # Try to get from dual values if available
        try:
            # For newer PyPSA versions, prices might be in different location
            prices = pd.DataFrame(index=n.snapshots, columns=buses, dtype=float)
            for bus in buses:
                # Try to get price from network results
                if hasattr(n, 'results') and hasattr(n.results, 'Buses'):
                    # This is version-dependent
                    pass
        except:
            pass
        
        # If we can't get prices, return NaN series
        return pd.Series(np.nan, index=n.snapshots)
    
    # Average across all buses (or use specific bus if only one)
    if len(buses) == 1:
        price_series = prices.iloc[:, 0]
    else:
        # Weight by load or just average
        price_series = prices.mean(axis=1)
    
    return price_series


def get_industry_dsr_dispatch(n):
    """
    Get total industry DSR store dispatch.
    
    Parameters
    ----------
    n : pypsa.Network
        Solved network
    
    Returns
    -------
    pd.Series
        Total industry DSR store power (MW) per snapshot
        Positive = charging (increasing demand)
        Negative = discharging (decreasing demand)
    """
    industry_stores = n.stores.index[n.stores.carrier == INDUSTRY_DSR_CARRIER]
    if industry_stores.empty:
        logger.warning("No industry DSR stores found")
        return pd.Series(0.0, index=n.snapshots)
    
    store_dispatch = n.stores_t.p[industry_stores].sum(axis=1)
    return store_dispatch


def plot_price_dsr_correlation(
    n,
    output_path=None,
    days=None,
    bus_carrier="AC",
    title=None,
):
    """
    Plot correlation between electricity prices and industry DSR dispatch.
    
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
    # Get prices and DSR dispatch
    prices = get_bus_prices(n, bus_carrier=bus_carrier)
    dsr_dispatch = get_industry_dsr_dispatch(n)
    
    # Align indices
    common_snapshots = prices.index.intersection(dsr_dispatch.index)
    prices = prices.reindex(common_snapshots)
    dsr_dispatch = dsr_dispatch.reindex(common_snapshots)
    
    # Filter by days if specified
    if days and days > 0:
        max_snapshots = min(days * 24, len(common_snapshots))
        prices = prices.iloc[:max_snapshots]
        dsr_dispatch = dsr_dispatch.iloc[:max_snapshots]
        snapshots = prices.index
    else:
        snapshots = prices.index
    
    # Remove NaN values for correlation
    valid_mask = ~(prices.isna() | dsr_dispatch.isna())
    prices_clean = prices[valid_mask]
    dsr_clean = dsr_dispatch[valid_mask]
    
    if len(prices_clean) == 0:
        logger.error("No valid price data found")
        return None
    
    # Calculate correlation
    correlation, p_value = stats.pearsonr(prices_clean.values, dsr_clean.values)
    
    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Top left: Scatter plot
    ax0 = axes[0, 0]
    scatter = ax0.scatter(prices_clean, dsr_clean, alpha=0.6, s=20, c=range(len(prices_clean)), cmap='viridis')
    ax0.set_xlabel("Electricity price (EUR/MWh)")
    ax0.set_ylabel("Industry DSR dispatch (MW)\n(>0 = charge, <0 = discharge)")
    ax0.set_title(f"Price vs DSR Dispatch\nCorrelation: {correlation:.3f} (p={p_value:.3f})")
    ax0.grid(True, alpha=0.3)
    ax0.axhline(0, color='k', linestyle='--', linewidth=0.5)
    ax0.axvline(prices_clean.mean(), color='r', linestyle='--', linewidth=0.5, alpha=0.5, label=f'Mean price: {prices_clean.mean():.2f}')
    ax0.legend()
    
    # Add trend line
    if len(prices_clean) > 1:
        z = np.polyfit(prices_clean.values, dsr_clean.values, 1)
        p = np.poly1d(z)
        x_trend = np.linspace(prices_clean.min(), prices_clean.max(), 100)
        ax0.plot(x_trend, p(x_trend), "r--", alpha=0.8, linewidth=2, label=f'Trend: y={z[0]:.2f}x+{z[1]:.2f}')
        ax0.legend()
    
    # Top right: Time series overlay
    ax1 = axes[0, 1]
    ax1_twin = ax1.twinx()
    
    line1 = ax1.plot(snapshots, prices, color='C0', linewidth=1.5, label='Price', alpha=0.7)
    line2 = ax1_twin.plot(snapshots, dsr_dispatch, color='C1', linewidth=1.5, label='DSR dispatch', alpha=0.7)
    
    ax1.set_xlabel("Time")
    ax1.set_ylabel("Electricity price (EUR/MWh)", color='C0')
    ax1_twin.set_ylabel("DSR dispatch (MW)", color='C1')
    ax1.set_title("Price and DSR Dispatch Over Time")
    ax1.tick_params(axis='y', labelcolor='C0')
    ax1_twin.tick_params(axis='y', labelcolor='C1')
    ax1.grid(True, alpha=0.3)
    
    # Combine legends
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left')
    
    # Bottom left: Price distribution by DSR state
    ax2 = axes[1, 0]
    charging_mask = dsr_clean > 0
    discharging_mask = dsr_clean < 0
    neutral_mask = dsr_clean.abs() < 0.01  # Very small values
    
    if charging_mask.sum() > 0:
        ax2.hist(prices_clean[charging_mask], bins=30, alpha=0.6, label=f'Charging (n={charging_mask.sum()})', color='C3', density=True)
    if discharging_mask.sum() > 0:
        ax2.hist(prices_clean[discharging_mask], bins=30, alpha=0.6, label=f'Discharging (n={discharging_mask.sum()})', color='C2', density=True)
    
    ax2.set_xlabel("Electricity price (EUR/MWh)")
    ax2.set_ylabel("Density")
    ax2.set_title("Price Distribution: Charging vs Discharging")
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Bottom right: DSR dispatch distribution by price quartiles
    ax3 = axes[1, 1]
    price_quartiles = pd.qcut(prices_clean, q=4, labels=['Q1 (lowest)', 'Q2', 'Q3', 'Q4 (highest)'])
    
    quartile_data = []
    quartile_labels = []
    for q in ['Q1 (lowest)', 'Q2', 'Q3', 'Q4 (highest)']:
        mask = price_quartiles == q
        if mask.sum() > 0:
            quartile_data.append(dsr_clean[mask].values)
            quartile_labels.append(f'{q}\n(n={mask.sum()})')
    
    if quartile_data:
        bp = ax3.boxplot(quartile_data, labels=quartile_labels, patch_artist=True)
        for patch in bp['boxes']:
            patch.set_facecolor('lightblue')
            patch.set_alpha(0.7)
        ax3.axhline(0, color='k', linestyle='--', linewidth=0.5)
        ax3.set_ylabel("DSR dispatch (MW)")
        ax3.set_xlabel("Price quartile")
        ax3.set_title("DSR Dispatch by Price Quartile")
        ax3.grid(True, alpha=0.3, axis='y')
    
    # Format x-axis for time series
    import matplotlib.dates as mdates
    for ax in [ax1]:
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, (snapshots[-1] - snapshots[0]).days // 7)))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d\n%H:%M"))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    fig.suptitle(title or "Industry DSR Response to Electricity Prices", fontsize=14, fontweight='bold')
    fig.tight_layout()
    
    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        fig.savefig(output_path, bbox_inches="tight", dpi=150)
        logger.info(f"Saved price-DSR correlation plot to {output_path}")
        logger.info(f"Correlation coefficient: {correlation:.3f} (p-value: {p_value:.3f})")
        logger.info(f"Expected negative correlation: DSR should discharge (negative) when prices are high")
    
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
        parser = argparse.ArgumentParser(description="Plot correlation between electricity prices and industry DSR")
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
    
    plot_price_dsr_correlation(
        n,
        output_path=output_path,
        days=days,
        bus_carrier=bus_carrier,
        title=title,
    )
