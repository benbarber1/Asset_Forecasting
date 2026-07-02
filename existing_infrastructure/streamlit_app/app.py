import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ── Import your existing functions ────────────────────────────────────────────
from revenue_patent_forecast.forecast import (
    group_by_indication,
    predict_revenue,
    FORECAST_END_YEAR
)
from comp_analysis.comp_forecast import (
    build_competitor_list,
    plot_combined_forecast
)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title  = "Asset Forecasting",
    page_icon   = "💊",
    layout      = "wide",
    initial_sidebar_state = "expanded"
)

st.title("Asset Forecasting")
st.markdown("*Competitive Intelligence Platform*")
st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — DATASET LOADING
# ══════════════════════════════════════════════════════════════════════════════

indication_groups = {}

with st.sidebar:
    st.header("⚙️ Configuration")
 
    # Dataset upload — replaces the hardcoded file path
    uploaded_file = st.file_uploader(
        "Upload core dataset (.xlsx)",
        type = ['xlsx'],
        help = "Upload the grouped and standardised dataset"
    )

    if uploaded_file:
        df_grouped = pd.read_excel(uploaded_file)
        indication_groups = group_by_indication(df_grouped)
        st.success(f"✅ Dataset loaded: {len(df_grouped)} rows")
        st.info(f"{len(indication_groups)} indication groups found")
    else:
        st.warning("Please upload the core dataset to begin")
        st.stop()  # Stops the app here until a file is uploaded

# ══════════════════════════════════════════════════════════════════════════════
# MAIN ASSET INPUTS
# ══════════════════════════════════════════════════════════════════════════════

st.header("1. Asset of Interest")

col1, col2, col3 = st.columns(3)

with col1:
    drug_name = st.text_input(
        "Drug name",
        value = "My Drug",
        help  = "Name of the asset being forecast"
    )
    indication = st.selectbox(
        "Indication group",
        options = sorted(list(indication_groups.keys())),
        help    = "Select the therapeutic area"
    )

with col2:
    launch_year = st.number_input(
        "Launch year",
        min_value = 1990,
        max_value = 2030,
        value     = 2021,
        step      = 1
    )
    patent_expiry_year = st.number_input(
        "Patent expiry year (0 = unknown)",
        min_value = 0,
        max_value = 2040,
        value     = 0,
        step      = 1,
        help      = "Enter 0 if patent expiry date is not yet known"
    )
    patent_expiry_year = None if patent_expiry_year == 0 else int(patent_expiry_year)

with col3:
    st.markdown("**Known revenues (USD millions)**")
    st.caption("Leave at 0 for years with no data")

    known_revenues = {}
    for yr in range(1, 6):
        val = st.number_input(
            f"Year {yr}",
            min_value = 0.0,
            value     = 0.0,
            step      = 10.0,
            key       = f"revenue_yr_{yr}"
        )
        if val > 0:
            known_revenues[yr] = val

# ══════════════════════════════════════════════════════════════════════════════
# COMPETITORS
# ══════════════════════════════════════════════════════════════════════════════

st.divider()
st.header("2. Competitors")

num_competitors = st.slider(
    "Number of competitors to add",
    min_value = 0,
    max_value = 8,
    value     = 0
)

competitors_input = []

