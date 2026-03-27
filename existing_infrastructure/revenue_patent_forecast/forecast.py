import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

FORECAST_END_YEAR = 2036

PATENT_EXPIRY_MULTIPLIERS = [
    0.834935,   # Year 1 post-expiry
    0.751169,   # Year 2
    0.689221,   # Year 3
    0.635714,   # Year 4
    0.579351,   # Year 5
    0.522078,   # Year 6
    0.472987,   # Year 7
    0.408052,   # Year 8+ (held constant beyond this point)
]


# ── 1. GROUP DATA BY INDICATION ───────────────────────────────────────────────

def group_by_indication(df):
    indication_groups = {}
    for indication, group in df.groupby('Indication_Group'):
        indication_groups[indication] = group.copy()

    print("Indication groups found in dataset:")
    for ind, grp in indication_groups.items():
        drugs = grp['Drug'].nunique()
        print(f"  {ind}: {drugs} drug(s)")

    return indication_groups


# ── 2. BUILD AVERAGE TRAJECTORY ───────────────────────────────────────────────

def build_indication_trajectory(indication_groups, indication):
    if indication not in indication_groups:
        print(f"Indication '{indication}' not found.")
        print(f"Available: {list(indication_groups.keys())}")
        return None

    group = indication_groups[indication]
    all_trajectories = []

    for drug, drug_data in group.groupby('Drug'):
        drug_data = drug_data.sort_values('year')
        drug_data = drug_data[
            drug_data['revenue_usd'].notna() & (drug_data['revenue_usd'] > 0)
        ].copy()

        if len(drug_data) < 2:
            continue

        drug_data['year_since_launch'] = range(1, len(drug_data) + 1)
        drug_data['drug'] = drug
        all_trajectories.append(drug_data[['drug', 'year_since_launch', 'revenue_usd']])

    if not all_trajectories:
        print(f"No valid revenue data found for: {indication}")
        return None

    combined = pd.concat(all_trajectories)
    avg_trajectory = (
        combined
        .groupby('year_since_launch')['revenue_usd']
        .agg(['mean', 'std', 'count'])
        .rename(columns={'mean': 'avg_revenue_usd', 'std': 'std_revenue_usd', 'count': 'drug_count'})
        .reset_index()
    )

    print(f"\nTrajectory for '{indication}' built from {combined['drug'].nunique()} drug(s).")
    return avg_trajectory


# ── 3. COMPUTE YEAR-ON-YEAR GROWTH RATES ─────────────────────────────────────

def compute_indication_growth_rates(avg_trajectory, max_years):
    revenues = avg_trajectory['avg_revenue_usd'].values
    years    = avg_trajectory['year_since_launch'].values.astype(int)

    growth_rates = {}
    for i in range(1, len(revenues)):
        if revenues[i - 1] > 0:
            rate = (revenues[i] - revenues[i - 1]) / revenues[i - 1]
            growth_rates[years[i - 1]] = rate

    if growth_rates:
        last_year = max(growth_rates.keys())
        last_rate = growth_rates[last_year]
    else:
        last_year = 1
        last_rate = 0.0

    for yr in range(last_year + 1, max_years + 1):
        growth_rates[yr] = last_rate

    return growth_rates


# ── 4. APPLY PATENT EXPIRY MULTIPLIERS ───────────────────────────────────────

