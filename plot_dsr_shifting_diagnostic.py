#!/usr/bin/env python3
"""Enhanced diagnostic plot to check if DSR shifting is working correctly."""

import pandas as pd
import pypsa
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

network_path = "results/Test_2030/networks/base_s_5___2030.nc"

print("=" * 80)
print("DSR SHIFTING DIAGNOSTIC")
print("=" * 80)

# Load network
n = pypsa.Network(network_path)
print(f"\n✓ Network loaded: {network_path}")
print(f"   Snapshots: {len(n.snapshots)} ({n.snapshots[0]} to {n.snapshots[-1]})")

# Get industry loads
industry_loads = n.loads.index[n.loads.carrier.str.contains("industry electricity", case=False, na=False)]
if len(industry_loads) == 0:
    print("\n✗ No industry electricity loads found!")
    sys.exit(1)

baseline = n.loads_t.p_set[industry_loads].sum(axis=1)
print(f"\n✓ Found {len(industry_loads)} industry electricity loads")
print(f"   Baseline demand range: [{baseline.min():.2f}, {baseline.max():.2f}] MW")
print(f"   Baseline demand mean: {baseline.mean():.2f} MW")

# Get DSR store dispatch
industry_dsr_stores = n.stores.index[n.stores.carrier == "industry dsr"]
if len(industry_dsr_stores) == 0:
    print("\n✗ No industry DSR stores found!")
    sys.exit(1)

store_dispatch = n.stores_t.p[industry_dsr_stores].sum(axis=1)
print(f"\n✓ Found {len(industry_dsr_stores)} industry DSR stores")
print(f"   Store dispatch range: [{store_dispatch.min():.2f}, {store_dispatch.max():.2f}] MW")
print(f"   Store dispatch mean: {store_dispatch.mean():.2f} MW")

# Net demand
net = baseline + store_dispatch
print(f"\n   Net demand range: [{net.min():.2f}, {net.max():.2f}] MW")
print(f"   Net demand mean: {net.mean():.2f} MW")

# Calculate statistics
total_baseline = baseline.sum()
total_net = net.sum()
difference = total_net - total_baseline
max_increase = (net - baseline).max()
max_decrease = (net - baseline).min()

print(f"\n" + "=" * 80)
print("ENERGY BALANCE STATISTICS")
print("=" * 80)
print(f"\nTotal baseline energy: {total_baseline:.2f} MWh")
print(f"Total net energy: {total_net:.2f} MWh")
print(f"Difference: {difference:.2f} MWh (should be ~0 for energy-neutral shifting)")
print(f"\nMaximum increase: {max_increase:.2f} MW")
print(f"Maximum decrease: {max_decrease:.2f} MW")
print(f"Mean difference: {(net - baseline).mean():.2f} MW")

# Check if net is consistently higher
hours_increase = (net > baseline).sum()
hours_decrease = (net < baseline).sum()
hours_equal = (net == baseline).sum()

print(f"\nHours with increased demand: {hours_increase} ({hours_increase/len(net)*100:.1f}%)")
print(f"Hours with decreased demand: {hours_decrease} ({hours_decrease/len(net)*100:.1f}%)")
print(f"Hours with no change: {hours_equal} ({hours_equal/len(net)*100:.1f}%)")

# Check charging vs discharging
charging_hours = (store_dispatch > 0.1).sum()  # Small threshold to ignore near-zero
discharging_hours = (store_dispatch < -0.1).sum()
neutral_hours = len(store_dispatch) - charging_hours - discharging_hours

print(f"\nStore charging hours: {charging_hours} ({charging_hours/len(store_dispatch)*100:.1f}%)")
print(f"Store discharging hours: {discharging_hours} ({discharging_hours/len(store_dispatch)*100:.1f}%)")
print(f"Neutral hours: {neutral_hours} ({neutral_hours/len(store_dispatch)*100:.1f}%)")

total_charging = store_dispatch[store_dispatch > 0].sum()
total_discharging = abs(store_dispatch[store_dispatch < 0].sum())
print(f"\nTotal charging energy: {total_charging:.2f} MWh")
print(f"Total discharging energy: {total_discharging:.2f} MWh")
print(f"Balance: {total_charging - total_discharging:.2f} MWh (should be ~0)")

# Create comprehensive plot
fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)

