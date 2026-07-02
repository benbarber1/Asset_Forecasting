import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sys
from pathlib import Path

# Add the project root directory to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# ══════════════════════════════════════════════════════════════════════════════
# COMPETITOR FORECAST MODULE
# Standalone code — imports the core forecasting functions from your main model
# Run after your main model has produced a forecast for your asset of interest
# ══════════════════════════════════════════════════════════════════════════════

# Import core functions from your main model file

from revenue_patent_forecast.forecast import (
    group_by_indication,
    build_indication_trajectory,
    compute_indication_growth_rates,
    apply_patent_expiry,
    FORECAST_END_YEAR,
    PATENT_EXPIRY_MULTIPLIERS
)


# ── COLOUR PALETTE ────────────────────────────────────────────────────────────
# Your asset of interest is always blue.
# Competitors are assigned colours from this list in the order they are added.

COMPETITOR_COLOURS = [
    '#E63946',   # Red
    '#2A9D8F',   # Teal
    '#E76F51',   # Orange
    '#8338EC',   # Purple
    '#FB8500',   # Amber
    '#06D6A0',   # Mint
    '#FF006E',   # Pink
    '#FFBE0B',   # Yellow
]


# ══════════════════════════════════════════════════════════════════════════════
# 1. FORECAST A SINGLE COMPETITOR
# Reuses the exact same logic as the main model — same indication trajectory,
# same growth rates, same patent expiry multipliers.
# ══════════════════════════════════════════════════════════════════════════════

