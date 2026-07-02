"""
============================================================
 CONJOINT DATA PIPELINE  —  Full Build
============================================================
 Combines up to 6 market conjoint CSVs, applies QA filters,
 merges Qualtrics survey metadata, and outputs a single
 clean CSV with respondent filter columns.

 INPUTS
   - Up to 6 Sawtooth conjoint CSV files (one per market)
   - 1 Qualtrics completes CSV (2-row header format)
   - 1 Qualtrics fails CSV (2-row header format, same structure)

 OUTPUT
   - combined_conjoint_final.csv  (all markets, cleaned, tagged)
   - pipeline_log.txt             (run summary and warnings)
============================================================
"""

import pandas as pd
import os
import sys
from datetime import datetime

# ════════════════════════════════════════════════════════
#  SECTION 1 — FILE PATHS
#  Set each conjoint file path. Set to None if not used.
# ════════════════════════════════════════════════════════

CONJOINT_FILES = {
    "US": r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\2 June\US Test.csv",
    "UK": r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\2 June\UK Test.csv",
    "FR": r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\2 June\FR Test.csv",
    "DE": r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\2 June\DE Test.csv",
    "ES": r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\2 June\ES Test.csv",
    "IT": r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\2 June\IT Test.csv",
}

SURVEY_FILE  = r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\2 June\Completes_dataset.csv"
QA_FAIL_FILE = r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\2 June\Fails_Dataset.csv"
OUTPUT_FILE  = r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\2 June\combined_conjoint_final_0206_v2.csv"
LOG_FILE     = r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\2 June\conjoint_analysis_log.txt"

# ════════════════════════════════════════════════════════
#  SECTION 2 — COLUMN NAMES
# ════════════════════════════════════════════════════════

# --- Conjoint CSV columns ---
CONJOINT_ID_COL       = "p"                 # respondent ID
CONJOINT_RESPNUM_COL  = "sys_RespNum"       # Sawtooth respondent number
CONJOINT_STATUS_COL   = "sys_LastQuestion"  # must contain "terminate" to be valid

# --- Qualtrics CSV columns (Row A header names) ---
SURVEY_ID_COL         = "ResponseID"        # links to conjoint "p" column
SURVEY_COUNTRY_COL    = "Q2"
SURVEY_ROLE_COL       = "Q3"
SURVEY_ED_COL         = "ED Respondent"
SURVEY_ADOPTER_COL    = "Wearable Usage"
SURVEY_BEDSIZE_COL    = "Q13 Number of bed bigger buckets"
SURVEY_HOSPTYPE_COL   = "Q14"

# --- Fails file column ---
# The column name in Fails_Dataset.csv that contains the respondent IDs.
# This should match the ResponseID column name used in the Qualtrics export.
QA_FAIL_ID_COL        = "ResponseID"

# ════════════════════════════════════════════════════════
#  SECTION 3 — sys_RespNum OFFSETS
# ════════════════════════════════════════════════════════

RESPNUM_OFFSET = 100_000
MARKET_ORDER   = ["US", "UK", "FR", "DE", "ES", "IT"]

# ════════════════════════════════════════════════════════
#  SECTION 4 — CODE MAPPINGS
# ════════════════════════════════════════════════════════

COUNTRY_MAP = {
    "United States":  1,
    "United Kingdom": 2,
    "France":         3,
    "Germany":        4,
    "Spain":          5,
    "Italy":          6,
}

ROLE_MAP = {
    "Clinician (e.g., physician, nurse, respiratory therapist, NP/PA)":             1,
    "Clinical Leader (e.g., department head, medical director, nursing leadership)": 2,
    "Hospital Administrator (e.g., operations, finance, IT, executive leadership)":  3,
}

ED_MAP = {
    "yes": 1,
    "":    2,
}

ADOPTER_MAP = {
    "Adopter":     1,
    "Non-Adopter": 2,
}

BEDSIZE_MAP = {
    "1-149 beds": 1,
    "150-499":    2,
    "500+":       3,
}

