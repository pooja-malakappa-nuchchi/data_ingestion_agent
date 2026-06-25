# This file runs the approved cleaning plan steps on the table.
# It applies each step one by one using the tool library.
# column is never passed to drop_duplicates since that tool operates on the whole table.
# Default params are applied if the AI forgets to include them.
# Each step is caught individually so a single failure does not stop the pipeline.
# It returns the updated table and a log of what happened.

import pandas as pd
from agent.tools import CLEANING_TOOLS

def apply_plan(df, plan_steps, approved_indices):
    # This function takes the table and runs only the approved steps.
    # It checks the approved indices to see if a step was checked by the user.
    # If a step is approved, it tries to execute it and logs the result.
    # If it is skipped or errors out, it logs that status instead.
    current_df = df.copy()
    execution_log = []
    
    for idx, step in enumerate(plan_steps):
        is_approved = idx in approved_indices
        
        step_info = {
            "op": step.op,
            "column": step.column,
            "params": step.params,
            "reason": step.reason,
            "status": "pending",
            "message": ""
        }
        
        if not is_approved:
            step_info["status"] = "skipped"
            step_info["message"] = "Skipped by the user."
            execution_log.append(step_info)
            continue
            
        tool_fn = CLEANING_TOOLS.get(step.op)
        if not tool_fn:
            step_info["status"] = "error"
            step_info["message"] = f"Cleaning tool '{step.op}' is not registered."
            execution_log.append(step_info)
            continue
            
        try:
            kwargs = {}
            if step.column is not None and step.op != "drop_duplicates":
                kwargs["column"] = step.column
            
            params = dict(step.params) if step.params else {}
            
            # Fallback to default parameters if the model forgets to supply them
            if step.op == "coerce_type" and "to" not in params:
                params["to"] = "numeric"
            elif step.op == "fill_missing" and "strategy" not in params:
                from agent.tools import is_text_column
                if step.column in current_df.columns and is_text_column(current_df[step.column]):
                    params["strategy"] = "mode"
                else:
                    params["strategy"] = "median"
            elif step.op == "standardize_text" and "mode" not in params:
                params["mode"] = "lower"
            elif step.op == "remove_outliers" and "method" not in params:
                params["method"] = "iqr"
                
            kwargs.update(params)
            step_info["params"] = params
                
            next_df, msg = tool_fn(current_df, **kwargs)
            current_df = next_df
            step_info["status"] = "applied"
            step_info["message"] = msg
            
        except Exception as e:
            # We catch any exception to avoid crashing the whole pipeline
            # This makes sure the rest of the cleaning plan can still run
            step_info["status"] = "error"
            step_info["message"] = f"Failed to execute step: {str(e)}"
            
        execution_log.append(step_info)
        
    return current_df, execution_log
