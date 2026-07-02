"""
CBC Revenue Simulation - Wearable Monitoring Study
===================================================
Simulates all possible product profiles against a fixed competitive set
using respondent-level HB utilities and a logit share model.

INSTRUCTIONS:
    1. Fill in the two paths in the CONFIGURATION block below
    2. Run:  python cbc_revenue_simulation.py
"""

import pandas as pd
import numpy as np
from itertools import product
import os

# =============================================================================
# CONFIGURATION — fill in these two paths before running
# =============================================================================

# Full path to your HB utilities CSV exported from Lighthouse Studio
# Example (Windows): r"C:\Users\you\Data\Utilities.csv"
# Example (Mac/Linux): "/Users/you/Data/Utilities.csv"
INPUT_FILE = r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\10 June\Utilities - WearableMonitoringCBC - 375 Full Analysis - HB - 2026-Jun-09 - 9_14 AM - Zero-Centered Differences.csv"

# Full path to the folder where output CSVs should be saved
# Example (Windows): r"C:\Users\you\Results"
# Example (Mac/Linux): "/Users/you/Results"
OUTPUT_FOLDER = r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\10 June"

# =============================================================================
# ATTRIBUTE & LEVEL DEFINITIONS
# Keys must exactly match the column headers in the utilities CSV
# =============================================================================

ATTRIBUTES = {
    "Form Factor": [
        "Disposable chest patch",
        "Rechargeable chest patch (e.g., adhesive replaced, but device reused)",
        "Disposable wrist band",
        "Rechargeable wrist band (e.g., band replaced, but device reused)",
    ],
    "Vitals Monitored": [
        "HR, RR",
        "HR, RR, Temp",
        "HR, RR, SpO2",
        "HR, RR, Temp, SpO2",
    ],
    "Blood Pressure Monitoring": [
        "Not Included",
        "Included; Requires BP calibration with an arm cuff every 24 hours",
        "Included; Requires BP calibration with an arm cuff once at outset",
        "Included; Does not require BP calibration with an arm cuff",
    ],
    "ECG Monitoring": [
        "Not included",
        "Includes 1-lead ECG",
        "Includes 3-lead ECG",
    ],
    "Measure Frequency": [
        "Continuous",
        "Every 15 minutes",
        "Every 30 minutes",
        "Every 1 hour",
        "Every 4 hours",
    ],
    "Algo/AI-Based Alerts": [
        "Alerts based on preset rules/thresholds",
        "Alerts based on preset rules/thresholds with filtration system",
        "Predictive alerts via AI algorithm based on patient trends",
    ],
    "Price per patient": [50, 75, 100, 125, 150],
}

NONE_COL   = "NONE"
PRICE_ATTR = "Price per patient"

# =============================================================================
# COMPETITIVE SET
# =============================================================================

COMPETITORS = {
    "MVP": {
        "Form Factor": "Disposable chest patch",
        "Vitals Monitored": "HR, RR, Temp",
        "Blood Pressure Monitoring": "Not Included",
        "ECG Monitoring": "Not included",
        "Measure Frequency": "Every 15 minutes",
        "Algo/AI-Based Alerts": "Alerts based on preset rules/thresholds",
        "Price per patient": 50,
    },
    "Wearable Sensor without BP": {
        "Form Factor": "Disposable chest patch",
        "Vitals Monitored": "HR, RR, SpO2",
        "Blood Pressure Monitoring": "Not Included",
        "ECG Monitoring": "Includes 1-lead ECG",
        "Measure Frequency": "Every 15 minutes",
        "Algo/AI-Based Alerts": "Alerts based on preset rules/thresholds",
        "Price per patient": 75,
    },
    "Wearable Sensor with BP": {
        "Form Factor": "Disposable chest patch",
        "Vitals Monitored": "HR, RR, SpO2",
        "Blood Pressure Monitoring": "Included; Requires BP calibration with an arm cuff every 24 hours",
        "ECG Monitoring": "Includes 1-lead ECG",
        "Measure Frequency": "Every 15 minutes",
        "Algo/AI-Based Alerts": "Alerts based on preset rules/thresholds",
        "Price per patient": 100,
    },
}

# =============================================================================
# SIMULATION FUNCTIONS — no edits needed below this line
# =============================================================================

