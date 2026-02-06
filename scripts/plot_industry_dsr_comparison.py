# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Plot industry electricity demand with vs without DSR to visualize load shifting.

Loads one or two solved networks and plots:
- Baseline industry electricity demand (fixed Load p_set)
- Net industry demand with DSR (baseline + industry DSR Store dispatch)
- Optionally: comparison with a second network run without DSR

Usage (standalone):
  python scripts/plot_industry_dsr_comparison.py --network-with-dsr path/to/network_with_dsr.nc [--network-without-dsr path/to/network_without_dsr.nc] [--output path/to/plot.pdf] [--days 14]

Or via Snakemake (see rule in rules/build_sector.smk or postprocess.smk).
"""

import argparse
import logging
import os

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import pypsa

from scripts._helpers import configure_logging

logger = logging.getLogger(__name__)

INDUSTRY_LOAD_CARRIER = "industry electricity"
INDUSTRY_DSR_CARRIER = "industry dsr"


def get_industry_baseline_and_net(n):
    """
    Get baseline industry electricity demand (MW) and net demand including DSR store dispatch.

    Parameters
    ----------
    n : pypsa.Network
        Solved network (must have been solved so stores_t.p is available if DSR present).

    Returns
    -------
    baseline : pd.Series
        Total industry electricity load (MW) per snapshot (index = n.snapshots).
    net : pd.Series
        Baseline + industry DSR store power (MW). When store charges, net > baseline; when it discharges, net < baseline.
    store_dispatch : pd.Series or None
        Sum of industry DSR store power (MW). None if no industry DSR stores.
    """
    # Industry electricity loads (carrier "industry electricity")
    industry_loads = n.loads.index[n.loads.carrier == INDUSTRY_LOAD_CARRIER]
    if industry_loads.empty:
        logger.warning("No industry electricity loads found in network.")
        baseline = pd.Series(0.0, index=n.snapshots)
    else:
        # Use p_set (baseline); after solve loads_t.p equals p_set for inelastic loads
        baseline = n.loads_t.p_set[industry_loads].reindex(n.snapshots).fillna(0).sum(axis=1)

    # Industry DSR stores (carrier "industry dsr")
    industry_stores = n.stores.index[n.stores.carrier == INDUSTRY_DSR_CARRIER]
    if industry_stores.empty:
        store_dispatch = None
        net = baseline
    else:
        # stores_t.p: positive = charging (drawing from bus = more demand)
        store_dispatch = n.stores_t.p[industry_stores].reindex(n.snapshots).fillna(0).sum(axis=1)
        net = baseline + store_dispatch

    return baseline, net, store_dispatch


def plot_industry_dsr_comparison(
    n_with_dsr,
    n_without_dsr=None,
    output_path=None,
    days=14,
    resample=None,
    title=None,
):
    """
    Plot industry electricity demand: baseline vs net (with DSR) and optionally vs no-DSR run.

    Parameters
    ----------
    n_with_dsr : pypsa.Network
        Solved network with industry DSR enabled.
    n_without_dsr : pypsa.Network or None
        If provided, solved network with industry DSR disabled (same scenario). Used for comparison line.
    output_path : str or None
        If set, save figure to this path.
    days : int
        Number of days to show (from start of snapshot index). Use 0 or None for full horizon.
    resample : str or None
        Pandas resample rule, e.g. "2h" or "D" for daily. None = hourly.
    title : str or None
        Plot title.
    """
    baseline, net, store_dispatch = get_industry_baseline_and_net(n_with_dsr)

    snapshots = n_with_dsr.snapshots
    if days and days > 0:
        snapshots = snapshots[: min(days * 24, len(snapshots))]
    baseline = baseline.reindex(snapshots).ffill().bfill()
    net = net.reindex(snapshots).ffill().bfill()
    if store_dispatch is not None:
        store_dispatch = store_dispatch.reindex(snapshots).ffill().bfill()

    if resample:
        baseline = baseline.resample(resample).mean().dropna()
        net = net.resample(resample).mean().dropna()
        if store_dispatch is not None:
            store_dispatch = store_dispatch.resample(resample).mean().dropna()
        snapshots = baseline.index

    fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True)

    # Top: baseline vs net demand (with DSR)
    ax0 = axes[0]
    ax0.fill_between(snapshots, 0, baseline.values, alpha=0.3, label="Baseline (fixed load)", color="C0")
    ax0.plot(snapshots, baseline.values, color="C0", linewidth=2, linestyle="--", alpha=0.7, label="Baseline (line)")
    ax0.plot(snapshots, net.values, color="C1", linewidth=2, label="Net demand (with DSR shift)")
    if n_without_dsr is not None:
        _, net_no_dsr, _ = get_industry_baseline_and_net(n_without_dsr)
        net_no_dsr = net_no_dsr.reindex(n_with_dsr.snapshots).ffill().bfill()
        if resample:
            net_no_dsr = net_no_dsr.resample(resample).mean().dropna()
        net_no_dsr = net_no_dsr.reindex(snapshots).ffill().bfill()
        ax0.plot(snapshots, net_no_dsr.values, color="C2", linestyle="--", linewidth=1, label="Without DSR (fixed)")
    
    # Add difference shading to make it more visible
    difference = net.values - baseline.values
    ax0.fill_between(snapshots, baseline.values, net.values, where=(difference > 0), 
                     alpha=0.4, color="C3", label="DSR increase")
    ax0.fill_between(snapshots, baseline.values, net.values, where=(difference < 0), 
                     alpha=0.4, color="C2", label="DSR decrease")
    
    ax0.set_ylabel("Industry electricity demand (MW)")
    ax0.legend(loc="upper right", fontsize=9)
    ax0.set_title(title or "Industry electricity: baseline vs with DSR")
    ax0.grid(True, alpha=0.3)

    # Bottom: DSR store dispatch (shift)
    ax1 = axes[1]
    if store_dispatch is not None:
        ax1.fill_between(snapshots, 0, store_dispatch.values, alpha=0.6, color="C3", label="Industry DSR store dispatch")
        ax1.axhline(0, color="k", linewidth=0.5)
        ax1.set_ylabel("Store power (MW)\n(>0 = charge = extra demand)")
    else:
        ax1.text(0.5, 0.5, "No industry DSR stores in this network", ha="center", va="center", transform=ax1.transAxes)
    ax1.set_xlabel("Time")
    ax1.legend(loc="upper right")
    ax1.grid(True, alpha=0.3)

    ax0.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, (snapshots[-1] - snapshots[0]).days // 7)))
    ax0.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d\n%H:%M"))
    fig.tight_layout()

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        fig.savefig(output_path, bbox_inches="tight")
        logger.info(f"Saved industry DSR comparison plot to {output_path}")
    return fig


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot industry electricity with vs without DSR")
    parser.add_argument("--network-with-dsr", default=None, help="Path to solved network with industry DSR enabled")
    parser.add_argument("--network-without-dsr", default=None, help="Path to solved network without industry DSR (optional)")
    parser.add_argument("--output", "-o", default=None, help="Output figure path (e.g. .pdf or .png)")
    parser.add_argument("--days", type=int, default=14, help="Number of days to plot (default 14); 0 = full horizon")
    parser.add_argument("--resample", default=None, help="Resample rule, e.g. 2h or D (optional)")
    parser.add_argument("--title", default=None, help="Plot title (optional)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    # Snakemake: use inputs/outputs from rule
    if "snakemake" in globals():
        network_with_dsr = snakemake.input.network
        network_without_dsr = getattr(snakemake.input, "network_without_dsr", None)
        if isinstance(network_without_dsr, list):
            network_without_dsr = network_without_dsr[0] if network_without_dsr else None
        output_path = getattr(snakemake.output, "plot", None) or (snakemake.output[0] if hasattr(snakemake.output, "__getitem__") else None)
        days = int(getattr(snakemake.params, "days", 14))
        configure_logging(snakemake)
    else:
        network_with_dsr = args.network_with_dsr
        network_without_dsr = args.network_without_dsr
        output_path = args.output
        days = args.days
        configure_logging(verbose=args.verbose)

    if not network_with_dsr:
        raise SystemExit("Provide --network-with-dsr or run via Snakemake")

    n_with_dsr = pypsa.Network(network_with_dsr)
    n_without_dsr = None
    if network_without_dsr and os.path.isfile(network_without_dsr):
        n_without_dsr = pypsa.Network(network_without_dsr)

    plot_industry_dsr_comparison(
        n_with_dsr,
        n_without_dsr=n_without_dsr,
        output_path=output_path,
        days=days if days > 0 else None,
        resample=args.resample,
        title=args.title,
    )
    if output_path:
        plt.close()
    else:
        plt.show()
