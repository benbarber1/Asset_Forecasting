import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from forecast import group_by_indication, predict_revenue

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


indication_groups = group_by_indication(df)

forecast = predict_revenue(
    indication          = 'HIV',
    launch_year         = 2024,
    known_revenues      = {1: 200, 2: 600},
    indication_groups   = indication_groups,
    patent_expiry_year  = 2038,          # set to None if not yet known
)
