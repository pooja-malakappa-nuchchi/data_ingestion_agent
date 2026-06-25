# This file creates a comprehensive messy dataset that exercises EVERY issue
# type the cleaning system can detect and fix, plus all three kinds of duplicates
# the pipeline is designed to catch.
#
# Column-level issue coverage (column -> issue -> tool that fixes it):
#   Customer_Name    whitespace + mixed_case        strip_whitespace + standardize_text
#   Product_Code     mixed-case alphanumeric code   NOT flagged (skipped on purpose)
#   City             internal double spaces         strip_whitespace
#   Department       mixed_case + missing_values    standardize_text + fill_missing(mode)
#   Salary           numbers_stored_as_text         coerce_type(numeric) + word2number
#   Order_Date       dates stored as text           coerce_type(datetime)  -- Gemini path only*
#   Rating           missing_values (numeric)       fill_missing(median)
#   Purchase_Amount  outliers (numeric)             remove_outliers(iqr)
#   Status           mixed_case + whitespace        strip_whitespace + standardize_text
#   Notes            nearly_empty (90%+ missing)    drop_column
#   Customer_ID      ID column                      no false outlier (values stay sequential)
#
# Duplicate coverage -- all three kinds the OP_ORDER is built to handle:
#   1. EXACT duplicate       identical row, caught directly by drop_duplicates
#   2. CASE-only duplicate    matches an anchor only AFTER standardize_text lowercases
#   3. WHITESPACE-only dup    matches an anchor only AFTER strip_whitespace trims
#   Cases 2 and 3 are why strip_whitespace and standardize_text MUST run before
#   drop_duplicates in OP_ORDER.
#
# * Pure date columns are only coerced by the Gemini plan. The fallback detects
#   dates inside the numbers_stored_as_text branch, which inspect.py only raises
#   for numeric-parseable columns, so the fallback will not coerce Order_Date by
#   itself. This is an intentional, documented gap, not a bug.

import os
import pandas as pd
import numpy as np