snapshots = n.snapshots
days_to_show = min(7, len(snapshots) // 24)
if days_to_show > 0:
    snapshots_to_plot = snapshots[:days_to_show*24]
else:
    snapshots_to_plot = snapshots

baseline_plot = baseline.loc[snapshots_to_plot]
net_plot = net.loc[snapshots_to_plot]
dispatch_plot = store_dispatch.loc[snapshots_to_plot]
difference_plot = (net_plot - baseline_plot)

# Plot 1: Baseline vs Net Demand
ax0 = axes[0]
ax0.fill_between(snapshots_to_plot, 0, baseline_plot.values, alpha=0.2, label="Baseline (fixed load)", color="C0")
ax0.plot(snapshots_to_plot, baseline_plot.values, color="C0", linewidth=2, linestyle="--", alpha=0.7, label="Baseline")
ax0.plot(snapshots_to_plot, net_plot.values, color="C1", linewidth=2, label="Net demand (with DSR)")
ax0.fill_between(snapshots_to_plot, baseline_plot.values, net_plot.values, 
                 where=(difference_plot > 0), alpha=0.4, color="C3", label="DSR increase")
ax0.fill_between(snapshots_to_plot, baseline_plot.values, net_plot.values, 
                 where=(difference_plot < 0), alpha=0.4, color="C2", label="DSR decrease")
ax0.set_ylabel("Industry electricity demand (MW)")
ax0.legend(loc="upper right", fontsize=9)
ax0.set_title("Industry Electricity Demand: Baseline vs Net (with DSR)", fontweight='bold')
ax0.grid(True, alpha=0.3)

# Plot 2: Store Dispatch
ax1 = axes[1]
ax1.fill_between(snapshots_to_plot, 0, dispatch_plot.values, 
                 where=(dispatch_plot > 0), alpha=0.5, color="C3", label="Charging (increasing demand)")
ax1.fill_between(snapshots_to_plot, 0, dispatch_plot.values, 
                 where=(dispatch_plot < 0), alpha=0.5, color="C2", label="Discharging (decreasing demand)")
ax1.plot(snapshots_to_plot, dispatch_plot.values, color="black", linewidth=1.5, alpha=0.8)
ax1.axhline(0, color='k', linestyle='--', linewidth=0.5)
ax1.set_ylabel("DSR Store Dispatch (MW)")
ax1.legend(loc="upper right", fontsize=9)
ax1.set_title("DSR Store Dispatch (Positive = Charging/Over-consumption, Negative = Discharging/Under-consumption)", fontweight='bold')
ax1.grid(True, alpha=0.3)

# Plot 3: Difference (Net - Baseline)
ax2 = axes[2]
ax2.fill_between(snapshots_to_plot, 0, difference_plot.values, 
                 where=(difference_plot > 0), alpha=0.5, color="C3", label="Increase")
ax2.fill_between(snapshots_to_plot, 0, difference_plot.values, 
                 where=(difference_plot < 0), alpha=0.5, color="C2", label="Decrease")
ax2.plot(snapshots_to_plot, difference_plot.values, color="black", linewidth=1.5, alpha=0.8)
ax2.axhline(0, color='k', linestyle='--', linewidth=0.5)
ax2.set_ylabel("Net - Baseline (MW)")
ax2.legend(loc="upper right", fontsize=9)
ax2.set_title("Load Shift (Net Demand - Baseline Demand)", fontweight='bold')
ax2.grid(True, alpha=0.3)

# Plot 4: Cumulative Energy Balance
ax3 = axes[3]
cumulative_dispatch = dispatch_plot.cumsum()
ax3.plot(snapshots_to_plot, cumulative_dispatch.values, color="C4", linewidth=2, label="Cumulative DSR dispatch")
ax3.axhline(0, color='k', linestyle='--', linewidth=0.5)
ax3.set_ylabel("Cumulative Energy (MWh)")
ax3.set_xlabel("Time")
ax3.legend(loc="upper right", fontsize=9)
ax3.set_title("Cumulative DSR Energy Balance (should return to ~0 at end if balanced)", fontweight='bold')
ax3.grid(True, alpha=0.3)

# Format x-axis
for ax in axes:
    if len(snapshots_to_plot) > 0:
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d\n%H:%M"))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

fig.suptitle(f"DSR Shifting Diagnostic - First {days_to_show} Days\n"
             f"Total Energy Difference: {difference:.2f} MWh | "
             f"Max Increase: {max_increase:.2f} MW | "
             f"Max Decrease: {max_decrease:.2f} MW", 
             fontsize=12, fontweight='bold', y=0.995)

fig.tight_layout()

# Save plot
output_path = "results/Test_2030/maps/static/base_s_5___2030-dsr_shifting_diagnostic.pdf"
os.makedirs(os.path.dirname(output_path), exist_ok=True)
fig.savefig(output_path, bbox_inches="tight", dpi=150)
print(f"\n✓ Plot saved to: {output_path}")

# Print summary
print("\n" + "=" * 80)
print("DIAGNOSTIC SUMMARY")
print("=" * 80)

if abs(difference) < 1.0:
    print("\n✓ Energy balance: GOOD (total difference < 1 MWh)")
else:
    print(f"\n⚠️  Energy balance: WARNING (total difference = {difference:.2f} MWh)")

if hours_increase > 0 and hours_decrease > 0:
    print("✓ Shifting behavior: GOOD (both increases and decreases present)")
elif hours_increase > 0 and hours_decrease == 0:
    print("✗ Shifting behavior: BAD (only increases, no decreases - overconsumption only)")
elif hours_increase == 0 and hours_decrease > 0:
    print("✗ Shifting behavior: BAD (only decreases, no increases - underconsumption only)")
else:
    print("✗ Shifting behavior: BAD (no shifting at all)")

if abs(total_charging - total_discharging) < 1.0:
    print("✓ Store balance: GOOD (charging ≈ discharging)")
else:
    print(f"⚠️  Store balance: WARNING (difference = {total_charging - total_discharging:.2f} MWh)")

print("\n" + "=" * 80)

plt.close()
