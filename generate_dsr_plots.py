#!/usr/bin/env python3
"""Generate both DSR visualization plots."""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set paths
network_path = "results/Test_2030/networks/base_s_5___2030.nc"
output_dir = "results/Test_2030/maps/static"
os.makedirs(output_dir, exist_ok=True)

comparison_output = os.path.join(output_dir, "base_s_5___2030-industry_dsr_comparison.pdf")
price_correlation_output = os.path.join(output_dir, "base_s_5___2030-industry_dsr_price_correlation.pdf")

print("=" * 80)
print("GENERATING DSR PLOTS")
print("=" * 80)

# Plot 1: DSR Comparison
print("\n1. Generating DSR comparison plot (baseline vs net demand)...")
try:
    from scripts.plot_industry_dsr_comparison import plot_industry_dsr_comparison
    import pypsa
    
    n = pypsa.Network(network_path)
    plot_industry_dsr_comparison(
        n,
        n_without_dsr=None,
        output_path=comparison_output,
        days=7,  # Show first week
        resample=None,
        title=None,
    )
    print(f"   ✓ Saved to: {comparison_output}")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Plot 2: Price-DSR Correlation
print("\n2. Generating price-DSR correlation plot...")
try:
    from scripts.plot_industry_dsr_price_correlation import plot_price_dsr_correlation
    import pypsa
    
    n = pypsa.Network(network_path)
    plot_price_dsr_correlation(
        n,
        output_path=price_correlation_output,
        days=7,  # Show first week
        bus_carrier="AC",
        title=None,
    )
    print(f"   ✓ Saved to: {price_correlation_output}")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("DONE!")
print("=" * 80)
print(f"\nPlots saved to:")
print(f"  - {comparison_output}")
print(f"  - {price_correlation_output}")
