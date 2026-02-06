#!/usr/bin/env python3
"""Check if DSR profile file exists and what it contains."""

import pandas as pd
import os

profile_path = "resources/Test_2030/industrial_dsr_profile_base_s_5_2030.csv"

print("=" * 80)
print("DSR PROFILE FILE CHECK")
print("=" * 80)

if os.path.exists(profile_path):
    print(f"\n✓ File exists: {profile_path}")
    df = pd.read_csv(profile_path, index_col=0, parse_dates=True)
    print(f"\n1. Profile shape: {df.shape}")
    print(f"   Snapshots: {len(df.index)}")
    print(f"   Profiles: {len(df.columns)}")
    print(f"   Profile names: {list(df.columns)}")
    
    print(f"\n2. Profile values:")
    print(f"   Unique values: {sorted(df.values.flatten())}")
    print(f"   Min: {df.values.min()}")
    print(f"   Max: {df.values.max()}")
    
    # Check for checkpoint hours (should be 0)
    zero_hours = (df == 0).sum()
    print(f"\n3. Checkpoint hours (where value = 0):")
    for profile in df.columns:
        zero_count = (df[profile] == 0).sum()
        total = len(df)
        print(f"   {profile}: {zero_count}/{total} hours ({zero_count/total*100:.1f}%)")
    
    # Check specific hours
    print(f"\n4. Sample values at key hours:")
    key_hours = [0, 6, 12, 18]
    for h in key_hours:
        if h < len(df):
            hour_vals = df.iloc[h]
            print(f"   Hour {h} ({df.index[h]}): {dict(hour_vals)}")
    
    # Check if all values are 1.0 (no checkpoints)
    if (df == 1.0).all().all():
        print(f"\n⚠️  WARNING: All values are 1.0! Checkpoint hours are NOT set to 0.")
        print(f"   This means the restriction_time config might not be working.")
else:
    print(f"\n✗ File does NOT exist: {profile_path}")
    print(f"   The DSR profile needs to be built first!")
    print(f"   Run: snakemake build_industry_dsr_profile --configfile config/test/config.industry.flex.yaml")

print("\n" + "=" * 80)
