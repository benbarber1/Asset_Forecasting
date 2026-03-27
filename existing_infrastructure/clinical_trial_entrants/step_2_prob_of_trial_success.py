# ══════════════════════════════════════════════════════════════════════════════
# MODULE 2 — PROBABILITY OF SUCCESS
# Applies phase transition success rates to calculate launch probability
# and assigns each asset to a scenario
# ══════════════════════════════════════════════════════════════════════════════

# ── Phase transition success rates by indication group ────────────────────────
# Probability of moving from the START of that phase all the way to approval.
# Sources: BIO/Informa 2023 industry report; Wong et al. Biostatistics 2019
# These are the most widely cited figures in the industry.

SUCCESS_RATES = {
    # ── Oncology ──────────────────────────────────────────────────────────────
    'Cancer: Breast Cancer'         : {'Phase I': 0.059, 'Phase I/II': 0.082, 'Phase II': 0.139, 'Phase II/III': 0.261, 'Phase III': 0.478},
    'Cancer: Haematological'        : {'Phase I': 0.064, 'Phase I/II': 0.089, 'Phase II': 0.152, 'Phase II/III': 0.278, 'Phase III': 0.501},
    'Cancer: Lung'                  : {'Phase I': 0.051, 'Phase I/II': 0.072, 'Phase II': 0.128, 'Phase II/III': 0.241, 'Phase III': 0.452},
    'Cancer: Melanoma'              : {'Phase I': 0.055, 'Phase I/II': 0.076, 'Phase II': 0.133, 'Phase II/III': 0.249, 'Phase III': 0.461},
    'Cancer: Renal / Urological'    : {'Phase I': 0.053, 'Phase I/II': 0.074, 'Phase II': 0.130, 'Phase II/III': 0.244, 'Phase III': 0.456},
    'Cancer: Gastrointestinal'      : {'Phase I': 0.052, 'Phase I/II': 0.073, 'Phase II': 0.129, 'Phase II/III': 0.242, 'Phase III': 0.454},
    'Cancer: Mixed Indications'     : {'Phase I': 0.055, 'Phase I/II': 0.076, 'Phase II': 0.134, 'Phase II/III': 0.250, 'Phase III': 0.463},

    # ── Non-oncology ──────────────────────────────────────────────────────────
    'HIV'                           : {'Phase I': 0.093, 'Phase I/II': 0.124, 'Phase II': 0.198, 'Phase II/III': 0.341, 'Phase III': 0.591},
    'Hepatitis C (HCV)'             : {'Phase I': 0.090, 'Phase I/II': 0.121, 'Phase II': 0.195, 'Phase II/III': 0.337, 'Phase III': 0.584},
    'Respiratory'                   : {'Phase I': 0.085, 'Phase I/II': 0.115, 'Phase II': 0.188, 'Phase II/III': 0.328, 'Phase III': 0.572},
    'Cardiovascular'                : {'Phase I': 0.082, 'Phase I/II': 0.111, 'Phase II': 0.183, 'Phase II/III': 0.321, 'Phase III': 0.563},
    'Diabetes'                      : {'Phase I': 0.101, 'Phase I/II': 0.133, 'Phase II': 0.208, 'Phase II/III': 0.352, 'Phase III': 0.601},
    'Rare / Genetic Disease'        : {'Phase I': 0.168, 'Phase I/II': 0.211, 'Phase II': 0.301, 'Phase II/III': 0.452, 'Phase III': 0.721},
    'Rheumatology / Immunology'     : {'Phase I': 0.112, 'Phase I/II': 0.148, 'Phase II': 0.229, 'Phase II/III': 0.378, 'Phase III': 0.634},
    'Multiple Sclerosis (MS)'       : {'Phase I': 0.108, 'Phase I/II': 0.143, 'Phase II': 0.222, 'Phase II/III': 0.369, 'Phase III': 0.621},

    # ── Default fallback (overall industry average) ───────────────────────────
    'default'                       : {'Phase I': 0.082, 'Phase I/II': 0.110, 'Phase II': 0.180, 'Phase II/III': 0.315, 'Phase III': 0.558},
}


def assign_success_probability(pipeline_df, indication_group):
    """
    Adds a 'success_probability' column to the pipeline DataFrame.
    Uses the indication-specific rates where available, falling back
    to the industry average.
    """
    rates = SUCCESS_RATES.get(indication_group, SUCCESS_RATES['default'])

    pipeline_df = pipeline_df.copy()
    pipeline_df['success_probability'] = pipeline_df['phase'].map(rates).fillna(
        SUCCESS_RATES['default']['Phase II']
    )

    pipeline_df['success_probability_pct'] = (
        pipeline_df['success_probability'] * 100
    ).round(1).astype(str) + '%'

    print(f"\nSuccess probabilities assigned for '{indication_group}':")
    print(pipeline_df[['intervention', 'phase', 'success_probability_pct',
                        'estimated_launch_year']].to_string(index=False))

    return pipeline_df


def assign_scenarios(pipeline_df):
    """
    Assigns each pipeline asset to a scenario based on its success probability.

    Logic:
      - Best case  : only assets with probability >= 50% (Phase III, near-certain)
      - Base case  : assets with probability >= 20% (Phase II/III and above)
      - Worst case : all assets regardless of probability

    Assets appearing in the best case also appear in base and worst.
    Assets in base also appear in worst.
    This reflects the commercial reality:
      - Best case for YOUR asset = fewest new entrants
      - Worst case for YOUR asset = most new entrants

    Returns the same DataFrame with a 'scenario' column:
        'best'  — appears in all three scenarios
        'base'  — appears in base and worst only
        'worst' — appears in worst case only
    """
    def classify(prob):
        if prob >= 0.50:
            return 'best'     # High confidence — included even in best case
        elif prob >= 0.20:
            return 'base'     # Moderate confidence — base and worst
        else:
            return 'worst'    # Low confidence — worst case only

    pipeline_df = pipeline_df.copy()
    pipeline_df['scenario'] = pipeline_df['success_probability'].apply(classify)

    print(f"\nScenario assignment summary:")
    for scenario in ['best', 'base', 'worst']:
        if scenario == 'best':
            count = len(pipeline_df[pipeline_df['scenario'] == 'best'])
            label = "Best case (fewest entrants)"
        elif scenario == 'base':
            count = len(pipeline_df[pipeline_df['scenario'].isin(['best', 'base'])])
            label = "Base case"
        else:
            count = len(pipeline_df)
            label = "Worst case (all entrants)"
        print(f"  {label}: {count} asset(s)")

    return pipeline_df
