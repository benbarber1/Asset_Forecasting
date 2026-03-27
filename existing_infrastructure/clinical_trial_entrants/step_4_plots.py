# ══════════════════════════════════════════════════════════════════════════════
# MODULE 4 — COMBINED VISUALISATION
# Three-panel dashboard:
#   Chart 1 — Stacked area: full market view
#   Chart 2 — Line: your asset pre/post competition
#   Chart 3 — Table: pipeline asset summary
# ══════════════════════════════════════════════════════════════════════════════

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec

PIPELINE_COLOURS = ['#E63946', '#2A9D8F', '#E76F51', '#8338EC',
                    '#FB8500', '#06D6A0', '#FF006E', '#FFBE0B']

def plot_full_dashboard(main_asset_name, main_asset_forecast_with_competition,
                        competitor_forecasts, pipeline_forecasts,
                        pipeline_df, scenario, patent_expiry_year=None,
                        forecast_end_year=2036):
    """
    Produces a three-panel dashboard.

    Args:
        main_asset_name:                      string
        main_asset_forecast_with_competition: DataFrame — output of calculate_cannibalization()
        competitor_forecasts:                 list — existing marketed competitors
        pipeline_forecasts:                   list — pipeline assets for this scenario
        pipeline_df:                          DataFrame — for the summary table
        scenario:                             'best', 'base', or 'worst'
        patent_expiry_year:                   int or None
        forecast_end_year:                    int
    """

    fig = plt.figure(figsize=(18, 20))
    gs  = gridspec.GridSpec(3, 2, figure=fig, hspace=0.45, wspace=0.3,
                            height_ratios=[1, 1, 0.7])

    ax1 = fig.add_subplot(gs[0, :])   # Full width — stacked area
    ax2 = fig.add_subplot(gs[1, :])   # Full width — your asset
    ax3 = fig.add_subplot(gs[2, :])   # Full width — table

    years = sorted(main_asset_forecast_with_competition['calendar_year'].unique())

    # ── CHART 1: Stacked area — full market view ──────────────────────────────
    ax1.set_title(f'Full Market Revenue — {scenario.title()} Case\n'
                  f'Stacked area: each band = one drug\'s revenue',
                  fontsize=12, fontweight='bold', pad=12)

    stack_data   = {}
    stack_labels = []
    stack_colours = []

    # Your asset (navy)
    main_rev = []
    for yr in years:
        row = main_asset_forecast_with_competition[
            main_asset_forecast_with_competition['calendar_year'] == yr
        ]
        main_rev.append(row['revenue_post_competition_usd'].values[0] if not row.empty else 0)

    stack_data[main_asset_name] = main_rev
    stack_labels.append(main_asset_name)
    stack_colours.append('#1D3557')

    # Existing competitors
    for i, comp in enumerate(competitor_forecasts):
        comp_rev = []
        for yr in years:
            row = comp['forecast'][comp['forecast']['calendar_year'] == yr]
            comp_rev.append(row['revenue_post_expiry_usd'].values[0] if not row.empty else 0)
        stack_data[comp['drug_name']] = comp_rev
        stack_labels.append(comp['drug_name'])
        stack_colours.append(PIPELINE_COLOURS[i % len(PIPELINE_COLOURS)])

    # Pipeline entrants (shown with hatching to distinguish from marketed)
    for j, asset in enumerate(pipeline_forecasts):
        pipe_rev = []
        for yr in years:
            row = asset['forecast'][asset['forecast']['calendar_year'] == yr]
            pipe_rev.append(row['revenue_post_expiry_usd'].values[0] if not row.empty else 0)
        name = f"{asset['drug_name']} (pipeline)"
        stack_data[name] = pipe_rev
        stack_labels.append(name)
        stack_colours.append(PIPELINE_COLOURS[(i + j + 1) % len(PIPELINE_COLOURS)])

    # Build stacked area
    stacks = [stack_data[label] for label in stack_labels]
    ax1.stackplot(years, stacks, labels=stack_labels, colors=stack_colours, alpha=0.75)

    # Mark pipeline launch dates with vertical lines
    for asset in pipeline_forecasts:
        ax1.axvline(x=asset['launch_year'], color='grey', linestyle=':', linewidth=1, alpha=0.6)
        ax1.text(asset['launch_year'] + 0.1,
                 ax1.get_ylim()[1] * 0.95 if ax1.get_ylim()[1] > 0 else 100,
                 asset['drug_name'], fontsize=7, color='grey', rotation=90, va='top')

    if patent_expiry_year:
        ax1.axvline(x=patent_expiry_year, color='red', linestyle='--',
                    linewidth=1.5, label=f'Patent expiry ({patent_expiry_year})')

    ax1.set_ylabel('Revenue (USD millions)', fontsize=10)
    ax1.legend(loc='upper left', fontsize=8, framealpha=0.8, ncol=2)
    ax1.grid(True, alpha=0.2)
    ax1.set_xlim(min(years), max(years))

    # ── CHART 2: Your asset — pre and post competition ────────────────────────
    ax2.set_title(f'{main_asset_name} — Revenue Impact of Pipeline Competition\n'
                  f'{scenario.title()} case: shaded area = revenue lost to new entrants',
                  fontsize=12, fontweight='bold', pad=12)

    pre_comp  = [main_asset_forecast_with_competition[
                     main_asset_forecast_with_competition['calendar_year'] == yr
                 ]['revenue_post_expiry_usd'].values[0]
                 for yr in years]
    post_comp = [main_asset_forecast_with_competition[
                     main_asset_forecast_with_competition['calendar_year'] == yr
                 ]['revenue_post_competition_usd'].values[0]
                 for yr in years]

    ax2.plot(years, pre_comp, color='#1D3557', linewidth=2,
             linestyle='--', label='Without pipeline competition', alpha=0.6)
    ax2.plot(years, post_comp, color='#1D3557', linewidth=2.5,
             label='With pipeline competition')
    ax2.fill_between(years, post_comp, pre_comp,
                     alpha=0.15, color='red', label='Revenue lost to pipeline')

    if patent_expiry_year:
        ax2.axvline(x=patent_expiry_year, color='red', linestyle='--',
                    linewidth=1.5, label=f'Patent expiry ({patent_expiry_year})')

    for asset in pipeline_forecasts:
        ax2.axvline(x=asset['launch_year'], color='grey', linestyle=':',
                    linewidth=1, alpha=0.5)

    ax2.set_ylabel('Revenue (USD millions)', fontsize=10)
    ax2.set_xlabel('Year', fontsize=10)
    ax2.legend(loc='upper left', fontsize=9, framealpha=0.9)
    ax2.grid(True, alpha=0.2)
    ax2.set_xlim(min(years), max(years))

    # ── CHART 3: Pipeline summary table ──────────────────────────────────────
    ax3.axis('off')
    ax3.set_title('Pipeline Asset Summary', fontsize=12, fontweight='bold', pad=12)

    if scenario == 'best':
        table_assets = pipeline_df[pipeline_df['scenario'] == 'best']
    elif scenario == 'base':
        table_assets = pipeline_df[pipeline_df['scenario'].isin(['best', 'base'])]
    else:
        table_assets = pipeline_df

    table_data = []
    for _, row in table_assets.iterrows():
        table_data.append([
            row['intervention'][:35] + '...' if len(str(row['intervention'])) > 35
            else row['intervention'],
            row['phase'],
            str(int(row['estimated_launch_year'])),
            f"{row['success_probability']*100:.1f}%",
            row['scenario'].title()
        ])

    if table_data:
        col_labels   = ['Intervention', 'Phase', 'Est. Launch', 'P(Success)', 'First Appears In']
        col_widths   = [0.35, 0.15, 0.12, 0.12, 0.18]
        table        = ax3.table(
            cellText    = table_data,
            colLabels   = col_labels,
            colWidths   = col_widths,
            loc         = 'center',
            cellLoc     = 'center'
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 1.6)

        # Style header row
        for j in range(len(col_labels)):
            table[0, j].set_facecolor('#1D3557')
            table[0, j].set_text_props(color='white', fontweight='bold')

        # Alternate row shading
        for i in range(1, len(table_data) + 1):
            colour = '#F2F2F2' if i % 2 == 0 else '#FFFFFF'
            for j in range(len(col_labels)):
                table[i, j].set_facecolor(colour)
    else:
        ax3.text(0.5, 0.5, 'No pipeline assets in this scenario.',
                 ha='center', va='center', fontsize=11, color='grey',
                 transform=ax3.transAxes)

    fig.suptitle(
        f'Market Forecast Dashboard — {scenario.title()} Case\n'
        f'Forecast to {forecast_end_year}',
        fontsize=14, fontweight='bold', y=0.98
    )

    plt.savefig(f'market_forecast_{scenario}_case.png', dpi=150, bbox_inches='tight')
    plt.show()
    print(f"\n✅ Dashboard saved: market_forecast_{scenario}_case.png")
