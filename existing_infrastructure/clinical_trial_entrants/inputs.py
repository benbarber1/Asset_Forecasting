import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sys
from pathlib import Path

# Add the project root directory to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

print("Current script location:", Path(__file__).resolve())
print("Calculated project root:", Path(__file__).resolve().parent.parent)
print("\nPython search paths:")
for p in sys.path:
    print(" ", p)


from clinical_trial_forecast.ct_gov_clean_up import load_and_clean_pipeline
from clinical_trial_forecast.prob_of_success import assign_success_probability, assign_scenarios
from clinical_trial_forecast.revenue_forecast import forecast_pipeline_assets, calculate_cannibalization
from clinical_trial_forecast.chart_creation import plot_full_dashboard
from competitor_forecast.v1_comp_forecast import build_competitor_list, plot_combined_forecast, print_summary_table
from patent_forecast.v1.v1_patent_forecast import group_by_indication, predict_revenue

# ══════════════════════════════════════════════════════════════════════════════
# FULL PIPELINE — RUN IN ORDER
# ══════════════════════════════════════════════════════════════════════════════

# Step 1: Load and group your dataset


'''

Identify whether the partially grouped or fully grouped dataset is more appropriate for your use case. 
The default is the grouped dataset, as for each disease there are likely to be more similar assets to learn from. 
However, if your asset is in a very unique indication, the partially grouped dataset may be more appropriate.

'''

#Fully grouped dataset:
# Paste your local path to the core dataset below.
# To find it: go into HCA Sharepoint > Business Planning > 2026 > Battlespaces > Horizon Intelligence Suite > Datasets
# Download the required dataset and save it somewhere in your user space
# Paste the file location here

core_dataset = r"C:\Users\Ben.Barber\OneDrive - Ipsos\Documents\Extracirriculars\[ML model]\Datasets\grouped_core_dataset.xlsx"

# ─────────────────────────────────────────────────────────────────────────────

df = pd.read_excel(core_dataset)


'''
Available indications in dataset: 
Indication_Group                 No. of assets
HIV                              18
Cancer: Haematological           13
Rare / Genetic Disease           10
Respiratory                      10
Hepatitis C (HCV)                 9
Cancer: Renal / Urological        7
Multiple Sclerosis (MS)           7
Cancer: Breast Cancer             5
Diabetes                          5
Cardiovascular                    5
Rheumatology / Immunology         5
Cancer: Lung                      3
Cancer: Mixed Indications         3
Cancer: Other Solid Tumour        3
Ungrouped                         2
COVID-19                          2
Cancer: Melanoma                  2
Cancer: Gastrointestinal          2
Deep Vein Thrombosis (DVT)        2
Osteoporosis                      2
Ophthalmology                     2
Female Birth Control              2
CNS / Neurology: Imaging          1
Acute Coronary Syndrome           1
Cervical Dystonia                 1
Dupuytren's Disease               1
Erectile Dysfunction              1
Mental Illness: MDD               1
Mental Illness: Schizophrenia     1
Human Papillomavirus (HPV)        1
Gastrointestinal                  1
Gout                              1
Infectious Disease: Other         1
Restless Legs Syndrome            1
'''

# ── Step 2: Run your main forecast ──────────────


indication_groups = group_by_indication(df)

main_forecast = predict_revenue(
    indication         = 'Cancer: Breast Cancer',
    launch_year        = 2021,
    known_revenues     = {1: 450, 2: 820, 3: 1100},
    indication_groups  = indication_groups,
    patent_expiry_year = 2032,
)

# ── Step 3: Load and clean the ClinicalTrials.gov pipeline data as a csv ───────────────

pipeline_raw = load_and_clean_pipeline(
    filepath = r"C:\Users\Ben.Barber\OneDrive - Ipsos\Documents\Extracirriculars\[ML model]\Clinical Trials\ctg-studies (3).csv"
)


# ── Diagnose before passing to next function ──────────────────────────────────
print(f"pipeline_raw type: {type(pipeline_raw)}")
print(f"pipeline_raw value: {pipeline_raw}")

# ── Step 4: Assign success probabilities and scenarios ────────────────────────

pipeline_scored = assign_success_probability(pipeline_raw, indication_group='Cancer: Breast Cancer')
pipeline_scored = assign_scenarios(pipeline_scored)

# ── Step 5: Load existing marketed competitors ────────────────────────────────

competitors_input = [
    {
        'drug_name'         : 'Competitor A',
        'indication'        : 'Cancer: Breast Cancer',
        'launch_year'       : 2018,
        'known_revenues'    : {1: 300, 2: 600, 3: 950, 4: 1200},
        'patent_expiry_year': 2027,
        'drug_type'         : 'small_molecule',
    },
]
competitor_forecasts = build_competitor_list(competitors_input, indication_groups)

# ── Step 6: Run for each scenario ─────────────────────────────────────────────

for scenario in ['best', 'base', 'worst']:
    print(f"\n{'#'*60}")
    print(f"  RUNNING: {scenario.upper()} CASE")
    print(f"{'#'*60}")

    # Forecast pipeline assets for this scenario
    pipeline_forecasts = forecast_pipeline_assets(
        pipeline_df      = pipeline_scored,
        indication_group = 'Cancer: Breast Cancer',
        indication_groups= indication_groups,
        scenario         = scenario,
    )

    # Calculate how much revenue pipeline takes from your asset
    main_with_competition = calculate_cannibalization(
        main_asset_forecast = main_forecast,
        pipeline_forecasts  = pipeline_forecasts,
        scenario            = scenario,
    )

    # Plot the full three-panel dashboard
    plot_full_dashboard(
        main_asset_name                      = 'My Drug',
        main_asset_forecast_with_competition = main_with_competition,
        competitor_forecasts                 = competitor_forecasts,
        pipeline_forecasts                   = pipeline_forecasts,
        pipeline_df                          = pipeline_scored,
        scenario                             = scenario,
        patent_expiry_year                   = 2032,
    )
