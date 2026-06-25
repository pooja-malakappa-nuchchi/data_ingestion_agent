# This file runs checks on the cleaned data to verify its quality.
# It checks for remaining duplicate rows, empty cells, and how many rows were lost.
# It reports a pass, warning, or failure status for each check.
# It includes a function to retry cleaning if a hard check fails.
# We do this to ensure the data is truly clean before the user downloads it.

import pandas as pd

def validate_data(raw_df, clean_df):
    # This function runs the quality checks on the cleaned table.
    # It returns status results for duplicate, missing, and row loss checks.
    # It also returns an overall pass flag.
    results = {}
    overall_pass = True
    
    # 1. Check for duplicates in the cleaned dataset
    dup_count = clean_df.duplicated().sum()
    if dup_count == 0:
        results["duplicates"] = {"status": "pass", "message": "No duplicate rows remain."}
    else:
        # Remaining duplicates is a hard failure that needs fixing
        results["duplicates"] = {"status": "fail", "message": f"{dup_count} duplicate rows remain in the cleaned data."}
        overall_pass = False
        
    # 2. Check for missing values in the cleaned dataset
    missing_count = clean_df.isna().sum().sum()
    if missing_count == 0:
        results["missing"] = {"status": "pass", "message": "No missing values remain."}
    else:
        # Missing values are a warning because users might choose to keep blanks
        results["missing"] = {"status": "warn", "message": f"{missing_count} blank cells remain in the cleaned data."}
        
    # 3. Check for row loss bounds
    raw_len = len(raw_df)
    clean_len = len(clean_df)
    if raw_len > 0:
        loss_pct = ((raw_len - clean_len) / raw_len) * 100
    else:
        loss_pct = 0.0
        
    if loss_pct > 30.0:
        # High row loss triggers a warning to alert the user
        results["row_loss"] = {"status": "warn", "message": f"High row loss: {loss_pct:.1f}% of rows were removed ({raw_len} -> {clean_len})."}
    elif loss_pct < 0:
        # Negative loss means rows were somehow added, which is a hard failure
        results["row_loss"] = {"status": "fail", "message": f"Cleaned table has more rows than raw table ({raw_len} -> {clean_len})."}
        overall_pass = False
    else:
        results["row_loss"] = {"status": "pass", "message": f"Row loss is within normal bounds: {loss_pct:.1f}% ({raw_len} -> {clean_len})."}
        
    return overall_pass, results

def run_with_self_correction(df, plan_steps, approved_indices, retry_cap=3):
    # This function applies the plan and checks if the output is valid.
    # If duplicates remain (a failure), it adds a deduplication step and retries.
    # It does this up to the retry cap to ensure we do not loop forever.
    from agent.apply import apply_plan
    from agent.propose import CleaningStep
    
    current_steps = list(plan_steps)
    current_approved = set(approved_indices)
    
    attempt = 0
    clean_df = df.copy()
    execution_log = []
    validation_results = {}
    
    while attempt < retry_cap:
        clean_df, execution_log = apply_plan(df, current_steps, current_approved)
        overall_pass, validation_results = validate_data(df, clean_df)
        
        # If the duplicate check passes, we can exit early
        if validation_results["duplicates"]["status"] == "pass":
            return clean_df, execution_log, validation_results, attempt + 1
            
        # If duplicates failed, we insert a drop_duplicates step at the start and retry
        dup_status = validation_results["duplicates"]["status"]
        if dup_status == "fail":
            has_dup_step = any(step.op == "drop_duplicates" for idx, step in enumerate(current_steps) if idx in current_approved)
            if not has_dup_step:
                new_step = CleaningStep(
                    op="drop_duplicates",
                    column=None,
                    params={},
                    reason="Self-correction: Automatically added to remove remaining duplicates."
                )
                current_steps.insert(0, new_step)
                current_approved = {idx + 1 for idx in current_approved}
                current_approved.add(0)
            else:
                # If we already tried it and failed, we break to avoid looping forever
                break
                
        attempt += 1
        
    # Run one final apply if we hit the retry limit
    clean_df, execution_log = apply_plan(df, current_steps, current_approved)
    overall_pass, validation_results = validate_data(df, clean_df)
    return clean_df, execution_log, validation_results, attempt