HOSPTYPE_MAP = {
    "Academic":     1,
    "Non-Academic": 2,
}

# ════════════════════════════════════════════════════════
#  SECTION 5 — OUTPUT FILTER COLUMN NAMES
# ════════════════════════════════════════════════════════

OUT_COUNTRY  = "cntry"
OUT_ROLE     = "role"
OUT_ED       = "ed_flag"
OUT_ADOPTER  = "adopter"
OUT_BEDSIZE  = "bed_size"
OUT_HOSPTYPE = "hosp_type"

# ════════════════════════════════════════════════════════
#  MAIN PIPELINE — no edits needed below this line
# ════════════════════════════════════════════════════════

log_lines = []

def log(msg: str, level: str = "INFO"):
    prefix = {"INFO": "  ✓", "WARN": "  ⚠", "ERR": "  ✗"}.get(level, "   ")
    line = f"{prefix}  {msg}"
    print(line)
    log_lines.append(line)

def check_col(df, col, file_label):
    if col not in df.columns:
        col_list = "\n".join(f"    - '{c}'" for c in df.columns)
        msg = (
            f"\n\n  COLUMN NOT FOUND: '{col}' in {file_label}\n"
            f"  Check the column names in SECTION 2 of the config match your file.\n"
            f"  Actual columns in file ({len(df.columns)}):\n{col_list}"
        )
        print(msg)
        raise ValueError(msg)

def apply_map(series: pd.Series, mapping: dict, col_name: str) -> pd.Series:
    result = series.map(mapping)
    unmapped = series[result.isna() & series.notna() & (series != "")].unique()
    if len(unmapped):
        log(f"Unmapped values in '{col_name}' — add to mapping dict: {list(unmapped)}", "WARN")
    return result


# ────────────────────────────────────────
#  STEP 1 — Load & validate conjoint files
# ────────────────────────────────────────
def load_conjoint_files() -> pd.DataFrame:
    log_lines.append("\n[STEP 1]  Load conjoint files")
    print("\n[STEP 1]  Loading conjoint files ...")

    frames = []
    for idx, market in enumerate(MARKET_ORDER):
        path = CONJOINT_FILES.get(market)
        if path is None:
            log(f"{market}: skipped (no file configured)", "WARN")
            continue
        if not os.path.exists(path):
            log(f"{market}: file '{path}' not found — skipping", "WARN")
            continue

        df = pd.read_csv(path, dtype=str)
        raw_count = len(df)

        for col in [CONJOINT_ID_COL, CONJOINT_RESPNUM_COL, CONJOINT_STATUS_COL]:
            check_col(df, col, f"conjoint ({market})")

        mask_complete = df[CONJOINT_STATUS_COL].str.contains("terminate", case=False, na=False)
        df_complete = df[mask_complete].copy()
        n_dropped = raw_count - len(df_complete)

        df_complete["market"] = market

        offset = MARKET_ORDER.index(market) * RESPNUM_OFFSET
        df_complete[CONJOINT_RESPNUM_COL] = (
            pd.to_numeric(df_complete[CONJOINT_RESPNUM_COL], errors="coerce")
            .add(offset)
            .astype("Int64")
        )

        log(f"{market}: {raw_count:,} rows loaded → {len(df_complete):,} complete "
            f"({n_dropped} incomplete removed) | RespNum offset +{offset:,}")
        frames.append(df_complete)

    if not frames:
        log("No conjoint files loaded. Exiting.", "ERR")
        sys.exit(1)

    combined = pd.concat(frames, ignore_index=True)
    log(f"Combined total: {len(combined):,} respondents across {len(frames)} market(s)")
    return combined


