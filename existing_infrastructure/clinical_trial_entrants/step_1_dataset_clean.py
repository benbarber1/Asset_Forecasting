import pandas as pd
import numpy as np
import re
from datetime import datetime

# ══════════════════════════════════════════════════════════════════════════════
# MODULE 1 — PIPELINE DATA CLEANING
# Reads the ClinicalTrials.gov export and produces a clean asset list
# ══════════════════════════════════════════════════════════════════════════════

# ── Phase normalisation map ───────────────────────────────────────────────────
# ClinicalTrials.gov uses inconsistent phase labels — standardise them here

PHASE_MAP = {
    'PHASE1'        : 'Phase I',
    'PHASE1|PHASE2' : 'Phase I/II',
    'PHASE2'        : 'Phase II',
    'PHASE2|PHASE3' : 'Phase II/III',
    'PHASE3'        : 'Phase III',
    'PHASE4'        : 'Phase IV',       # post-marketing — already launched
    'NA'            : 'Not Applicable',
    'EARLY_PHASE1'  : 'Phase I',
}

# ── Intervention cleaning ─────────────────────────────────────────────────────

def clean_intervention_name(raw_intervention):
    """
    ClinicalTrials.gov interventions are free text and may look like:
      'Drug: Pembrolizumab | Drug: Carboplatin | Procedure: Surgery'

    This extracts only the Drug interventions and strips the 'Drug:' prefix.
    Returns a sorted, deduplicated string of drug names for grouping.
    """
    if pd.isna(raw_intervention):
        return None

    parts  = str(raw_intervention).split('|')
    drugs  = []

    for part in parts:
        part = part.strip()
        if part.lower().startswith('drug:') or part.lower().startswith('biological:'):
            name = re.sub(r'^(drug|biological)\s*:\s*', '', part, flags=re.IGNORECASE)
            name = name.strip().title()
            if name:
                drugs.append(name)

    if not drugs:
        return None

    # Sort alphabetically so 'Drug A + Drug B' and 'Drug B + Drug A' group together
    return ' + '.join(sorted(set(drugs)))


def estimate_launch_year(row, avg_phase_durations):
    """
    Estimates the earliest likely launch year for a pipeline asset.

    Logic:
      - If the trial has a Completion Date, add the typical remaining development
        time from that phase to approval.
      - If no Completion Date, use today as the start and add the full
        remaining pipeline duration.

    avg_phase_durations: dict of {phase: years_to_approval_from_that_phase}
    """
    phase = row['Phase_Standardised']

    if phase not in avg_phase_durations:
        return None

    years_remaining = avg_phase_durations[phase]

    # Use completion date if available, otherwise today
    if pd.notna(row['Completion Date']):
        try:
            completion = pd.to_datetime(row['Completion Date'])
            base_year  = completion.year
        except:
            base_year = datetime.today().year
    else:
        base_year = datetime.today().year

    estimated_launch = base_year + years_remaining

    # Cap at forecast end — anything beyond 2036 is outside the window
    return int(estimated_launch) if estimated_launch <= 2036 else None

def get_most_advanced_phase(group, full_df):
    """
    For a group of rows sharing the same intervention name,
    returns the phase label from the row with the highest Phase_Order value.
    """
    phase_orders = full_df.loc[group.index, 'Phase_Order']
    best_idx     = phase_orders.idxmax()
    return group.loc[best_idx]


def load_and_clean_pipeline(filepath, avg_phase_durations=None):

    if avg_phase_durations is None:
        avg_phase_durations = {
            'Phase I'     : 8.0,
            'Phase I/II'  : 6.5,
            'Phase II'    : 5.0,
            'Phase II/III': 3.5,
            'Phase III'   : 1.5,
            'Phase IV'    : 0,
        }

    print(f"Loading pipeline data from: {filepath}")

    if filepath.endswith('.csv'):
        df = pd.read_csv(filepath)
    else:
        df = pd.read_excel(filepath)

    print(f"  Raw rows loaded: {len(df)}")
    print(f"  Columns found: {df.columns.tolist()}")
    print(f"  Unique Study Status values: {df['Study Status'].unique()}")
    print(f"  Unique Phase values: {df['Phases'].unique()}")

    # ── Filter to relevant trials ─────────────────────────────────────────────
    valid_statuses = [
        'RECRUITING', 'ACTIVE_NOT_RECRUITING', 'NOT_YET_RECRUITING',
        'ENROLLING_BY_INVITATION', 'COMPLETED'
    ]
    df = df[df['Study Status'].str.upper().str.strip().isin(valid_statuses)].copy()
    print(f"  After status filter: {len(df)} rows")

    # ── Standardise and filter phases ────────────────────────────────────────
    df['Phase_Standardised'] = (
        df['Phases'].str.upper().str.strip()
        .map(PHASE_MAP)
        .fillna('Unknown')
    )
    df = df[~df['Phase_Standardised'].isin(['Phase IV', 'Not Applicable', 'Unknown'])]
    print(f"  After phase filter: {len(df)} rows")

    # ── Clean interventions ───────────────────────────────────────────────────
    df['Intervention_Clean'] = df['Interventions'].apply(clean_intervention_name)
    df = df[df['Intervention_Clean'].notna()]
    print(f"  After intervention cleaning: {len(df)} rows")

    # ── Estimate launch year ──────────────────────────────────────────────────
    df['estimated_launch_year'] = df.apply(
        lambda row: estimate_launch_year(row, avg_phase_durations), axis=1
    )
    df = df[df['estimated_launch_year'].notna()]
    print(f"  Within forecast window (≤2036): {len(df)} rows")

    if len(df) == 0:
        print("  ⚠️  No rows remaining after filters — returning None.")
        return None

    # ── Assign phase order for groupby ───────────────────────────────────────
    phase_order_map = {
        'Phase I': 1, 'Phase I/II': 2, 'Phase II': 3,
        'Phase II/III': 4, 'Phase III': 5
    }
    df['Phase_Order'] = df['Phase_Standardised'].map(phase_order_map).fillna(0)

    # ── Group by intervention ─────────────────────────────────────────────────
    try:
        pipeline = (
            df.groupby('Intervention_Clean')
            .apply(lambda x: pd.Series({
                'phase'                : get_most_advanced_phase(x, df)['Phase_Standardised'],
                'estimated_launch_year': x['estimated_launch_year'].min(),
                'trial_count'          : x['NCT Number'].nunique(),
                'nct_numbers'          : ', '.join(x['NCT Number'].unique()[:3]),
                'study_status'         : x['Study Status'].mode()[0]
            }))
            .reset_index()
            .rename(columns={'Intervention_Clean': 'intervention'})
            .sort_values('estimated_launch_year')
            .reset_index(drop=True)
        )
        print(f"  Groupby complete. Pipeline shape: {pipeline.shape}")

    except Exception as e:
        print(f"  ERROR in groupby: {type(e).__name__}: {e}")
        return None

    print(f"\n✅ Pipeline cleaned: {len(pipeline)} unique intervention(s) identified.")
    print(pipeline[['intervention', 'phase', 'estimated_launch_year', 'trial_count']].to_string(index=False))

    return pipeline