def validate_paths(input_file, output_folder):
    if not input_file:
        raise ValueError("INPUT_FILE is empty — please fill in the path at the top of the script.")
    if not output_folder:
        raise ValueError("OUTPUT_FOLDER is empty — please fill in the path at the top of the script.")
    if not os.path.isfile(input_file):
        raise FileNotFoundError(f"Input file not found:\n  {input_file}")
    os.makedirs(output_folder, exist_ok=True)


def load_utilities(filepath):
    df = pd.read_csv(filepath)
    df = df.set_index(df.columns[0])
    print(f"Loaded utilities for {len(df)} respondents, {len(df.columns)} columns.")
    return df


def profile_utility(profile_dict, utilities_df):
    total = pd.Series(0.0, index=utilities_df.index)
    for attr, level in profile_dict.items():
        col = str(level)
        if col not in utilities_df.columns:
            raise KeyError(
                f"Column '{col}' not found in utilities file.\n"
                f"Available columns: {list(utilities_df.columns)}"
            )
        total += utilities_df[col]
    return total


def simulate_shares(test_profiles_df, competitors_dict, utilities_df):
    comp_utils = [profile_utility(p, utilities_df).values for p in competitors_dict.values()]
    none_utils = utilities_df[NONE_COL].values if NONE_COL in utilities_df.columns else None

    denom_fixed = np.zeros(len(utilities_df))
    for cu in comp_utils:
        denom_fixed += np.exp(cu)
    if none_utils is not None:
        denom_fixed += np.exp(none_utils)

    n_profiles = len(test_profiles_df)
    print(f"\nSimulating {n_profiles:,} profiles against "
          f"{len(competitors_dict)} competitors + None option...")

    shares = []
    for i, (_, row) in enumerate(test_profiles_df.iterrows()):
        if i % 5000 == 0:
            print(f"  {i:,} / {n_profiles:,} profiles processed...")
        test_util = profile_utility(row.to_dict(), utilities_df).values
        exp_test  = np.exp(test_util)
        shares.append((exp_test / (denom_fixed + exp_test)).mean())

    print(f"  {n_profiles:,} / {n_profiles:,} profiles processed. Done.")
    return np.array(shares)


def generate_profiles(attributes_dict):
    keys   = list(attributes_dict.keys())
    values = list(attributes_dict.values())
    df     = pd.DataFrame(list(product(*values)), columns=keys)
    print(f"Generated {len(df):,} possible profiles.")
    return df


def main():
    validate_paths(INPUT_FILE, OUTPUT_FOLDER)
    print(f"\nInput  : {INPUT_FILE}")
    print(f"Output : {OUTPUT_FOLDER}\n")

    utilities_df = load_utilities(INPUT_FILE)
    profiles_df  = generate_profiles(ATTRIBUTES)
    shares       = simulate_shares(profiles_df, COMPETITORS, utilities_df)

    results = profiles_df.copy()
    results["Preference Share (%)"] = (shares * 100).round(2)
    results["Price"]                = results[PRICE_ATTR]
    results["Revenue Index"]        = (results["Preference Share (%)"] / 100 * results["Price"]).round(4)
    results = results.sort_values("Revenue Index", ascending=False).reset_index(drop=True)
    results.index += 1
    results.index.name = "Rank"

    out_all   = os.path.join(OUTPUT_FOLDER, "cbc_simulation_results.csv")
    out_top20 = os.path.join(OUTPUT_FOLDER, "cbc_top20_profiles.csv")
    results.to_csv(out_all)
    results.head(20).to_csv(out_top20)

    print(f"\nResults saved:")
    print(f"  All profiles : {out_all}")
    print(f"  Top 20       : {out_top20}")

    display_cols = list(ATTRIBUTES.keys()) + ["Preference Share (%)", "Price", "Revenue Index"]
    print("\n=== TOP 10 PROFILES BY REVENUE INDEX ===\n")
    print(results[display_cols].head(10).to_string())

    top_share   = results.sort_values("Preference Share (%)", ascending=False).iloc[0]
    top_revenue = results.iloc[0]
    print("\n=== KEY INSIGHT ===")
    print(f"Highest preference share: Rank {top_share.name}  |  "
          f"Share: {top_share['Preference Share (%)']:.2f}%  |  "
          f"Price: ${top_share['Price']}  |  Revenue Index: {top_share['Revenue Index']:.4f}")
    print(f"Highest revenue index:    Rank 1  |  "
          f"Share: {top_revenue['Preference Share (%)']:.2f}%  |  "
          f"Price: ${top_revenue['Price']}  |  Revenue Index: {top_revenue['Revenue Index']:.4f}")


if __name__ == "__main__":
    main()