# ────────────────────────────────────────
#  STEP 2 — Load Qualtrics survey
# ────────────────────────────────────────
def load_survey() -> pd.DataFrame:
    log_lines.append("\n[STEP 2]  Load Qualtrics survey (completes)")
    print("\n[STEP 2]  Loading Qualtrics survey ...")

    if not os.path.exists(SURVEY_FILE):
        log(f"Survey file '{SURVEY_FILE}' not found. Exiting.", "ERR")
        sys.exit(1)

    raw = pd.read_csv(SURVEY_FILE, header=0, dtype=str, encoding="cp1252")
    df  = raw.iloc[1:].reset_index(drop=True)   # drop the question-text row

    print("\n  Columns found in survey file:")
    for c in df.columns:
        print(f"    '{c}'")

    for col in [SURVEY_ID_COL, SURVEY_COUNTRY_COL, SURVEY_ROLE_COL,
                SURVEY_ED_COL, SURVEY_ADOPTER_COL, SURVEY_BEDSIZE_COL, SURVEY_HOSPTYPE_COL]:
        check_col(df, col, "Qualtrics survey")

    log(f"Survey loaded: {len(df):,} respondents")
    return df


# ────────────────────────────────────────
#  STEP 3 — Merge & apply filter codes
# ────────────────────────────────────────
def merge_and_tag(conjoint: pd.DataFrame, survey: pd.DataFrame) -> pd.DataFrame:
    log_lines.append("\n[STEP 3]  Merge & apply filter codes")
    print("\n[STEP 3]  Merging and applying filter codes ...")

    survey_cols = [SURVEY_ID_COL, SURVEY_COUNTRY_COL, SURVEY_ROLE_COL,
                   SURVEY_ED_COL, SURVEY_ADOPTER_COL, SURVEY_BEDSIZE_COL, SURVEY_HOSPTYPE_COL]
    survey_sub = survey[survey_cols].copy()
    survey_sub = survey_sub.rename(columns={SURVEY_ID_COL: CONJOINT_ID_COL})

    conjoint[CONJOINT_ID_COL]   = conjoint[CONJOINT_ID_COL].str.strip()
    survey_sub[CONJOINT_ID_COL] = survey_sub[CONJOINT_ID_COL].str.strip()

    merged = conjoint.merge(survey_sub, on=CONJOINT_ID_COL, how="left")

    n_no_match = merged[SURVEY_COUNTRY_COL].isna().sum()
    if n_no_match:
        log(f"{n_no_match} conjoint respondents had no match in survey file", "WARN")

    merged[OUT_COUNTRY]  = apply_map(merged[SURVEY_COUNTRY_COL].str.strip(),  COUNTRY_MAP,  SURVEY_COUNTRY_COL)
    merged[OUT_ROLE]     = apply_map(merged[SURVEY_ROLE_COL].str.strip(),     ROLE_MAP,     SURVEY_ROLE_COL)
    merged[OUT_ADOPTER]  = apply_map(merged[SURVEY_ADOPTER_COL].str.strip(),  ADOPTER_MAP,  SURVEY_ADOPTER_COL)
    merged[OUT_BEDSIZE]  = apply_map(merged[SURVEY_BEDSIZE_COL].str.strip(),  BEDSIZE_MAP,  SURVEY_BEDSIZE_COL)
    merged[OUT_HOSPTYPE] = apply_map(merged[SURVEY_HOSPTYPE_COL].str.strip(), HOSPTYPE_MAP, SURVEY_HOSPTYPE_COL)

    ed_series = merged[SURVEY_ED_COL].fillna("").str.strip().str.lower()
    merged[OUT_ED] = ed_series.map(lambda x: 1 if x == "yes" else 2).astype("Int64")

    for col in [OUT_COUNTRY, OUT_ROLE, OUT_ADOPTER, OUT_BEDSIZE, OUT_HOSPTYPE]:
        merged[col] = pd.to_numeric(merged[col], errors="coerce").astype("Int64")

    log(f"Merge complete: {len(merged):,} rows")
    return merged


