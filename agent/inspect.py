# This file inspects a data table to find potential problems.
# It uses only standard data rules with no AI models.
# It checks for duplicates, missing values, nearly empty columns, whitespace,
# mixed case, numbers stored as text, and outliers.
# Columns with 90%+ missing values are flagged separately as nearly_empty.
# Outlier checks are skipped for ID-like columns where 90%+ of values are unique.
# Each issue has a simple explanation of why it matters to the user.

import pandas as pd
import numpy as np
from agent.tools import is_text_column

def inspect_dataframe(df):
    # This function inspects the table and records all issues.
    # It checks for duplicates, nearly empty columns, missing values, whitespace,
    # mixed case, numbers stored as text, and outliers.
    # It returns a list of all issues with clear explanations.
    issues = []
    total_rows = len(df)
    
    if total_rows == 0:
        return issues
        
    # 1. Check for duplicate rows in the entire table
    duplicate_count = df.duplicated().sum()
    if duplicate_count > 0:
        issues.append({
            "column": None,
            "issue": "duplicate_rows",
            "detail": f"{duplicate_count} duplicate rows found out of {total_rows}.",
            "why": "Duplicate rows can skew statistical calculations and make counts inaccurate."
        })
        
    # Inspect each column individually
    for column in df.columns:
        series = df[column]
        
        # 2. Check for missing values in the column
        missing_count = series.isna().sum()
        if missing_count > 0:
            pct = (missing_count / total_rows) * 100
            if pct >= 90:
                issues.append({
                    "column": column,
                    "issue": "nearly_empty",
                    "detail": f"{missing_count} blank cells ({pct:.1f}% of column) — nearly all values are missing.",
                    "why": "Filling 90%+ of a column with estimated values fabricates data and corrupts analysis. Dropping is safer."
                })
            else:
                issues.append({
                    "column": column,
                    "issue": "missing_values",
                    "detail": f"{missing_count} blank cells ({pct:.1f}% of column).",
                    "why": "Blank fields can cause mathematical errors or lead to incomplete data analysis."
                })
            
        # 3. Check text columns for specific formatting issues
        if is_text_column(series):
            non_null_series = series.dropna()
            non_null_count = len(non_null_series)
            
            if non_null_count > 0:
                # Check for numbers saved as text
                coerced = pd.to_numeric(non_null_series, errors='coerce')
                parsed_count = coerced.notna().sum()
                
                if parsed_count > 0:
                    unparsed_count = non_null_count - parsed_count
                    if unparsed_count > 0 and (parsed_count / non_null_count) >= 0.5:
                        # Case A: Mostly numbers, but has some non-numeric text
                        issues.append({
                            "column": column,
                            "issue": "numbers_stored_as_text",
                            "detail": f"{unparsed_count} values could not be read as numbers in a column that is mostly numeric.",
                            "why": "Numbers stored as text prevent mathematical operations like sums or averages from working."
                        })
                    elif unparsed_count == 0:
                        # Case B: Completely numeric but typed as object/str
                        issues.append({
                            "column": column,
                            "issue": "numbers_stored_as_text",
                            "detail": "All values can be read as numbers, but the column is saved as text.",
                            "why": "Columns saved as text cannot be used for math until they are converted to numbers."
                        })
                
                # Check for leading, trailing, or multiple internal spaces
                has_space = non_null_series.apply(
                    lambda x: isinstance(x, str) and (x != x.strip() or '  ' in x)
                )
                space_count = has_space.sum()
                if space_count > 0:
                    issues.append({
                        "column": column,
                        "issue": "whitespace",
                        "detail": f"{space_count} values have extra spacing at the start, end, or inside.",
                        "why": "Hidden spaces can cause matching problems or make reports look messy."
                    })

                # Check for mixed case — same value in different capitalizations
                # Skip columns where any value contains digits mixed with letters (codes/IDs like A10023f)
                has_alphanumeric_codes = non_null_series.apply(
                    lambda x: isinstance(x, str) and any(c.isdigit() for c in x)
                ).any()
                if not has_alphanumeric_codes:
                    lowered = non_null_series.str.lower()
                    if lowered.nunique() < non_null_series.nunique():
                        issues.append({
                            "column": column,
                            "issue": "mixed_case",
                            "detail": f"Same values found in different capitalizations in '{column}'.",
                            "why": "Mixed casing makes identical values look different, causing incorrect duplicate detection and grouping errors."
                        })
                    
        # 4. Check numeric columns for outliers
        if pd.api.types.is_numeric_dtype(series):
            non_null_numeric = series.dropna()
            unique_ratio = non_null_numeric.nunique() / len(non_null_numeric) if len(non_null_numeric) > 0 else 0
            if unique_ratio > 0.9:
                continue
            if len(non_null_numeric) > 0:
                q1 = non_null_numeric.quantile(0.25)
                q3 = non_null_numeric.quantile(0.75)
                iqr = q3 - q1
                
                if iqr > 0:
                    lower_bound = q1 - 1.5 * iqr
                    upper_bound = q3 + 1.5 * iqr
                    
                    outliers = non_null_numeric[(non_null_numeric < lower_bound) | (non_null_numeric > upper_bound)]
                    outlier_count = len(outliers)
                    
                    if outlier_count > 0:
                        issues.append({
                            "column": column,
                            "issue": "outliers",
                            "detail": f"{outlier_count} values are outside normal bounds ({lower_bound:.2f} to {upper_bound:.2f}).",
                            "why": "Extreme values can distort averages and make chart scales hard to read."
                        })
                        
    return issues