if num_competitors > 0:
    for i in range(num_competitors):
        with st.expander(f"Competitor {i + 1}", expanded=(i == 0)):
            c1, c2, c3 = st.columns(3)

            with c1:
                comp_name = st.text_input(
                    "Drug name",
                    value = f"Competitor {i + 1}",
                    key   = f"comp_name_{i}"
                )
                comp_indication = st.selectbox(
                    "Indication",
                    options = sorted(list(indication_groups.keys())),
                    key     = f"comp_ind_{i}"
                )

            with c2:
                comp_launch = st.number_input(
                    "Launch year",
                    min_value = 1990,
                    max_value = 2030,
                    value     = 2018,
                    step      = 1,
                    key       = f"comp_launch_{i}"
                )
                comp_expiry = st.number_input(
                    "Patent expiry (0 = unknown)",
                    min_value = 0,
                    max_value = 2040,
                    value     = 0,
                    step      = 1,
                    key       = f"comp_expiry_{i}"
                )
                comp_expiry = None if comp_expiry == 0 else int(comp_expiry)

            with c3:
                st.markdown("**Known revenues**")
                comp_revenues = {}
                for yr in range(1, 6):
                    val = st.number_input(
                        f"Year {yr}",
                        min_value = 0.0,
                        value     = 0.0,
                        step      = 10.0,
                        key       = f"comp_rev_{i}_{yr}"
                    )
                    if val > 0:
                        comp_revenues[yr] = val

            competitors_input.append({
                'drug_name'         : comp_name,
                'indication'        : comp_indication,
                'launch_year'       : comp_launch,
                'known_revenues'    : comp_revenues,
                'patent_expiry_year': comp_expiry,
                'drug_type'         : 'unknown',
            })

# ══════════════════════════════════════════════════════════════════════════════
# GENERATE FORECAST
# ══════════════════════════════════════════════════════════════════════════════

st.divider()

if st.button("🚀 Generate Forecast", type="primary", use_container_width=True):

    if not known_revenues:
        st.warning("No known revenues entered — forecast will use the indication average in full.")

    with st.spinner("Building forecast..."):

        # ── Main asset forecast ───────────────────────────────────────────────
        main_forecast = predict_revenue(
            indication         = indication,
            launch_year        = launch_year,
            known_revenues     = known_revenues,
            indication_groups  = indication_groups,
            patent_expiry_year = patent_expiry_year,
        )

        # ── Competitor forecasts ──────────────────────────────────────────────
        competitor_forecasts = []
        if competitors_input:
            competitor_forecasts = build_competitor_list(
                competitors_input, indication_groups
            )

    st.success("Forecast generated successfully.")
    st.divider()

    # ── Results ───────────────────────────────────────────────────────────────
    st.header("3. Results")

    tab1, tab2, tab3 = st.tabs(["📈 Forecast Chart", "📊 Revenue Table", "📋 Methodology"])

    with tab1:
        fig = plot_combined_forecast(
            main_asset_forecast  = main_forecast,
            main_asset_name      = drug_name,
            competitor_forecasts = competitor_forecasts,
            return_figure        = True   # see note below
        )
        st.pyplot(fig)

    with tab2:
        # Build summary table
        all_years = sorted(main_forecast['calendar_year'].unique())
        summary   = pd.DataFrame({'Year': all_years}).set_index('Year')
        summary[drug_name] = main_forecast.set_index(
            'calendar_year')['revenue_post_expiry_usd'].reindex(all_years)

        for comp in competitor_forecasts:
            summary[comp['drug_name']] = comp['forecast'].set_index(
                'calendar_year')['revenue_post_expiry_usd'].reindex(all_years)

        st.dataframe(summary.round(1).fillna('—'), use_container_width=True)

        # Download button
        csv = summary.to_csv()
        st.download_button(
            label     = "⬇️ Download as CSV",
            data      = csv,
            file_name = f"{drug_name}_forecast.csv",
            mime      = "text/csv"
        )

    with tab3:
        st.markdown("""
        **How the forecast is generated**

        The revenue forecast combines two sources of information:
        the historical revenue trajectories of comparable drugs within the same
        therapeutic area, and any known revenue figures provided for the asset
        being analysed.

        For each therapeutic area, the model calculates average year-on-year
        growth rates from all comparable drugs in the dataset, indexed to years
        since launch. These rates are then applied forward from the last known
        revenue data point, so the forecast reflects the drug's actual
        performance rather than reverting to the indication average.

        Where a patent expiry date is provided, revenues are adjusted using
        observed post-expiry decay multipliers derived from cross-country data.
        """)