def apply_patent_expiry(forecast_df, patent_expiry_year):
    """
    Adjusts forecast revenues after patent expiry.

    Logic:
      - The revenue in patent_expiry_year is taken as the base value.
      - Each subsequent year's revenue = base_revenue x multiplier[years_since_expiry - 1]
      - e.g. if patent expires in 2028 at $1,000m:
            2029 = 1000 x 0.834935 = $835m
            2030 = 1000 x 0.751169 = $751m  (NOT 835 x 0.751)
            2031 = 1000 x 0.689221 = $689m
      - Beyond year 8, the floor multiplier (0.408) is held constant.
      - Years up to and including patent_expiry_year are unaffected.

    Args:
        forecast_df:         DataFrame with 'calendar_year' and 'predicted_revenue_usd'
        patent_expiry_year:  int or None

    Returns:
        DataFrame with 'revenue_post_expiry_usd' column added.
    """
    df = forecast_df.copy()
    df['revenue_post_expiry_usd'] = df['predicted_revenue_usd']

    if patent_expiry_year is None:
        print("\nNo patent expiry year provided — skipping patent expiry adjustment.")
        return df

    # Find the base revenue: what the drug earned in the patent expiry year
    expiry_row = df[df['calendar_year'] == patent_expiry_year]

    if expiry_row.empty:
        print(f"\n⚠️  Patent expiry year {patent_expiry_year} is outside the forecast window. "
              f"Forecast runs {int(df['calendar_year'].min())}–{int(df['calendar_year'].max())}.")
        return df

    base_revenue = expiry_row['predicted_revenue_usd'].values[0]
    floor        = PATENT_EXPIRY_MULTIPLIERS[-1]

    print(f"\nPatent expiry adjustment:")
    print(f"  Expiry year : {patent_expiry_year}")
    print(f"  Base revenue (expiry year): ${base_revenue:,.2f}m")
    print(f"\n  {'Calendar Year':<16} {'Pre-Expiry Revenue':>20} {'Multiplier':>12} {'Adjusted Revenue':>18}")
    print(f"  {'-'*68}")

    for idx, row in df.iterrows():
        years_since_expiry = int(row['calendar_year']) - patent_expiry_year

        if years_since_expiry <= 0:
            # Expiry year and earlier: no change
            df.at[idx, 'revenue_post_expiry_usd'] = row['predicted_revenue_usd']
            if years_since_expiry == 0:
                print(f"  {int(row['calendar_year']):<16} {row['predicted_revenue_usd']:>20.2f} "
                      f"{'(expiry year)':>12} {row['predicted_revenue_usd']:>18.2f}")

        elif years_since_expiry <= len(PATENT_EXPIRY_MULTIPLIERS):
            multiplier = PATENT_EXPIRY_MULTIPLIERS[years_since_expiry - 1]
            adjusted   = base_revenue * multiplier
            df.at[idx, 'revenue_post_expiry_usd'] = adjusted
            print(f"  {int(row['calendar_year']):<16} {row['predicted_revenue_usd']:>20.2f} "
                  f"{multiplier:>12.6f} {adjusted:>18.2f}")

        else:
            # Beyond year 8: hold at floor
            adjusted = base_revenue * floor
            df.at[idx, 'revenue_post_expiry_usd'] = adjusted
            print(f"  {int(row['calendar_year']):<16} {row['predicted_revenue_usd']:>20.2f} "
                  f"{floor:>10.6f}* {adjusted:>18.2f}")

    print(f"\n  * Floor multiplier held constant beyond year 8 post-expiry.")
    return df


# ── 5. MAIN PREDICTION FUNCTION ───────────────────────────────────────────────

