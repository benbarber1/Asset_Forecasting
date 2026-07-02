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
   - 1 ED respondents CSV/Excel file (ResponseID column)

 OUTPUT
   - combined_conjoint_final.csv  (all markets, cleaned, tagged)
   - pipeline_log.txt             (run summary and warnings)

 KEY LOGIC
   - Only respondents whose "p" value appears in the Completes
     file are kept in the final output. Sawtooth completion
     status alone is NOT sufficient — the Completes file is
     the definitive allowlist.
   - ED_role is tagged from the ED Roles file (ResponseID
     membership), not from Q4/Q5 survey text.
   - vendor/pid come from Qualtrics and are preserved in output.
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
    "US": r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\17 June\US Test.csv",
    "UK": r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\17 June\UK Test.csv",
    "FR": r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\17 June\FR Test.csv",
    "DE": r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\17 June\DE Test.csv",
    "ES": r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\17 June\ES Test.csv",
    "IT": r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\17 June\IT Test.csv",
}

SURVEY_FILE  = r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\17 June\Completes 1706.csv"
QA_FAIL_FILE = r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\17 June\Fails 1706.csv"
OUTPUT_FILE  = r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\17 June\combined_conjoint_final_1706_v6.csv"
LOG_FILE     = r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\17 June\conjoint_analysis_log.txt"

# Path to the CSV/Excel file containing ED respondent IDs.
# Set to None to skip ED tagging entirely.
ED_FILE      = r"C:\Users\bbarber\OneDrive - BGB Group\Documents\1) Project work\BD\BD-014\Conjoint Analysis\17 June\ED Roles 1706.csv"

# ════════════════════════════════════════════════════════
#  SECTION 2 — COLUMN NAMES
# ════════════════════════════════════════════════════════

# --- Conjoint CSV columns ---
CONJOINT_ID_COL       = "p"                 # respondent ID — must match ResponseID in Completes
CONJOINT_RESPNUM_COL  = "sys_RespNum"       # Sawtooth respondent number
CONJOINT_STATUS_COL   = "sys_LastQuestion"  # used only as a pre-filter; Completes file is definitive

# --- Qualtrics CSV columns (Row A header names) ---
SURVEY_ID_COL         = "ResponseID"        # links to conjoint "p" column
SURVEY_VENDOR_COL     = "vendor"            # vendor identifier (vendor1 / vendor2)
SURVEY_PID_COL        = "pid"               # vendor2 respondent ID
SURVEY_COUNTRY_COL    = "Q2"
SURVEY_ROLE_COL       = "Q3"
SURVEY_Q4_COL         = "Q4"
SURVEY_Q5_COL         = "Q5"
SURVEY_ED_COL         = "ED Respondent"
SURVEY_ADOPTER_COL    = "Wearable Usage"
SURVEY_BEDSIZE_COL    = "Q13 Number of bed bigger buckets"
SURVEY_HOSPTYPE_COL   = "Q14"

# --- Fails file column ---
QA_FAIL_ID_COL        = "ResponseID"

# --- ED respondents file ---
ED_FILE_ID_COL        = "ResponseID"

# ════════════════════════════════════════════════════════
#  SECTION 3 — sys_RespNum OFFSETS
# ════════════════════════════════════════════════════════

RESPNUM_OFFSET = 100_000
MARKET_ORDER   = ["US", "UK", "FR", "DE", "ES", "IT"]

# ════════════════════════════════════════════════════════
#  SECTION 4 — CODE MAPPINGS
# ════════════════════════════════════════════════════════

# Keys are lowercase — Q2 values are normalised before mapping.
COUNTRY_MAP = {
    "united states":           1,
    "united states of america": 1,
    "us":                      1,
    "usa":                     1,
    "united kingdom":          2,
    "uk":                      2,
    "great britain":           2,
    "france":                  3,
    "germany":                 4,
    "spain":                   5,
    "italy":                   6,
}

