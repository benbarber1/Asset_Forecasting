import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sys
from pathlib import Path

# Add the project root directory to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from revenue_patent_forecast.forecast import group_by_indication, predict_revenue
from comp_forecast import build_competitor_list, plot_combined_forecast, print_summary_table
'''

Identify whether the partially grouped or fully grouped dataset is more appropriate for your use case. 
Un-hash the desired databased before running.

'''

#Partially grouped dataset:
#core_dataset = r"C:\Users\bbarber\OneDrive - BGB Group\Documents\Modelling\Core Dataset\odd_standardised.xlsx"

#Fully grouped dataset:
core_dataset = r"C:\Users\bbarber\OneDrive - BGB Group\Documents\Modelling\Core Dataset\odd_grouped.xlsx"

df = pd.read_excel(core_dataset)

# Step 1: Load and group your dataset
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

# ── Step 1: Run your main model first ─────────────────────────────────────────

indication_groups = group_by_indication(df)

main_forecast = predict_revenue(
    indication         = 'HIV',
    launch_year        = 2021,
    known_revenues     = {1: 450, 2: 820, 3: 1100},
    indication_groups  = indication_groups,
    patent_expiry_year = 2032,
)

# ── Step 2: Define your competitors ───────────────────────────────────────────
# Add as many competitors as needed — each is a dict.
# known_revenues: pass {} if you have no actual revenue data yet.
# patent_expiry_year: pass None if unknown.
# drug_type: 'small_molecule', 'biologic', or 'unknown' (no effect on output yet)

competitors_input = [
    {
        'drug_name'         : 'Competitor A',
        'indication'        : 'HIV',
        'launch_year'       : 2018,
        'known_revenues'    : {1: 100, 2: 250, 3: 350, 4: 400, 5: 600, 6: 650, 7: 800},
        'patent_expiry_year': 2027,
        'drug_type'         : 'small_molecule',
    },
    {
        'drug_name'         : 'Competitor B',
        'indication'        : 'HIV',
        'launch_year'       : 2020,
        'known_revenues'    : {1: 150, 2: 400, 3: 1000, 4: 1050, 5: 1150},
        'patent_expiry_year': 2029,
        'drug_type'         : 'biologic',
    },
    {
        'drug_name'         : 'Competitor C',
        'indication'        : 'HIV',
        'launch_year'       : 2023,
        'known_revenues'    : {1: 300, 2: 600},           # no known revenues yet
        'patent_expiry_year': 2031,
        'drug_type'         : 'unknown',
    },
]

# ── Step 3: Build competitor forecasts ────────────────────────────────────────

competitor_forecasts = build_competitor_list(competitors_input, indication_groups)

# ── Step 4: Plot everything together ──────────────────────────────────────────

plot_combined_forecast(
    main_asset_forecast  = main_forecast,
    main_asset_name      = 'My Drug',
    competitor_forecasts = competitor_forecasts,
)

# ── Step 5: Print summary table ───────────────────────────────────────────────

summary = print_summary_table(
    main_asset_forecast  = main_forecast,
    main_asset_name      = 'My Drug',
    competitor_forecasts = competitor_forecasts,
)
