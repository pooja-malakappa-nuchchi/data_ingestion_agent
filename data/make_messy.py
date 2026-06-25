# This file creates test data with deliberate mistakes.
# It generates a clean list of workers first.
# It then copies that list and mixes in different errors.
# The errors include empty spaces, duplicated rows, and bad numbers.
# We do this so we can test if our cleaning agent finds and fixes every error.

import os
import pandas as pd
import numpy as np

def generate_data():
    # This function creates both clean and messy datasets.
    # It saves them as CSV files inside the data folder.
    # We do this so the user has an immediate file to upload and test.
    os.makedirs("data", exist_ok=True)
    
    # 1. Create a clean dataset of employees
    clean_records = [
        {"Employee_ID": 101, "Name": "Alice Smith", "Department": "Sales", "Salary": 55000, "Hire_Date": "2020-01-15"},
        {"Employee_ID": 102, "Name": "Bob Jones", "Department": "Marketing", "Salary": 62000, "Hire_Date": "2019-05-12"},
        {"Employee_ID": 103, "Name": "Charlie Brown", "Department": "Engineering", "Salary": 85000, "Hire_Date": "2021-03-22"},
        {"Employee_ID": 104, "Name": "Diana Prince", "Department": "Human Resources", "Salary": 58000, "Hire_Date": "2018-11-01"},
        {"Employee_ID": 105, "Name": "Evan Wright", "Department": "Engineering", "Salary": 90000, "Hire_Date": "2022-07-19"},
        {"Employee_ID": 106, "Name": "Fiona Gallagher", "Department": "Sales", "Salary": 53000, "Hire_Date": "2020-10-10"},
        {"Employee_ID": 107, "Name": "George Costanza", "Department": "Marketing", "Salary": 48000, "Hire_Date": "2015-04-01"},
        {"Employee_ID": 108, "Name": "Hannah Abbott", "Department": "Human Resources", "Salary": 60000, "Hire_Date": "2021-08-30"},
        {"Employee_ID": 109, "Name": "Ian Malcolm", "Department": "Engineering", "Salary": 95000, "Hire_Date": "2017-06-15"},
        {"Employee_ID": 110, "Name": "Julia Roberts", "Department": "Sales", "Salary": 72000, "Hire_Date": "2016-12-25"}
    ]
    
    clean_df = pd.DataFrame(clean_records)
    clean_path = os.path.join("data", "clean_data.csv")
    clean_df.to_csv(clean_path, index=False)
    print(f"Saved clean test data to {clean_path}")
    
    # 2. Create the messy dataset by copying and injecting errors
    messy_df = clean_df.copy()
    
    # Convert columns to objects to allow injecting mixed types
    messy_df["Salary"] = messy_df["Salary"].astype(object)
    messy_df["Department"] = messy_df["Department"].astype(object)
    messy_df["Name"] = messy_df["Name"].astype(object)
    
    # Inject whitespace and bad casing
    messy_df.at[0, "Name"] = "  Alice Smith"
    messy_df.at[1, "Department"] = "marketing"
    messy_df.at[5, "Department"] = "Sales  "
    messy_df.at[6, "Department"] = "MARKETING"
    messy_df.at[7, "Name"] = "Hannah Abbott  "
    
    # Inject missing values
    messy_df.at[2, "Salary"] = np.nan
    messy_df.at[3, "Department"] = np.nan
    messy_df.at[8, "Hire_Date"] = np.nan
    
    # Inject text into numeric columns (numbers stored as text / unconvertible text)
    messy_df.at[4, "Salary"] = "N/A"
    messy_df.at[9, "Salary"] = "Seventy-Two Thousand"
    
    # Inject duplicate rows
    duplicate_rows = messy_df.iloc[[0, 1, 5]]
    messy_df = pd.concat([messy_df, duplicate_rows], ignore_index=True)
    
    # Inject outliers in Salary
    outlier_row_1 = pd.DataFrame([{"Employee_ID": 999, "Name": "Rich Uncle", "Department": "Executive", "Salary": 1500000, "Hire_Date": "2010-01-01"}])
    outlier_row_2 = pd.DataFrame([{"Employee_ID": -99, "Name": "Underpaid Intern", "Department": "Marketing", "Salary": 10, "Hire_Date": "2023-01-01"}])
    messy_df = pd.concat([messy_df, outlier_row_1, outlier_row_2], ignore_index=True)
    
    messy_path = os.path.join("data", "messy_data.csv")
    messy_df.to_csv(messy_path, index=False)
    print(f"Saved messy test data to {messy_path}")

if __name__ == "__main__":
    generate_data()
