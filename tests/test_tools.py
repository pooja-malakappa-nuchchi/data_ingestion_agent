import pytest
import pandas as pd
from agent.tools import (
    drop_duplicates, fill_missing, coerce_type,
    strip_whitespace, standardize_text, remove_outliers, drop_column
)

# --- drop_duplicates ---

def test_drop_duplicates_removes_exact_copies():
    df = pd.DataFrame({"name": ["Alice", "Alice", "Bob"], "age": [25, 25, 30]})
    result, msg = drop_duplicates(df)
    assert len(result) == 2

def test_drop_duplicates_keeps_unique_rows():
    df = pd.DataFrame({"name": ["Alice", "Bob"], "age": [25, 30]})
    result, msg = drop_duplicates(df)
    assert len(result) == 2

def test_drop_duplicates_message_shows_count():
    df = pd.DataFrame({"name": ["Alice", "Alice", "Bob"], "age": [25, 25, 30]})
    result, msg = drop_duplicates(df)
    assert "1" in msg

# --- fill_missing ---

def test_fill_missing_median():
    df = pd.DataFrame({"salary": [10000, 20000, 30000, None]})
    result, msg = fill_missing(df, "salary", "median")
    assert result["salary"].isna().sum() == 0
    assert result["salary"].iloc[3] == 20000.0

def test_fill_missing_mean():
    df = pd.DataFrame({"salary": [10000.0, 20000.0, 30000.0, None]})
    result, msg = fill_missing(df, "salary", "mean")
    assert result["salary"].isna().sum() == 0
    assert result["salary"].iloc[3] == 20000.0

def test_fill_missing_mode():
    df = pd.DataFrame({"city": ["NYC", "NYC", "LA", None]})
    result, msg = fill_missing(df, "city", "mode")
    assert result["city"].iloc[3] == "NYC"

def test_fill_missing_constant():
    df = pd.DataFrame({"notes": [None, "ok"]})
    result, msg = fill_missing(df, "notes", "constant", fill_value="unknown")
    assert result["notes"].iloc[0] == "unknown"

def test_fill_missing_column_not_found():
    df = pd.DataFrame({"name": ["Alice"]})
    result, msg = fill_missing(df, "nonexistent", "median")
    assert "not found" in msg

def test_fill_missing_unknown_strategy():
    df = pd.DataFrame({"salary": [10000, None]})
    result, msg = fill_missing(df, "salary", "invalid_strategy")
    assert "Unknown strategy" in msg

# --- coerce_type ---

def test_coerce_type_numeric():
    df = pd.DataFrame({"salary": ["50000", "60000", "70000"]})
    result, msg = coerce_type(df, "salary", "numeric")
    assert pd.api.types.is_numeric_dtype(result["salary"])

def test_coerce_type_word_numbers():
    df = pd.DataFrame({"salary": ["Seventy-Two Thousand", "50000"]})
    result, msg = coerce_type(df, "salary", "numeric")
    assert result["salary"].iloc[0] == 72000

def test_coerce_type_datetime():
    df = pd.DataFrame({"date": ["2024-01-15", "2024-02-20"]})
    result, msg = coerce_type(df, "date", "datetime")
    assert pd.api.types.is_datetime64_any_dtype(result["date"])

def test_coerce_type_invalid_text_becomes_nan():
    df = pd.DataFrame({"salary": ["not_a_number", "50000"]})
    result, msg = coerce_type(df, "salary", "numeric")
    assert pd.isna(result["salary"].iloc[0])

def test_coerce_type_unknown_target():
    df = pd.DataFrame({"salary": ["50000"]})
    result, msg = coerce_type(df, "salary", "unknown_type")
    assert "Unknown target type" in msg

def test_coerce_type_column_not_found():
    df = pd.DataFrame({"name": ["Alice"]})
    result, msg = coerce_type(df, "nonexistent", "numeric")
    assert "not found" in msg

# --- strip_whitespace ---

def test_strip_whitespace_leading_trailing():
    df = pd.DataFrame({"name": ["  Alice  ", "Bob"]})
    result, msg = strip_whitespace(df, "name")
    assert result["name"].iloc[0] == "Alice"

def test_strip_whitespace_internal_spaces():
    df = pd.DataFrame({"city": ["New    York", "Los Angeles"]})
    result, msg = strip_whitespace(df, "city")
    assert result["city"].iloc[0] == "New York"

def test_strip_whitespace_no_change_needed():
    df = pd.DataFrame({"name": ["Alice", "Bob"]})
    result, msg = strip_whitespace(df, "name")
    assert result["name"].tolist() == ["Alice", "Bob"]

def test_strip_whitespace_column_not_found():
    df = pd.DataFrame({"name": ["Alice"]})
    result, msg = strip_whitespace(df, "nonexistent")
    assert "not found" in msg

def test_strip_whitespace_skips_numeric_column():
    df = pd.DataFrame({"salary": [50000, 60000]})
    result, msg = strip_whitespace(df, "salary")
    assert "not a text column" in msg

# --- standardize_text ---

def test_standardize_text_lower():
    df = pd.DataFrame({"name": ["Alice", "ALICE", "aLiCe"]})
    result, msg = standardize_text(df, "name", "lower")
    assert result["name"].tolist() == ["alice", "alice", "alice"]

def test_standardize_text_title():
    df = pd.DataFrame({"name": ["alice smith", "BOB JONES"]})
    result, msg = standardize_text(df, "name", "title")
    assert result["name"].iloc[0] == "Alice Smith"
    assert result["name"].iloc[1] == "Bob Jones"

def test_standardize_text_unknown_mode():
    df = pd.DataFrame({"name": ["Alice"]})
    result, msg = standardize_text(df, "name", "unknown_mode")
    assert "Unknown mode" in msg

def test_standardize_text_column_not_found():
    df = pd.DataFrame({"name": ["Alice"]})
    result, msg = standardize_text(df, "nonexistent", "lower")
    assert "not found" in msg

# --- remove_outliers ---

def test_remove_outliers_removes_extremes():
    df = pd.DataFrame({"salary": [30000, 35000, 40000, 45000, 50000, 9999999]})
    result, msg = remove_outliers(df, "salary")
    assert len(result) < len(df)
    assert 9999999 not in result["salary"].values

def test_remove_outliers_keeps_normal_values():
    df = pd.DataFrame({"salary": [30000, 35000, 40000, 45000, 50000, 9999999]})
    result, msg = remove_outliers(df, "salary")
    assert 30000 in result["salary"].values

def test_remove_outliers_column_not_found():
    df = pd.DataFrame({"name": ["Alice"]})
    result, msg = remove_outliers(df, "nonexistent")
    assert "not found" in msg

def test_remove_outliers_no_variation():
    df = pd.DataFrame({"salary": [50000, 50000, 50000]})
    result, msg = remove_outliers(df, "salary")
    assert "not enough numeric variation" in msg

# --- drop_column ---

def test_drop_column_removes_column():
    df = pd.DataFrame({"name": ["Alice"], "id": [1]})
    result, msg = drop_column(df, "id")
    assert "id" not in result.columns

def test_drop_column_keeps_other_columns():
    df = pd.DataFrame({"name": ["Alice"], "id": [1]})
    result, msg = drop_column(df, "id")
    assert "name" in result.columns

def test_drop_column_not_found():
    df = pd.DataFrame({"name": ["Alice"]})
    result, msg = drop_column(df, "nonexistent")
    assert "not found" in msg