# ────────────────────────────────────────
#  STEP 4 — Remove QA failures from final dataset
# ────────────────────────────────────────
def remove_qa_failures(df: pd.DataFrame) -> pd.DataFrame:
    log_lines.append("\n[STEP 4]  Remove QA failures from final dataset")
    print("\n[STEP 4]  Removing QA failures from final dataset ...")

    if QA_FAIL_FILE is None or not os.path.exists(str(QA_FAIL_FILE)):
        log("No QA failure file provided or file not found — skipping", "WARN")
        return df

    # Read fails file — handles both:
    #   (a) Qualtrics 2-row header export (skips the question-text row)
    #   (b) Plain list with a single header row
    raw_fails = pd.read_csv(QA_FAIL_FILE, header=0, dtype=str, encoding="cp1252")

    # If it looks like a Qualtrics export (second row is question text), drop that row
    if raw_fails.shape[0] > 0 and raw_fails.iloc[0].astype(str).str.startswith("Import").any():
        raw_fails = raw_fails.iloc[1:].reset_index(drop=True)

    # Validate the ID column exists
    check_col(raw_fails, QA_FAIL_ID_COL, "QA fails file")

    fail_ids = set(raw_fails[QA_FAIL_ID_COL].str.strip().dropna().tolist())
    log(f"{len(fail_ids):,} respondent IDs loaded from fails file")

    # Print the IDs being removed so it's easy to audit
    print(f"\n  Fail IDs to be removed ({len(fail_ids)}):")
    for rid in sorted(fail_ids):
        print(f"    {rid}")

    # Strip whitespace on conjoint IDs before comparing
    df[CONJOINT_ID_COL] = df[CONJOINT_ID_COL].str.strip()

    before        = len(df)
    matched_ids   = set(df[CONJOINT_ID_COL]).intersection(fail_ids)
    df            = df[~df[CONJOINT_ID_COL].isin(fail_ids)].copy()
    removed       = before - len(df)
    not_found     = fail_ids - matched_ids

    log(f"{removed:,} respondents removed from final dataset  "
        f"({before:,} before → {len(df):,} after)")

    if not_found:
        log(f"{len(not_found)} fail ID(s) were not found in the dataset "
            f"(already absent or ID mismatch):", "WARN")
        for rid in sorted(not_found):
            log(f"  not matched: {rid}", "WARN")

    return df


# ────────────────────────────────────────
#  STEP 5 — Drop survey raw columns & save
# ────────────────────────────────────────
def save_output(df: pd.DataFrame):
    log_lines.append("\n[STEP 5]  Save output")
    print("\n[STEP 5]  Saving output ...")

    drop_cols = [SURVEY_COUNTRY_COL, SURVEY_ROLE_COL, SURVEY_ED_COL,
                 SURVEY_ADOPTER_COL, SURVEY_BEDSIZE_COL, SURVEY_HOSPTYPE_COL]
    df = df.drop(columns=[c for c in drop_cols if c in df.columns])

    df.to_csv(OUTPUT_FILE, index=False)
    log(f"Output saved → {OUTPUT_FILE}  ({len(df):,} rows, {len(df.columns)} columns)")

    filter_cols = [OUT_COUNTRY, OUT_ROLE, OUT_ED, OUT_ADOPTER, OUT_BEDSIZE, OUT_HOSPTYPE]
    print("\n  Filter column distributions:")
    for col in filter_cols:
        if col in df.columns:
            counts = df[col].value_counts(dropna=False).sort_index().to_dict()
            print(f"    {col:12s}: {counts}")


# ────────────────────────────────────────
#  STEP 6 — Write log file
# ────────────────────────────────────────
def write_log():
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"Conjoint Pipeline Log\nRun: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 55 + "\n")
        f.write("\n".join(log_lines))
    print(f"\n  Log saved → {LOG_FILE}")


# ────────────────────────────────────────
#  RUN
# ────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  CONJOINT PIPELINE")
    print("=" * 55)

    conjoint = load_conjoint_files()       # Step 1: load & filter conjoint files
    survey   = load_survey()               # Step 2: load Qualtrics completes
    final    = merge_and_tag(conjoint,     # Step 3: merge & tag with filter codes
                             survey)
    final    = remove_qa_failures(final)   # Step 4: remove fails from final dataset
    save_output(final)                     # Step 5: drop raw cols & save
    write_log()                            # Step 6: write log

    print("\n" + "=" * 55)
    print("  PIPELINE COMPLETE")
    print("=" * 55 + "\n")