ROLE_MAP = {
    "Clinician (e.g., physician, nurse, respiratory therapist, NP/PA)":             1,
    "Clinical Leader (e.g., department head, medical director, nursing leadership)": 2,
    "Hospital Administrator (e.g., operations, finance, IT, executive leadership)":  3,
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

OUT_COUNTRY    = "cntry"
OUT_COUNTRY_US = "Country"   # 1 = US, 2 = OUS
OUT_ROLE       = "role"
OUT_ED         = "ed_flag"
OUT_ADOPTER    = "adopter"
OUT_BEDSIZE    = "bed_size"
OUT_HOSPTYPE   = "hosp_type"
OUT_ED_ROLE    = "ED_role"   # 1 = in ED Roles file, 2 = not in ED Roles file

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

def load_qualtrics_csv(path: str, label: str) -> pd.DataFrame:
    """
    Load a Qualtrics CSV that has a 2-row header (row 0 = column names,
    row 1 = question text / ImportId metadata). Strips the second header row
    and returns a clean DataFrame.
    """
    raw = pd.read_csv(path, header=0, dtype=str, encoding="cp1252")
    df  = raw.iloc[1:].reset_index(drop=True)
    log(f"{label} loaded: {len(df):,} rows")
    return df


# ────────────────────────────────────────
#  STEP 1 — Load conjoint files
#  Pre-filters to Sawtooth-complete rows only. The definitive
#  allowlist filter against the Completes file happens in Step 3.
# ────────────────────────────────────────
def load_conjoint_files() -> pd.DataFrame:
    log_lines.append("\n[STEP 1]  Load conjoint files")
    print("\n[STEP 1]  Loading conjoint files ...")

    frames = []
    for market in MARKET_ORDER:
        path = CONJOINT_FILES.get(market)
        if path is None:
            log(f"{market}: skipped (no file configured)", "WARN")
            continue
        if not os.path.exists(path):
            log(f"{market}: file not found at '{path}' — skipping", "WARN")
            continue

        df = pd.read_csv(path, dtype=str)
        raw_count = len(df)

        for col in [CONJOINT_ID_COL, CONJOINT_RESPNUM_COL, CONJOINT_STATUS_COL]:
            check_col(df, col, f"conjoint ({market})")

        mask_complete = df[CONJOINT_STATUS_COL].str.contains("terminate", case=False, na=False)
        df_complete   = df[mask_complete].copy()
        n_dropped     = raw_count - len(df_complete)

        df_complete["market"] = market

        offset = MARKET_ORDER.index(market) * RESPNUM_OFFSET
        df_complete[CONJOINT_RESPNUM_COL] = (
            pd.to_numeric(df_complete[CONJOINT_RESPNUM_COL], errors="coerce")
            .add(offset)
            .astype("Int64")
        )

        log(f"{market}: {raw_count:,} rows → {len(df_complete):,} Sawtooth-complete "
            f"({n_dropped} incomplete removed) | RespNum offset +{offset:,}")
        frames.append(df_complete)

    if not frames:
        log("No conjoint files loaded. Exiting.", "ERR")
        sys.exit(1)

    combined = pd.concat(frames, ignore_index=True)
    log(f"Combined total after Sawtooth filter: {len(combined):,} respondents across {len(frames)} market(s)")
    return combined


# ────────────────────────────────────────
#  STEP 2 — Load Qualtrics Completes
# ────────────────────────────────────────
def load_survey() -> pd.DataFrame:
    log_lines.append("\n[STEP 2]  Load Qualtrics survey (completes)")
    print("\n[STEP 2]  Loading Qualtrics completes ...")

    if not os.path.exists(SURVEY_FILE):
        log(f"Survey file not found: '{SURVEY_FILE}'. Exiting.", "ERR")
        sys.exit(1)

    df = load_qualtrics_csv(SURVEY_FILE, "Completes")

    print("\n  Columns found in completes file:")
    for c in df.columns:
        print(f"    '{c}'")

    required = [SURVEY_ID_COL, SURVEY_VENDOR_COL, SURVEY_PID_COL,
                SURVEY_COUNTRY_COL, SURVEY_ROLE_COL,
                SURVEY_Q4_COL, SURVEY_Q5_COL,
                SURVEY_ED_COL, SURVEY_ADOPTER_COL,
                SURVEY_BEDSIZE_COL, SURVEY_HOSPTYPE_COL]
    for col in required:
        check_col(df, col, "Qualtrics completes")

    # Diagnostic: show unique Q2 values to catch country string mismatches early
    unique_q2 = df[SURVEY_COUNTRY_COL].dropna().unique()
    print(f"\n  Unique Q2 (country) values ({len(unique_q2)}):")
    for v in sorted(unique_q2):
        print(f"    '{v}'")

    return df


# ────────────────────────────────────────
#  STEP 3 — Merge conjoint with Completes, then filter to Completes-only
#
#  BUG FIX: previously the pipeline kept all Sawtooth-complete rows and
#  did a left-join, so conjoint respondents not in the Completes file
#  were retained with empty vendor/tagging columns. We now do the
#  opposite: start from the Completes file's ResponseIDs as the
#  allowlist, inner-join to conjoint, and drop anything not in both.
# ────────────────────────────────────────
def merge_and_tag(conjoint: pd.DataFrame, survey: pd.DataFrame) -> pd.DataFrame:
    log_lines.append("\n[STEP 3]  Filter to Completes allowlist & apply filter codes")
    print("\n[STEP 3]  Filtering to Completes and applying filter codes ...")

    survey_cols = [SURVEY_ID_COL, SURVEY_VENDOR_COL, SURVEY_PID_COL,
                   SURVEY_COUNTRY_COL, SURVEY_ROLE_COL,
                   SURVEY_Q4_COL, SURVEY_Q5_COL,
                   SURVEY_ED_COL, SURVEY_ADOPTER_COL,
                   SURVEY_BEDSIZE_COL, SURVEY_HOSPTYPE_COL]
    survey_sub = survey[survey_cols].copy()
    survey_sub = survey_sub.rename(columns={SURVEY_ID_COL: CONJOINT_ID_COL})

    # Normalise IDs on both sides before joining
    conjoint[CONJOINT_ID_COL]   = conjoint[CONJOINT_ID_COL].str.strip()
    survey_sub[CONJOINT_ID_COL] = survey_sub[CONJOINT_ID_COL].str.strip()

    n_conjoint_before = len(conjoint)
    completes_ids     = set(survey_sub[CONJOINT_ID_COL])

    # INNER JOIN — only keep conjoint rows whose "p" is in the Completes file.
    # This is the definitive allowlist filter; it replaces the old left-join
    # which was leaving unmatched conjoint rows with empty tagging columns.
    merged = conjoint.merge(survey_sub, on=CONJOINT_ID_COL, how="inner")

    n_removed = n_conjoint_before - len(merged)
    if n_removed > 0:
        log(f"{n_removed} conjoint rows removed: 'p' not found in Completes file", "WARN")
        # Identify and log the missing IDs for auditing
        missing_ids = set(conjoint[CONJOINT_ID_COL]) - completes_ids
        for rid in sorted(missing_ids):
            log(f"  not in Completes: {rid}", "WARN")

    log(f"After Completes filter: {len(merged):,} respondents retained")

    # Sanity check — there should be no rows with missing vendor after an inner join
    n_missing_vendor = merged[SURVEY_VENDOR_COL].isna().sum()
    if n_missing_vendor:
        log(f"{n_missing_vendor} rows have no vendor value after merge — "
            f"check for blank vendor cells in the Completes file", "WARN")

    # ── cntry: map country name → numeric code (case-insensitive) ──────────
    country_norm = merged[SURVEY_COUNTRY_COL].fillna("").str.strip().str.lower()
    merged[OUT_COUNTRY] = country_norm.map(COUNTRY_MAP)
    unmapped = country_norm[merged[OUT_COUNTRY].isna() & (country_norm != "")].unique()
    if len(unmapped):
        log(f"Unmapped Q2 values — add to COUNTRY_MAP: {list(unmapped)}", "WARN")
    merged[OUT_COUNTRY] = pd.to_numeric(merged[OUT_COUNTRY], errors="coerce").astype("Int64")

    # ── Country: 1 = US, 2 = OUS ────────────────────────────────────────────
    merged[OUT_COUNTRY_US] = merged[OUT_COUNTRY].map(
        lambda x: 1 if x == 1 else (2 if pd.notna(x) else pd.NA)
    ).astype("Int64")

    # ── Other filter columns ─────────────────────────────────────────────────
    merged[OUT_ROLE]     = apply_map(merged[SURVEY_ROLE_COL].str.strip(),     ROLE_MAP,     SURVEY_ROLE_COL)
    merged[OUT_ADOPTER]  = apply_map(merged[SURVEY_ADOPTER_COL].str.strip(),  ADOPTER_MAP,  SURVEY_ADOPTER_COL)
    merged[OUT_BEDSIZE]  = apply_map(merged[SURVEY_BEDSIZE_COL].str.strip(),  BEDSIZE_MAP,  SURVEY_BEDSIZE_COL)
    merged[OUT_HOSPTYPE] = apply_map(merged[SURVEY_HOSPTYPE_COL].str.strip(), HOSPTYPE_MAP, SURVEY_HOSPTYPE_COL)

    ed_series = merged[SURVEY_ED_COL].fillna("").str.strip().str.lower()
    merged[OUT_ED] = ed_series.map(lambda x: 1 if x == "yes" else 2).astype("Int64")

    for col in [OUT_ROLE, OUT_ADOPTER, OUT_BEDSIZE, OUT_HOSPTYPE]:
        merged[col] = pd.to_numeric(merged[col], errors="coerce").astype("Int64")

    log(f"Merge and tagging complete: {len(merged):,} rows")

    vendor_counts = merged[SURVEY_VENDOR_COL].value_counts(dropna=False).to_dict()
    log(f"Vendor distribution: {vendor_counts}")

    return merged


# ────────────────────────────────────────
#  STEP 4 — Tag ED respondents from ED Roles file
#
#  BUG FIX: previously this function used Q4/Q5 survey text to infer
#  ED status, but the ED Roles file (ED_FILE) was never actually read
#  or used. ED_role is now derived purely from ResponseID membership
#  in the ED Roles file, which is the intended behaviour.
# ────────────────────────────────────────
def tag_ed_respondents(df: pd.DataFrame) -> pd.DataFrame:
    log_lines.append("\n[STEP 4]  Tag ED respondents from ED Roles file")
    print("\n[STEP 4]  Tagging ED respondents ...")

    if ED_FILE is None or not os.path.exists(str(ED_FILE)):
        log("ED file not configured or not found — setting all ED_role = 2", "WARN")
        df[OUT_ED_ROLE] = 2
        return df

    # Load ED file — supports both CSV and Excel
    ext = os.path.splitext(ED_FILE)[1].lower()
    if ext in (".xlsx", ".xls"):
        ed_df = pd.read_excel(ED_FILE, dtype=str)
    else:
        ed_df = pd.read_csv(ED_FILE, dtype=str, encoding="cp1252")

    # Strip the Qualtrics second header row if present
    if ed_df.shape[0] > 0 and str(ed_df.iloc[0].get(ED_FILE_ID_COL, "")).startswith("{"): 
        ed_df = ed_df.iloc[1:].reset_index(drop=True)

    check_col(ed_df, ED_FILE_ID_COL, "ED Roles file")

    ed_ids = set(ed_df[ED_FILE_ID_COL].str.strip().dropna())
    log(f"ED Roles file: {len(ed_ids):,} ResponseIDs loaded")

    df[CONJOINT_ID_COL] = df[CONJOINT_ID_COL].str.strip()
    df[OUT_ED_ROLE] = df[CONJOINT_ID_COL].isin(ed_ids).map({True: 1, False: 2}).astype("Int64")

    n_ed     = (df[OUT_ED_ROLE] == 1).sum()
    n_not_ed = (df[OUT_ED_ROLE] == 2).sum()
    log(f"{OUT_ED_ROLE}: {n_ed:,} ED respondents (1), {n_not_ed:,} non-ED (2)")

    # Warn if ED file IDs don't appear in the final dataset at all
    unmatched_ed = ed_ids - set(df[CONJOINT_ID_COL])
    if unmatched_ed:
        log(f"{len(unmatched_ed)} ED Roles ID(s) not found in dataset "
            f"(may have been removed as QA fails or not in conjoint):", "WARN")
        for rid in sorted(unmatched_ed):
            log(f"  not matched: {rid}", "WARN")

    return df


# ────────────────────────────────────────
#  STEP 5 — Remove QA failures
# ────────────────────────────────────────
def remove_qa_failures(df: pd.DataFrame) -> pd.DataFrame:
    log_lines.append("\n[STEP 5]  Remove QA failures")
    print("\n[STEP 5]  Removing QA failures ...")

    if QA_FAIL_FILE is None or not os.path.exists(str(QA_FAIL_FILE)):
        log("No QA failure file provided or file not found — skipping", "WARN")
        return df

    # Use the shared Qualtrics loader to handle the 2-row header consistently
    raw_fails = load_qualtrics_csv(QA_FAIL_FILE, "Fails file")
    check_col(raw_fails, QA_FAIL_ID_COL, "QA fails file")

    fail_ids = set(raw_fails[QA_FAIL_ID_COL].str.strip().dropna())
    log(f"{len(fail_ids):,} fail IDs loaded")

    print(f"\n  Fail IDs to be removed ({len(fail_ids)}):")
    for rid in sorted(fail_ids):
        print(f"    {rid}")

    df[CONJOINT_ID_COL] = df[CONJOINT_ID_COL].str.strip()
    before      = len(df)
    matched_ids = set(df[CONJOINT_ID_COL]).intersection(fail_ids)
    df          = df[~df[CONJOINT_ID_COL].isin(fail_ids)].copy()
    removed     = before - len(df)
    not_found   = fail_ids - matched_ids

    log(f"{removed:,} respondents removed ({before:,} → {len(df):,})")

    if not_found:
        log(f"{len(not_found)} fail ID(s) not found in dataset (already absent):", "WARN")
        for rid in sorted(not_found):
            log(f"  not matched: {rid}", "WARN")

    return df


# ────────────────────────────────────────
#  STEP 6 — Drop raw survey columns & save
#  vendor, pid, Q4, Q5 are kept in the output.
# ────────────────────────────────────────
def save_output(df: pd.DataFrame):
    log_lines.append("\n[STEP 6]  Save output")
    print("\n[STEP 6]  Saving output ...")

    # Drop the raw Qualtrics label columns that have been converted to coded
    # filter columns. vendor, pid, Q4, and Q5 are intentionally kept.
    drop_cols = [SURVEY_COUNTRY_COL, SURVEY_ROLE_COL,
                 SURVEY_ED_COL, SURVEY_ADOPTER_COL,
                 SURVEY_BEDSIZE_COL, SURVEY_HOSPTYPE_COL]
    df = df.drop(columns=[c for c in drop_cols if c in df.columns])

    df.to_csv(OUTPUT_FILE, index=False)
    log(f"Output saved → {OUTPUT_FILE}  ({len(df):,} rows, {len(df.columns)} columns)")

    print("\n  Filter column distributions:")
    for col in [OUT_COUNTRY, OUT_COUNTRY_US, OUT_ROLE, OUT_ED,
                OUT_ADOPTER, OUT_BEDSIZE, OUT_HOSPTYPE, OUT_ED_ROLE,
                SURVEY_VENDOR_COL]:
        if col in df.columns:
            counts = df[col].value_counts(dropna=False).sort_index().to_dict()
            print(f"    {col:12s}: {counts}")


# ────────────────────────────────────────
#  STEP 7 — Write log file
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

    conjoint = load_conjoint_files()           # Step 1: load conjoint (Sawtooth pre-filter)
    survey   = load_survey()                   # Step 2: load Qualtrics completes
    final    = merge_and_tag(conjoint, survey) # Step 3: inner-join to Completes allowlist + tag
    final    = tag_ed_respondents(final)       # Step 4: tag ED respondents from ED Roles file
    final    = remove_qa_failures(final)       # Step 5: remove QA fails
    save_output(final)                         # Step 6: drop raw cols & save
    write_log()                                # Step 7: write log

    print("\n" + "=" * 55)
    print("  PIPELINE COMPLETE")
    print("=" * 55 + "\n")