def predict_revenue(indication, launch_year, known_revenues, indication_groups,
                    patent_expiry_year=None, forecast_end_year=FORECAST_END_YEAR):
    """
    Args:
        indication:          string — must match a key in indication_groups
        launch_year:         int    — calendar year the drug was launched
        known_revenues:      dict   — {year_number: revenue_usd_millions},
                                      consecutive from year 1, treated as ground truth
        indication_groups:   dict   — output of group_by_indication()
        patent_expiry_year:  int or None — calendar year the patent expires
        forecast_end_year:   int    — last year of forecast (default 2036)
    """
    total_years = forecast_end_year - launch_year + 1

    if total_years <= 0:
        raise ValueError(f"launch_year ({launch_year}) must be before {forecast_end_year}.")

    print(f"\n{'='*60}")
    print(f"  Indication     : {indication}")
    print(f"  Launch year    : {launch_year}")
    print(f"  Patent expiry  : {patent_expiry_year if patent_expiry_year else 'Not provided'}")
    print(f"  Forecast       : {launch_year} → {forecast_end_year} ({total_years} years)")
    print(f"  Known revenues : {known_revenues}")
    print(f"{'='*60}")

    # Step 1: Build average trajectory
    avg_trajectory = build_indication_trajectory(indication_groups, indication)
    if avg_trajectory is None:
        return None

    # Step 2: Extract growth rates
    growth_rates = compute_indication_growth_rates(avg_trajectory, total_years)

    # Step 3: Establish extrapolation start point
    if known_revenues:
        last_known_year    = max(known_revenues.keys())
        last_known_revenue = known_revenues[last_known_year]
    else:
        last_known_year    = 0
        last_known_revenue = avg_trajectory['avg_revenue_usd'].iloc[0]
        print("\nNo known revenues — using indication average year 1 as starting point.")

    # Step 4: Build pre-expiry forecast
    results = []
    for yr_num in range(1, total_years + 1):
        calendar_year = launch_year + yr_num - 1

        if yr_num in known_revenues:
            revenue  = known_revenues[yr_num]
            is_known = True
        else:
            years_beyond = yr_num - last_known_year
            revenue = last_known_revenue
            for step in range(years_beyond):
                rate_lookup_year = last_known_year + step
                rate = growth_rates.get(rate_lookup_year, growth_rates[max(growth_rates.keys())])
                revenue = revenue * (1 + rate)
            revenue  = max(revenue, 0)
            is_known = False

        results.append({
            'year_since_launch'     : yr_num,
            'calendar_year'         : calendar_year,
            'predicted_revenue_usd' : round(revenue, 2),
            'is_known_datapoint'    : is_known
        })

    forecast_df = pd.DataFrame(results)

    # Step 5: Apply patent expiry
    forecast_df = apply_patent_expiry(forecast_df, patent_expiry_year)

    # Step 6: Plot
    plot_forecast(forecast_df, indication, launch_year, known_revenues,
                  patent_expiry_year, forecast_end_year)

    return forecast_df


# ── 6. PLOT ───────────────────────────────────────────────────────────────────

def plot_forecast(forecast_df, indication, launch_year, known_revenues,
                  patent_expiry_year, forecast_end_year):
    """
    Plots a single clean revenue line (post-expiry adjusted where applicable).
    Removed: pre-expiry dashed line, patent expiry impact shading.
    Kept:    extrapolation begins marker, patent expiry year marker.
    """
    known = forecast_df[forecast_df['is_known_datapoint']]
    fig, ax = plt.subplots(figsize=(13, 6))

    # Single revenue line — post-expiry adjusted (or plain forecast if no expiry)
    ax.plot(forecast_df['calendar_year'], forecast_df['revenue_post_expiry_usd'],
            'b-', linewidth=2.5, label='Revenue forecast')

    # Known data points (ground truth anchors)
    if len(known) > 0:
        ax.scatter(known['calendar_year'], known['predicted_revenue_usd'],
                   color='green', s=100, zorder=5, label='Known revenues (ground truth)')
        last_known_cal_year = known['calendar_year'].max()
        ax.axvline(x=last_known_cal_year, color='grey', linestyle='--',
                   linewidth=1, label='Extrapolation begins')

    # Patent expiry marker
    if patent_expiry_year:
        ax.axvline(x=patent_expiry_year, color='red', linestyle='--',
                   linewidth=1.5, label=f'Patent expiry ({patent_expiry_year})')

    ax.set_xlabel('Year')
    ax.set_ylabel('Revenue (USD millions)')
    ax.set_title(f'Revenue Forecast to {forecast_end_year}\n{indication} | Launched {launch_year}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
