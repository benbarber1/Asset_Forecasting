from pathlib import Path
import pandas as pd
import numpy as np

core_dataset = r"C:\Users\bbarber\OneDrive - BGB Group\Documents\Modelling\Core Dataset\odd_grouped.xlsx"
df = pd.read_excel(core_dataset)

def revenue_per_group(df, indication_group=None):
    """
    Converts the long-format core dataset into a wide-format table with one row
    per drug and one column per year since launch, using USD revenues only.
    """

    df = df[df['revenue_usd'].notna()].copy()

    if indication_group is not None:
        df = df[df['Indication_Group'] == indication_group].copy()
        if df.empty:
            print(f"⚠️  No data found for indication group: '{indication_group}'")
            return None

    launch_years = (
        df[df['revenue_usd'] > 0]
        .groupby('Drug')['year']
        .min()
        .rename('launch_year')
    )
    df = df.merge(launch_years, on='Drug', how='left')

    df['year_since_launch'] = df['year'] - df['launch_year'] + 1
    df = df[df['year_since_launch'] >= 1]

    wide = df.pivot_table(
        index   = 'Drug',
        columns = 'year_since_launch',
        values  = 'revenue_usd',
        aggfunc = 'first'
    )
    wide.columns = [f'Year {int(col)}' for col in wide.columns]
    wide = wide.reset_index()

    metadata = (
        df.groupby('Drug')
        .agg(
            Indication_Group         = ('Indication_Group',       'first'),
            Indication               = ('Indication',             'first'),
            Company                  = ('Company or Companies',   'first'),
            Launch_Year              = ('launch_year',            'first'),
            Cumulative_Revenue_USD_m = ('revenue_usd',            'sum')
        )
        .reset_index()
    )

    result = metadata.merge(wide, on='Drug', how='left')

    year_cols  = sorted([c for c in result.columns if c.startswith('Year ')],
                        key=lambda x: int(x.split(' ')[1]))
    fixed_cols = [
        'Indication_Group', 'Indication', 'Drug', 'Company',
        'Launch_Year', 'Cumulative_Revenue_USD_m'
    ]
    result = result[fixed_cols + year_cols]
    result = result.sort_values(['Indication_Group', 'Drug']).reset_index(drop=True)

    print(f"✅ Table generated: {len(result)} drug(s) across "
          f"{result['Indication_Group'].nunique()} indication group(s)")

    return result


# ══════════════════════════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════════════════════════

result = revenue_per_group(df)

# ── Folder and file path ──────────────────────────────────────────────────────
output_folder = Path(r"C:\Users\bbarber\OneDrive - BGB Group\Documents\Modelling\Experimental")
output_folder.mkdir(parents=True, exist_ok=True)

output_file = output_folder / "Revenue Data Test.xlsx"

# ── Export to Excel ───────────────────────────────────────────────────────────
if result is not None:
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        result.to_excel(writer, sheet_name='All Groups', index=False)

    print(f"✅ Exported to: {output_file}")