def generate_data():
    os.makedirs("data", exist_ok=True)

    # Each dict is one row. Comments mark the issue(s) that row carries.
    rows = [
        # ---- Anchor rows that get duplicated later (kept clean here) ----
        # ID 1001 -> gets an EXACT duplicate appended at the end
        {"Customer_ID": 1001, "Customer_Name": "Alice Smith", "Product_Code": "A10023F",
         "City": "New York", "Department": "Sales", "Salary": "55000",
         "Order_Date": "2024-01-15", "Rating": 4, "Purchase_Amount": 110,
         "Status": "active", "Notes": np.nan},
        # ID 1002 -> gets a CASE-only duplicate appended at the end
        {"Customer_ID": 1002, "Customer_Name": "Bob Jones", "Product_Code": "B20034G",
         "City": "Los Angeles", "Department": "Marketing", "Salary": "62000",
         "Order_Date": "2024-02-20", "Rating": 5, "Purchase_Amount": 100,
         "Status": "active", "Notes": np.nan},
        # ID 1003 -> gets a WHITESPACE-only duplicate appended at the end
        {"Customer_ID": 1003, "Customer_Name": "Charlie Day", "Product_Code": "C30045H",
         "City": "Chicago", "Department": "Engineering", "Salary": "85000",
         "Order_Date": "2024-03-10", "Rating": 3, "Purchase_Amount": 120,
         "Status": "inactive", "Notes": np.nan},

        # ---- Distinct rows carrying the column-level issues ----
        # lowercase name (mixed_case), missing Department, word-number Salary, lowercase code
        {"Customer_ID": 1004, "Customer_Name": "charlie brown", "Product_Code": "c30045h",
         "City": "Houston", "Department": np.nan, "Salary": "forty eight thousand",
         "Order_Date": "04-05-2024", "Rating": 4, "Purchase_Amount": 100,
         "Status": "active", "Notes": np.nan},
        # the ONLY Notes value -> Notes column ends up 90%+ empty (nearly_empty); uppercase Status
        {"Customer_ID": 1005, "Customer_Name": "Evan Wright", "Product_Code": "E50067J",
         "City": "Phoenix", "Department": "Engineering", "Salary": "90000",
         "Order_Date": "2024-05-18", "Rating": 5, "Purchase_Amount": 110,
         "Status": "ACTIVE", "Notes": "VIP customer"},
        # uppercase name (mixed_case), lowercase alphanumeric code (should NOT be flagged)
        {"Customer_ID": 1006, "Customer_Name": "FIONA GREEN", "Product_Code": "f60078k",
         "City": "New York", "Department": "Sales", "Salary": "53000",
         "Order_Date": "2024-06-22", "Rating": 3, "Purchase_Amount": 100,
         "Status": "inactive", "Notes": np.nan},
        # uppercase Department, word-number Salary, trailing-space Status
        {"Customer_ID": 1007, "Customer_Name": "George Hall", "Product_Code": "G70089L",
         "City": "Los Angeles", "Department": "MARKETING", "Salary": "Seventy-Two Thousand",
         "Order_Date": "2024-07-30", "Rating": 4, "Purchase_Amount": 120,
         "Status": "active  ", "Notes": np.nan},
        # internal double space in City, missing Rating
        {"Customer_ID": 1008, "Customer_Name": "Hannah Lee", "Product_Code": "H80090M",
         "City": "Chi  cago", "Department": "HR", "Salary": "60000",
         "Order_Date": "2024-08-14", "Rating": np.nan, "Purchase_Amount": 110,
         "Status": "active", "Notes": np.nan},
        # N/A Salary (unconvertible -> NaN -> filled by median), title-case Status
        {"Customer_ID": 1009, "Customer_Name": "Ian Malcolm", "Product_Code": "I90101N",
         "City": "Houston", "Department": "Engineering", "Salary": "N/A",
         "Order_Date": "2024-09-09", "Rating": 4, "Purchase_Amount": 120,
         "Status": "Inactive", "Notes": np.nan},
        # internal double space in City, lowercase Department
        {"Customer_ID": 1010, "Customer_Name": "Julia Roberts", "Product_Code": "J10112O",
         "City": "Phoe  nix", "Department": "sales", "Salary": "72000",
         "Order_Date": "2024-10-25", "Rating": 3, "Purchase_Amount": 100,
         "Status": "active", "Notes": np.nan},
        # leading/trailing whitespace in name, missing Rating
        {"Customer_ID": 1011, "Customer_Name": "  Karen Page  ", "Product_Code": "K11123P",
         "City": "Seattle", "Department": "Sales", "Salary": "58000",
         "Order_Date": "2024-11-02", "Rating": np.nan, "Purchase_Amount": 110,
         "Status": "active", "Notes": np.nan},
        # internal double space in City, missing Department
        {"Customer_ID": 1012, "Customer_Name": "Liam Neeson", "Product_Code": "L12134Q",
         "City": "San  Diego", "Department": np.nan, "Salary": "67000",
         "Order_Date": "2024-12-12", "Rating": 4, "Purchase_Amount": 120,
         "Status": "inactive", "Notes": np.nan},

        # ---- Outlier rows (Purchase_Amount is a genuine numeric column) ----
        # very HIGH purchase amount -> outlier
        {"Customer_ID": 1013, "Customer_Name": "Mona Lisa", "Product_Code": "M13145R",
         "City": "Boston", "Department": "Sales", "Salary": "61000",
         "Order_Date": "2024-04-19", "Rating": 5, "Purchase_Amount": 999999,
         "Status": "active", "Notes": np.nan},
        # very LOW purchase amount -> outlier
        {"Customer_ID": 1014, "Customer_Name": "Nina Simone", "Product_Code": "N14156S",
         "City": "Denver", "Department": "Marketing", "Salary": "59000",
         "Order_Date": "2024-03-28", "Rating": 2, "Purchase_Amount": 1,
         "Status": "inactive", "Notes": np.nan},
    ]

    df = pd.DataFrame(rows)

    # ---- Append the three kinds of duplicates ----
    # 1. EXACT duplicate of 1001 -> identical in every column, so inspect.py flags
    #    duplicate_rows immediately and drop_duplicates removes it directly.
    exact_dup = df[df["Customer_ID"] == 1001].copy()

    # 2. CASE-only duplicate of 1002 -> same row, name in a different case.
    #    NOT an exact match now, but becomes one AFTER standardize_text lowercases names.
    case_dup = df[df["Customer_ID"] == 1002].copy()
    case_dup["Customer_Name"] = "BOB JONES"

    # 3. WHITESPACE-only duplicate of 1003 -> same row, name padded with spaces.
    #    Becomes an exact match AFTER strip_whitespace trims the name.
    ws_dup = df[df["Customer_ID"] == 1003].copy()
    ws_dup["Customer_Name"] = "  Charlie Day  "

    messy_df = pd.concat([df, exact_dup, case_dup, ws_dup], ignore_index=True)

    messy_path = os.path.join("data", "messy_data_v2.csv")
    messy_df.to_csv(messy_path, index=False)

    print(f"Saved messy_data_v2.csv - {len(messy_df)} rows, {len(messy_df.columns)} columns")
    print("\nColumn-level issues injected:")
    print("  [whitespace]      Customer_Name (leading/trailing), City (internal double), Status (trailing)")
    print("  [mixed_case]      Customer_Name, Department, Status  (letters only - flagged)")
    print("  [skip mixed_case] Product_Code  (alphanumeric code - NOT flagged)")
    print("  [missing_values]  Department (text -> fill mode), Rating (numeric -> fill median)")
    print("  [nearly_empty]    Notes  (1 value of 17 -> 90%+ empty -> drop_column)")
    print("  [num_as_text]     Salary  (plain '55000', word-form, and 'N/A')")
    print("  [outliers]        Purchase_Amount  (999999 high, 1 low)")
    print("  [no false flag]   Customer_ID  (sequential IDs - no outlier flagged)")
    print("  [Gemini only]     Order_Date  (text dates - fallback does not auto-coerce dates)")
    print("\nDuplicate kinds injected (all three the pipeline handles):")
    print("  1. EXACT       copy of ID 1001 - caught directly by drop_duplicates")
    print("  2. CASE-only   'BOB JONES' of ID 1002 - matches only AFTER standardize_text")
    print("  3. WHITESPACE  '  Charlie Day  ' of ID 1003 - matches only AFTER strip_whitespace")


if __name__ == "__main__":
    generate_data()
