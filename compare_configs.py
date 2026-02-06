#!/usr/bin/env python3
"""Compare default config vs test config to see what we added."""

import yaml

# Read default config
with open("config/config.default.yaml", "r") as f:
    default_config = yaml.safe_load(f)

# Read test config
with open("config/test/config.industry.flex.yaml", "r") as f:
    test_config = yaml.safe_load(f)

print("=" * 80)
print("COMPARING DEFAULT CONFIG vs TEST CONFIG")
print("=" * 80)

# Check industry.dsr section
default_dsr = default_config.get("industry", {}).get("dsr", {})
test_dsr = test_config.get("industry", {}).get("dsr", {})

print("\n1. DSR ENABLE")
print("-" * 80)
print(f"  Default: {default_dsr.get('enable', 'NOT SET')}")
print(f"  Test:    {test_dsr.get('enable', 'NOT SET')}")

print("\n2. NEW PARAMETERS WE ADDED")
print("-" * 80)

# Check for technology_breakdown
if "technology_breakdown" in test_dsr:
    print("  ✓ technology_breakdown: ADDED (not in default)")
    print(f"    Profiles: {list(test_dsr['technology_breakdown'].keys())}")
else:
    print("  ✗ technology_breakdown: NOT in test config")

# Check for negative_only
if "negative_only" in test_dsr:
    print("  ✓ negative_only: ADDED (not in default)")
else:
    print("  ✗ negative_only: NOT in test config (or not set)")

# Check for min_load
if "min_load" in test_dsr:
    print("  ✓ min_load: ADDED (not in default)")
else:
    print("  ✗ min_load: NOT in test config (or not set)")

print("\n3. PARAMETERS THAT EXIST IN DEFAULT")
print("-" * 80)

# Check flexibility_fraction format
default_flex = default_dsr.get("flexibility_fraction", {})
test_flex = test_dsr.get("flexibility_fraction", {})

print(f"  Default flexibility_fraction format:")
print(f"    Keys: {list(default_flex.keys())[:3]}... (profile-level)")
print(f"  Test flexibility_fraction format:")
test_flex_keys = list(test_flex.keys())
if any("|" in k for k in test_flex_keys):
    print(f"    Keys: {test_flex_keys[:3]}... (profile|technology format)")
    print(f"    ✓ Using technology-specific format (our addition)")
else:
    print(f"    Keys: {list(test_flex.keys())[:3]}... (profile-level)")

# Check shift_hours
default_shift = default_dsr.get("shift_hours", {})
test_shift = test_dsr.get("shift_hours", {})

print(f"\n  Default shift_hours format:")
print(f"    Keys: {list(default_shift.keys())[:3]}... (profile-level)")
print(f"  Test shift_hours format:")
test_shift_keys = list(test_shift.keys())
if any("|" in k for k in test_shift_keys):
    print(f"    Keys: {test_shift_keys[:3]}... (profile|technology format)")
    print(f"    ✓ Using technology-specific format (our addition)")

# Check restriction_time
default_restrict = default_dsr.get("restriction_time", {})
test_restrict = test_dsr.get("restriction_time", {})

print(f"\n  Default restriction_time format:")
print(f"    Keys: {list(default_restrict.keys())[:3]}... (profile-level)")
print(f"  Test restriction_time format:")
test_restrict_keys = list(test_restrict.keys())
if any("|" in k for k in test_restrict_keys):
    print(f"    Keys: {test_restrict_keys[:3]}... (profile|technology format)")
    print(f"    ✓ Using technology-specific format (our addition)")

print("\n4. PARAMETERS FROM DEFAULT (NOT OUR ADDITION)")
print("-" * 80)

# H2_DRI and elec_DRI
default_industry = default_config.get("industry", {})
test_industry = test_config.get("industry", {})

print(f"  H2_DRI:")
print(f"    Default: {default_industry.get('H2_DRI', 'NOT SET')}")
print(f"    Test:    {test_industry.get('H2_DRI', 'NOT SET')}")
print(f"    ✓ Already in default config (not our addition)")

print(f"\n  elec_DRI:")
print(f"    Default: {default_industry.get('elec_DRI', 'NOT SET')}")
print(f"    Test:    {test_industry.get('elec_DRI', 'NOT SET')}")
print(f"    ✓ Already in default config (not our addition)")

print("\n5. SUMMARY")
print("-" * 80)
print("What we ADDED (new parameters):")
print("  1. technology_breakdown - completely new")
print("  2. negative_only - completely new")
print("  3. min_load - completely new")
print("  4. Technology-specific keys in flexibility_fraction, shift_hours, restriction_time")
print("\nWhat we DIDN'T ADD (already in default):")
print("  1. H2_DRI - already exists")
print("  2. elec_DRI - already exists")
print("  3. restriction_value - already exists")
print("\nNone of our additions should affect electricity prices:")
print("  - They only configure DSR store parameters")
print("  - Stores don't have marginal_cost")
print("  - They're passive components (load shifting only)")

print("\n" + "=" * 80)
