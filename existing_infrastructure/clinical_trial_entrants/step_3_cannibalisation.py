from patent_forecast.v1.v1_patent_forecast import build_indication_trajectory, compute_indication_growth_rates
import pandas as pd
# ══════════════════════════════════════════════════════════════════════════════
# MODULE 3 — PIPELINE REVENUE FORECASTING AND MARKET CANNIBALIZATION
# Forecasts revenue for each pipeline asset and models the share it takes
# from existing marketed drugs
# ══════════════════════════════════════════════════════════════════════════════

# ── Market share erosion assumptions ─────────────────────────────────────────
# When a new entrant launches, it captures share from the existing market.
# These figures represent how much of a new entrant's revenue comes at the
# expense of your asset vs. growing the overall market.
# 'displacement_rate' = proportion of new entrant revenue taken FROM existing drugs
# 'your_asset_share'  = of the displaced revenue, what % comes from your asset
#                       (vs. other existing competitors)
# These are conservative estimates — adjust based on indication dynamics.

CANNIBALIZATION_ASSUMPTIONS = {
    'best' : {'displacement_rate': 0.30, 'your_asset_share': 0.40},
    'base' : {'displacement_rate': 0.50, 'your_asset_share': 0.50},
    'worst': {'displacement_rate': 0.70, 'your_asset_share': 0.60},
}


def forecast_pipeline_assets(pipeline_df, indication_group, indication_groups,
                              scenario, forecast_end_year=2036):
    """
    Generates revenue forecasts for all pipeline assets in the given scenario.
    Uses the existing predict_revenue infrastructure — pipeline assets start
    from zero with no known revenues, so the indication average trajectory
    is used in full.

    Args:
        pipeline_df:      cleaned + scored pipeline DataFrame (Module 1 + 2 output)
        indication_group: string — the indication group to use for trajectory
        indication_groups:dict   — output of group_by_indication()
        scenario:         'best', 'base', or 'worst'
        forecast_end_year:int

    Returns:
        list of dicts, one per pipeline asset that appears in this scenario
    """

    # Filter to assets that appear in this scenario
    if scenario == 'best':
        assets = pipeline_df[pipeline_df['scenario'] == 'best']
    elif scenario == 'base':
        assets = pipeline_df[pipeline_df['scenario'].isin(['best', 'base'])]
    else:
        assets = pipeline_df  # all assets

    print(f"\n{'='*55}")
    print(f"  Forecasting pipeline assets — {scenario.upper()} CASE")
    print(f"  {len(assets)} asset(s) included")
    print(f"{'='*55}")

    pipeline_forecasts = []

    for _, row in assets.iterrows():
        launch_year = int(row['estimated_launch_year'])

        if launch_year > forecast_end_year:
            print(f"  Skipping {row['intervention']} — launches after {forecast_end_year}")
            continue

        print(f"\n  Forecasting: {row['intervention']} (launches {launch_year}, {row['phase']})")

        # Use existing forecast infrastructure — no known revenues for pipeline assets
        avg_trajectory = build_indication_trajectory(indication_groups, indication_group)
        if avg_trajectory is None:
            continue

        total_years  = forecast_end_year - launch_year + 1
        growth_rates = compute_indication_growth_rates(avg_trajectory, total_years)

        # Start from indication average year 1 revenue (no known data)
        base_revenue = avg_trajectory['avg_revenue_usd'].iloc[0]

        results = []
        for yr_num in range(1, total_years + 1):
            calendar_year = launch_year + yr_num - 1
            revenue       = base_revenue

            for step in range(yr_num - 1):
                rate    = growth_rates.get(step + 1, growth_rates[max(growth_rates.keys())])
                revenue = revenue * (1 + rate)

            revenue = max(revenue, 0)
            results.append({
                'year_since_launch'      : yr_num,
                'calendar_year'          : calendar_year,
                'predicted_revenue_usd'  : round(revenue, 2),
                'revenue_post_expiry_usd': round(revenue, 2),
                'is_known_datapoint'     : False
            })

        pipeline_forecasts.append({
            'drug_name'  : row['intervention'],
            'phase'      : row['phase'],
            'launch_year': launch_year,
            'probability': row['success_probability'],
            'scenario'   : row['scenario'],
            'forecast'   : pd.DataFrame(results)
        })

    print(f"\n✅ {len(pipeline_forecasts)} pipeline asset(s) forecast for {scenario} case.")
    return pipeline_forecasts

def calculate_cannibalization(main_asset_forecast, pipeline_forecasts,
                              scenario, forecast_end_year=2036):
    """
    Calculates the revenue loss to your asset caused by pipeline entrants.

    For each year, the total revenue of all new pipeline entrants is calculated.
    A proportion of this is assumed to come at the expense of existing drugs
    (displacement_rate), and of that, a proportion comes from your asset
    specifically (your_asset_share).

    Revenue lost from your asset in year Y =
        sum(pipeline revenues in year Y)
        x displacement_rate
        x your_asset_share

    Returns the main asset forecast with an additional
    'revenue_post_competition_usd' column.
    """
    assumptions = CANNIBALIZATION_ASSUMPTIONS[scenario]
    displacement = assumptions['displacement_rate']
    asset_share  = assumptions['your_asset_share']

    df = main_asset_forecast.copy()
    df['pipeline_revenue_total'] = 0.0
    df['revenue_lost_to_pipeline'] = 0.0

    all_years = df['calendar_year'].values

    for year in all_years:
        total_pipeline_rev = 0.0
        for asset in pipeline_forecasts:
            asset_df = asset['forecast']
            year_row = asset_df[asset_df['calendar_year'] == year]
            if not year_row.empty:
                total_pipeline_rev += year_row['revenue_post_expiry_usd'].values[0]

        revenue_lost = total_pipeline_rev * displacement * asset_share

        df.loc[df['calendar_year'] == year, 'pipeline_revenue_total']  = round(total_pipeline_rev, 2)
        df.loc[df['calendar_year'] == year, 'revenue_lost_to_pipeline'] = round(revenue_lost, 2)

    df['revenue_post_competition_usd'] = (
        df['revenue_post_expiry_usd'] - df['revenue_lost_to_pipeline']
    ).clip(lower=0).round(2)

    total_loss = df['revenue_lost_to_pipeline'].sum()
    print(f"\nCannibalization summary ({scenario} case):")
    print(f"  Displacement rate : {displacement*100:.0f}% of pipeline revenue comes from existing drugs")
    print(f"  Your asset share  : {asset_share*100:.0f}% of that displacement hits your asset")
    print(f"  Total revenue lost to pipeline over forecast: ${total_loss:,.0f}m")

    return df
