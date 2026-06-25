import pandas as pd
from agent.inspect import inspect_dataframe


def test_empty_dataframe_returns_no_issues():
    df = pd.DataFrame()
    issues = inspect_dataframe(df)
    assert issues == []

def test_zero_rows_returns_no_issues():
    df = pd.DataFrame({"name": [], "age": []})
    issues = inspect_dataframe(df)
    assert issues == []

# --- duplicate rows ---

def test_detects_duplicate_rows():
    df = pd.DataFrame({"name": ["Alice", "Alice"], "age": [25, 25]})
    issues = inspect_dataframe(df)
    types = [i["issue"] for i in issues]
    assert "duplicate_rows" in types

def test_no_duplicate_flag_when_rows_unique():
    df = pd.DataFrame({"name": ["Alice", "Bob"], "age": [25, 30]})
    issues = inspect_dataframe(df)
    types = [i["issue"] for i in issues]
    assert "duplicate_rows" not in types

# --- missing values ---

def test_detects_missing_values():
    df = pd.DataFrame({"age": [25, None, 30]})
    issues = inspect_dataframe(df)
    types = [i["issue"] for i in issues]
    assert "missing_values" in types

def test_no_missing_flag_when_column_complete():
    df = pd.DataFrame({"age": [25, 30, 35]})
    issues = inspect_dataframe(df)
    types = [i["issue"] for i in issues]
    assert "missing_values" not in types

# --- nearly empty ---

def test_detects_nearly_empty_column():
    df = pd.DataFrame({"notes": [None] * 95 + ["ok"] * 5})
    issues = inspect_dataframe(df)
    types = [i["issue"] for i in issues]
    assert "nearly_empty" in types

def test_nearly_empty_not_flagged_as_missing_values():
    df = pd.DataFrame({"notes": [None] * 95 + ["ok"] * 5})
    issues = inspect_dataframe(df)
    types = [i["issue"] for i in issues]
    assert "missing_values" not in types

def test_below_90pct_missing_flagged_as_missing_values():
    df = pd.DataFrame({"notes": [None] * 50 + ["ok"] * 50})
    issues = inspect_dataframe(df)
    types = [i["issue"] for i in issues]
    assert "missing_values" in types
    assert "nearly_empty" not in types

# --- whitespace ---

def test_detects_leading_whitespace():
    df = pd.DataFrame({"name": ["  Alice", "Bob"]})
    issues = inspect_dataframe(df)
    types = [i["issue"] for i in issues]
    assert "whitespace" in types

def test_detects_internal_double_spaces():
    df = pd.DataFrame({"city": ["New  York", "LA"]})
    issues = inspect_dataframe(df)
    types = [i["issue"] for i in issues]
    assert "whitespace" in types

def test_no_whitespace_flag_when_clean():
    df = pd.DataFrame({"name": ["Alice", "Bob"]})
    issues = inspect_dataframe(df)
    types = [i["issue"] for i in issues]
    assert "whitespace" not in types

# --- mixed case ---

def test_detects_mixed_case():
    df = pd.DataFrame({"city": ["New York", "new york", "NEW YORK"]})
    issues = inspect_dataframe(df)
    types = [i["issue"] for i in issues]
    assert "mixed_case" in types

def test_no_mixed_case_when_consistent():
    df = pd.DataFrame({"city": ["new york", "los angeles", "chicago"]})
    issues = inspect_dataframe(df)
    types = [i["issue"] for i in issues]
    assert "mixed_case" not in types

def test_skips_mixed_case_for_alphanumeric_codes():
    df = pd.DataFrame({"code": ["A10023f", "B20034g", "a10023f"]})
    issues = inspect_dataframe(df)
    types = [i["issue"] for i in issues]
    assert "mixed_case" not in types

# --- numbers stored as text ---

def test_detects_numbers_stored_as_text():
    df = pd.DataFrame({"salary": ["50000", "60000", "70000"]})
    issues = inspect_dataframe(df)
    types = [i["issue"] for i in issues]
    assert "numbers_stored_as_text" in types

def test_no_numbers_as_text_for_real_numeric_column():
    df = pd.DataFrame({"salary": [50000, 60000, 70000]})
    issues = inspect_dataframe(df)
    types = [i["issue"] for i in issues]
    assert "numbers_stored_as_text" not in types

# --- outliers ---

def test_detects_outliers():
    # repeated values keep unique_ratio below 0.9 so ID column skip does not trigger
    df = pd.DataFrame({"salary": [30000, 35000, 40000, 45000, 50000,
                                   30000, 35000, 40000, 45000, 9999999]})
    issues = inspect_dataframe(df)
    types = [i["issue"] for i in issues]
    assert "outliers" in types

def test_no_outlier_flag_for_normal_distribution():
    df = pd.DataFrame({"salary": [30000, 35000, 40000, 45000, 50000,
                                   30000, 35000, 40000, 45000, 50000]})
    issues = inspect_dataframe(df)
    types = [i["issue"] for i in issues]
    assert "outliers" not in types

def test_skips_outlier_check_for_id_columns():
    df = pd.DataFrame({"id": list(range(1000))})
    issues = inspect_dataframe(df)
    types = [i["issue"] for i in issues]
    assert "outliers" not in types