def forecast_competitor(drug_name, indication, launch_year, known_revenues,
                        patent_expiry_year, indication_groups,
                        drug_type='unknown', forecast_end_year=FORECAST_END_YEAR):
    """
    Generates a revenue forecast for a single competitor drug.

    Args:
        drug_name:           string — name of the competitor drug
        indication:          string — must match a key in indication_groups
        launch_year:         int    — calendar year the competitor launched
        known_revenues:      dict   — {year_number: revenue_usd_millions}
                                      e.g. {1: 200, 2: 450}
                                      pass {} if no known revenues
        patent_expiry_year:  int or None — calendar year the patent expires
        indication_groups:   dict   — output of group_by_indication()
        drug_type:           string — 'small_molecule', 'biologic', or 'unknown'
                                      no functional impact yet — stored for future
                                      best/base/worst case patent expiry scenarios
        forecast_end_year:   int    — last forecast year (default 2036)

    Returns:
        dict containing:
            'drug_name'    : string
            'indication'   : string
            'launch_year'  : int
            'drug_type'    : string
            'forecast'     : DataFrame with year_since_launch, calendar_year,
                             predicted_revenue_usd, revenue_post_expiry_usd,
                             is_known_datapoint
    """

    total_years = forecast_end_year - launch_year + 1
    if total_years <= 0:
        raise ValueError(f"launch_year ({launch_year}) must be before {forecast_end_year}.")

    print(f"\n{'─'*55}")
    print(f"  Competitor     : {drug_name}")
    print(f"  Indication     : {indication}")
    print(f"  Drug type      : {drug_type}")
    print(f"  Launch year    : {launch_year}")
    print(f"  Patent expiry  : {patent_expiry_year if patent_expiry_year else 'Not provided'}")
    print(f"  Known revenues : {known_revenues if known_revenues else 'None — using indication average'}")
    print(f"{'─'*55}")

    # Step 1: Build indication trajectory
    avg_trajectory = build_indication_trajectory(indication_groups, indication)
    if avg_trajectory is None:
        print(f"  ⚠️  Could not build trajectory for '{indication}'. Skipping {drug_name}.")
        return None

    # Step 2: Extract growth rates
    growth_rates = compute_indication_growth_rates(avg_trajectory, total_years)

    # Step 3: Set extrapolation anchor
    if known_revenues:
        last_known_year    = max(known_revenues.keys())
        last_known_revenue = known_revenues[last_known_year]
    else:
        last_known_year    = 0
        last_known_revenue = avg_trajectory['avg_revenue_usd'].iloc[0]
        print(f"  No known revenues — starting from indication average "
              f"(${last_known_revenue:,.0f}m in year 1).")

    # Step 4: Build forecast year by year
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
                rate = growth_rates.get(
                    rate_lookup_year,
                    growth_rates[max(growth_rates.keys())]
                )
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

    print(f"  ✅ Forecast complete for {drug_name}.")
    return {
        'drug_name'   : drug_name,
        'indication'  : indication,
        'launch_year' : launch_year,
        'drug_type'   : drug_type,
        'forecast'    : forecast_df
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2. ADD MULTIPLE COMPETITORS
# Call this once per competitor — it appends to a running list.
# ══════════════════════════════════════════════════════════════════════════════

def build_competitor_list(competitors_input, indication_groups,
                          forecast_end_year=FORECAST_END_YEAR):
    """
    Takes a list of competitor input dictionaries and returns a list of
    completed competitor forecast objects.

    Args:
        competitors_input: list of dicts, each with keys:
            drug_name, indication, launch_year, known_revenues,
            patent_expiry_year, drug_type (optional)
        indication_groups: dict — output of group_by_indication()

    Returns:
        List of competitor forecast dicts (output of forecast_competitor)
    """
    competitor_forecasts = []

    print(f"\n{'='*55}")
    print(f"  Building forecasts for {len(competitors_input)} competitor(s)")
    print(f"{'='*55}")

    for comp in competitors_input:
        result = forecast_competitor(
            drug_name          = comp['drug_name'],
            indication         = comp['indication'],
            launch_year        = comp['launch_year'],
            known_revenues     = comp.get('known_revenues', {}),
            patent_expiry_year = comp.get('patent_expiry_year', None),
            drug_type          = comp.get('drug_type', 'unknown'),
            indication_groups  = indication_groups,
            forecast_end_year  = forecast_end_year
        )
        if result is not None:
            competitor_forecasts.append(result)

    print(f"\n✅ {len(competitor_forecasts)} competitor forecast(s) built successfully.")
    return competitor_forecasts


# ══════════════════════════════════════════════════════════════════════════════
# 3. COMBINED PLOT
# Plots your asset of interest (always blue) alongside all competitors.
# ══════════════════════════════════════════════════════════════════════════════

def plot_combined_forecast(main_asset_forecast, main_asset_name,
                           competitor_forecasts, forecast_end_year=FORECAST_END_YEAR,
                           return_figure=False):
    """
    Plots your asset of interest alongside all competitor forecasts on one chart.

    Args:
        main_asset_forecast:  DataFrame — output of predict_revenue() from main model
        main_asset_name:      string    — name of your asset of interest
        competitor_forecasts: list      — output of build_competitor_list()
        forecast_end_year:    int       — for axis labelling
    """

    fig, ax = plt.subplots(figsize=(14, 7))

    # ── Plot main asset (always blue) ─────────────────────────────────────────
    known_main = main_asset_forecast[main_asset_forecast['is_known_datapoint']]

    ax.plot(main_asset_forecast['calendar_year'],
            main_asset_forecast['revenue_post_expiry_usd'],
            color='#1D3557', linewidth=2.5, label=main_asset_name, zorder=5)

    if len(known_main) > 0:
        ax.scatter(known_main['calendar_year'],
                   known_main['predicted_revenue_usd'],
                   color='#1D3557', s=80, zorder=6)
        ax.axvline(x=known_main['calendar_year'].max(),
                   color='#1D3557', linestyle=':', linewidth=1, alpha=0.5)

    # ── Plot each competitor ───────────────────────────────────────────────────
    for i, comp in enumerate(competitor_forecasts):
        colour     = COMPETITOR_COLOURS[i % len(COMPETITOR_COLOURS)]
        df         = comp['forecast']
        known_comp = df[df['is_known_datapoint']]

        ax.plot(df['calendar_year'],
                df['revenue_post_expiry_usd'],
                color=colour, linewidth=2,
                label=comp['drug_name'], zorder=4)

        # Known data points for this competitor
        if len(known_comp) > 0:
            ax.scatter(known_comp['calendar_year'],
                       known_comp['predicted_revenue_usd'],
                       color=colour, s=70, zorder=5)
            ax.axvline(x=known_comp['calendar_year'].max(),
                       color=colour, linestyle=':', linewidth=1, alpha=0.4)

        # Patent expiry marker (subtle, matched to competitor colour)
        patent_yr = None
        for row in comp['forecast'].itertuples():
            if row.predicted_revenue_usd != row.revenue_post_expiry_usd:
                patent_yr = row.calendar_year
                break
        if patent_yr:
            ax.axvline(x=patent_yr, color=colour, linestyle='--',
                       linewidth=1, alpha=0.6)

    # ── Formatting ─────────────────────────────────────────────────────────────
    ax.set_xlabel('Year', fontsize=12)
    ax.set_ylabel('Revenue (USD millions)', fontsize=12)
    ax.set_title(f'Revenue Forecast to {forecast_end_year}\n'
                 f'{main_asset_name} vs. Competitors', fontsize=13)
    ax.legend(loc='upper left', framealpha=0.9, fontsize=10)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    
    if return_figure:
        return fig        # ← Streamlit uses this
    else:
        plt.show()        # ← terminal use still works
    


# ══════════════════════════════════════════════════════════════════════════════
# 4. SUMMARY TABLE
# Prints a clean year-by-year revenue table across all assets.
# ══════════════════════════════════════════════════════════════════════════════

def print_summary_table(main_asset_forecast, main_asset_name,
                        competitor_forecasts, forecast_end_year=FORECAST_END_YEAR):
    """
    Prints a combined revenue table with one column per drug and one row per year.
    All values are post-patent-expiry adjusted.
    """
    all_years = sorted(main_asset_forecast['calendar_year'].unique())

    summary = pd.DataFrame({'Year': all_years})
    summary = summary.set_index('Year')

    # Main asset
    main_rev = main_asset_forecast.set_index('calendar_year')['revenue_post_expiry_usd']
    summary[main_asset_name] = main_rev.reindex(all_years)

    # Competitors
    for comp in competitor_forecasts:
        comp_rev = comp['forecast'].set_index('calendar_year')['revenue_post_expiry_usd']
        summary[comp['drug_name']] = comp_rev.reindex(all_years)

    summary = summary.round(1).fillna('—')

    print(f"\n── Revenue Summary (USD millions, patent expiry adjusted) ──")
    print(summary.to_string())

    return summary
