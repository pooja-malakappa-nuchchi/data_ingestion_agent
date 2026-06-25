# This file contains the exact operations for cleaning data.
# Each function takes a data table and some settings.
# It returns a new cleaned table and a simple message about what was done.
# We use these tools so the AI does not change the data directly — keeping all changes safe and auditable.
# strip_whitespace removes leading, trailing, and multiple internal spaces using regex.
# We also have a helper function to find text columns correctly.

import re
import pandas as pd
import numpy as np

def is_text_column(series):
    # This helper checks if a column contains text values.
    # It works with old and new versions of the table library.
    # We do this because text types can look different in newer software.
    return series.dtype == object or pd.api.types.is_string_dtype(series)

def drop_duplicates(df):
    # This tool removes rows that are exact copies of other rows.
    # It keeps only the first copy of each duplicate row.
    # We do this to clean up repeated information.
    initial_rows = len(df)
    new_df = df.drop_duplicates()
    removed = initial_rows - len(new_df)
    message = f"Removed {removed} duplicate rows."
    return new_df, message

def fill_missing(df, column, strategy, fill_value=None):
    # This tool fills in empty spaces in a column.
    # It can use the middle value, the average value, the most common value, or a set text.
    # We do this so that missing details do not break our analysis later.
    if column not in df.columns:
        return df, f"Column '{column}' not found."
    
    new_df = df.copy()
    series = new_df[column]
    
    if strategy == "mean":
        val = pd.to_numeric(series, errors='coerce').mean()
        strategy_desc = "average value"
    elif strategy == "median":
        val = pd.to_numeric(series, errors='coerce').median()
        strategy_desc = "middle value"
    elif strategy == "mode":
        mode_series = series.mode()
        val = mode_series.iloc[0] if not mode_series.empty else None
        strategy_desc = "most common value"
    elif strategy == "constant":
        val = fill_value if fill_value is not None else ""
        strategy_desc = f"fixed value '{val}'"
    else:
        return df, f"Unknown strategy '{strategy}'."
        
    if val is None or pd.isna(val):
        return df, f"Could not calculate fill value for '{column}' using strategy '{strategy}'."
        
    missing_count = series.isna().sum()
    new_df[column] = series.fillna(val)
    message = f"Filled {missing_count} missing values in '{column}' using {strategy_desc} ({val})."
    return new_df, message

def coerce_type(df, column, to):
    # This tool changes the type of data in a column.
    # It can change text into numbers, dates, or groups.
    # For numeric conversion, word-form numbers like "Seventy-Two Thousand" are converted first.
    # Any values that cannot be converted will become blank spaces.
    if column not in df.columns:
        return df, f"Column '{column}' not found."

    new_df = df.copy()
    series = new_df[column]
    initial_na = series.isna().sum()

    if to == "numeric":
        try:
            from word2number import w2n
            def try_parse(x):
                if isinstance(x, str):
                    try:
                        return w2n.word_to_num(x)
                    except Exception:
                        return x
                return x
            series = series.apply(try_parse)
        except ImportError:
            pass
        new_df[column] = pd.to_numeric(series, errors='coerce')
        desc = "numbers"
    elif to == "datetime":
        new_df[column] = pd.to_datetime(series, errors='coerce')
        desc = "dates"
    elif to == "category":
        new_df[column] = series.astype('category')
        desc = "groups"
    else:
        return df, f"Unknown target type '{to}'."
        
    final_na = new_df[column].isna().sum()
    new_blanks = final_na - initial_na
    message = f"Converted column '{column}' to {desc}. Created {new_blanks} new blank spaces from unconvertible values."
    return new_df, message

def strip_whitespace(df, column):
    # This tool removes spaces from the start, end, and collapses multiple internal spaces to one.
    # It only runs on columns that contain text.
    # We do this because extra spaces can cause matching errors.
    if column not in df.columns:
        return df, f"Column '{column}' not found."
        
    if not is_text_column(df[column]):
        return df, f"Column '{column}' is not a text column, skipping whitespace removal."
        
    new_df = df.copy()
    new_df[column] = df[column].apply(
        lambda x: re.sub(r' +', ' ', x.strip()) if isinstance(x, str) else x
    )

    message = f"Removed extra spaces from the start, end, and inside text in column '{column}'."
    return new_df, message

def standardize_text(df, column, mode):
    # This tool makes all text casing consistent.
    # It can change text to all lowercase or capitalize the first letter of each word.
    # We do this so that different capitalizations do not look like different words.
    if column not in df.columns:
        return df, f"Column '{column}' not found."
        
    if not is_text_column(df[column]):
        return df, f"Column '{column}' is not a text column."
        
    new_df = df.copy()
    if mode == "lower":
        new_df[column] = df[column].apply(lambda x: x.lower() if isinstance(x, str) else x)
        desc = "lowercase"
    elif mode == "title":
        new_df[column] = df[column].apply(lambda x: x.title() if isinstance(x, str) else x)
        desc = "title case"
    else:
        return df, f"Unknown mode '{mode}'."
        
    message = f"Standardized text casing in column '{column}' to {desc}."
    return new_df, message

def remove_outliers(df, column, method="iqr"):
    # This tool removes rows that have extreme numbers.
    # It uses the middle range to find values that are too high or too low.
    # We do this to stop unusual values from spoiling our analysis.
    if column not in df.columns:
        return df, f"Column '{column}' not found."
        
    series = pd.to_numeric(df[column], errors='coerce')
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    
    if pd.isna(iqr) or iqr == 0:
        return df, f"Could not calculate IQR for '{column}' (not enough numeric variation)."
        
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    
    mask = (series >= lower_bound) & (series <= upper_bound) | df[column].isna()
    new_df = df[mask]
    removed = len(df) - len(new_df)
    
    message = f"Removed {removed} rows with outliers in '{column}' using IQR method (bounds: {lower_bound:.2f} to {upper_bound:.2f})."
    return new_df, message

def drop_column(df, column):
    # This tool removes a column completely from the table.
    # We do this to get rid of columns that are not needed.
    if column not in df.columns:
        return df, f"Column '{column}' not found."
        
    new_df = df.drop(columns=[column])
    message = f"Dropped column '{column}'."
    return new_df, message

# A registry of tools that we can call by name.
CLEANING_TOOLS = {
    "drop_duplicates": drop_duplicates,
    "fill_missing": fill_missing,
    "coerce_type": coerce_type,
    "strip_whitespace": strip_whitespace,
    "standardize_text": standardize_text,
    "remove_outliers": remove_outliers,
    "drop_column": drop_column
}
