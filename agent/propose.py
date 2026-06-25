# This file suggests a list of cleaning steps for a data table.
# It uses Pydantic to structure the cleaning plan steps.
# The fallback rules handle: duplicate_rows, whitespace, mixed_case,
# numbers_stored_as_text (with date detection), nearly_empty, missing_values, and outliers.
# Execution order is enforced via OP_ORDER — standardize and strip run before dedup
# so that Alice/alice duplicates are correctly caught after case normalization.
# The Gemini function uses structured output via response_schema to return a validated plan.
# If Gemini fails, the system falls back to rule-based planning automatically.

import os
import pandas as pd
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

DATE_FORMATS = [
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%m-%d-%Y",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d.%m.%Y",
    "%Y.%m.%d",
    "%d %b %Y",
    "%b %d, %Y",
]

def looks_like_date(series):
    sample = series.dropna().head(10)
    if len(sample) == 0:
        return False
    for fmt in DATE_FORMATS:
        try:
            parsed = sample.apply(lambda x: pd.to_datetime(x, format=fmt, errors='coerce'))
            if parsed.notna().sum() / len(sample) >= 0.8:
                return True
        except Exception:
            continue
    return False

# Define the structure of a single cleaning step
class CleaningStep(BaseModel):
    op: str = Field(description="The name of the operation from the toolset")
    column: Optional[str] = Field(None, description="The name of the column to clean, or None for the whole table")
    params: Dict[str, Any] = Field(default_factory=dict, description="Settings and options for the operation")
    reason: str = Field(description="A brief explanation of why this step is recommended")

# Define the structure of the entire cleaning plan
class CleaningPlan(BaseModel):
    steps: List[CleaningStep] = Field(description="The ordered list of cleaning steps")

# Sorting priorities for the cleaning operations
# Standardize text and strip whitespace first so duplicates are caught correctly after case normalization
OP_ORDER = {
    "strip_whitespace": 1,
    "standardize_text": 2,
    "drop_duplicates": 3,
    "coerce_type": 4,
    "remove_outliers": 5,
    "fill_missing": 6,
    "drop_column": 7
}

def propose_plan_fallback(df, issues):
    # This is a rule-based fallback when no AI is used.
    # It maps each detected issue type to a specific cleaning action.
    # nearly_empty columns are dropped instead of filled to avoid fabricating data.
    # numbers_stored_as_text checks for date formats before deciding numeric vs datetime.
    # Steps are deduplicated and sorted by OP_ORDER before returning.
    steps = []
    
    for issue in issues:
        col = issue["column"]
        iss_type = issue["issue"]
        
        if iss_type == "duplicate_rows":
            steps.append(CleaningStep(
                op="drop_duplicates",
                column=None,
                params={},
                reason="Remove repeated rows to make sure counts and statistics are accurate."
            ))
            
        elif iss_type == "whitespace":
            steps.append(CleaningStep(
                op="strip_whitespace",
                column=col,
                params={},
                reason=f"Remove hidden spaces in '{col}' to prevent matching and typing errors."
            ))

        elif iss_type == "mixed_case":
            steps.append(CleaningStep(
                op="standardize_text",
                column=col,
                params={"mode": "lower"},
                reason=f"Standardize casing in '{col}' so Alice, alice, ALicE are all treated as the same value."
            ))
            
        elif iss_type == "numbers_stored_as_text":
            if col in df.columns and looks_like_date(df[col]):
                steps.append(CleaningStep(
                    op="coerce_type",
                    column=col,
                    params={"to": "datetime"},
                    reason=f"Convert '{col}' to a date type so date operations like sorting and filtering work correctly."
                ))
            else:
                steps.append(CleaningStep(
                    op="coerce_type",
                    column=col,
                    params={"to": "numeric"},
                    reason=f"Convert '{col}' to a numeric type so we can perform math operations."
                ))
                steps.append(CleaningStep(
                    op="fill_missing",
                    column=col,
                    params={"strategy": "median"},
                    reason=f"Fill empty spaces in '{col}' created by conversion with the middle value."
                ))
            
        elif iss_type == "nearly_empty":
            steps.append(CleaningStep(
                op="drop_column",
                column=col,
                params={},
                reason=f"'{col}' is 90%+ empty — filling this many blanks fabricates data. Dropping the column is safer."
            ))

        elif iss_type == "missing_values":
            from agent.tools import is_text_column
            if col in df.columns:
                if is_text_column(df[col]):
                    steps.append(CleaningStep(
                        op="fill_missing",
                        column=col,
                        params={"strategy": "mode"},
                        reason=f"Fill empty cells in '{col}' with the most common word."
                    ))
                else:
                    steps.append(CleaningStep(
                        op="fill_missing",
                        column=col,
                        params={"strategy": "median"},
                        reason=f"Fill empty cells in '{col}' with the middle numeric value."
                    ))
                    
        elif iss_type == "outliers":
            steps.append(CleaningStep(
                op="remove_outliers",
                column=col,
                params={"method": "iqr"},
                reason=f"Remove row outliers in '{col}' to prevent extreme values from skewing statistics."
            ))
            
    # Remove exact duplicate steps if they were added more than once
    unique_steps = []
    seen = set()
    for s in steps:
        key = (s.op, s.column, str(sorted(s.params.items())))
        if key not in seen:
            seen.add(key)
            unique_steps.append(s)
            
    # Sort the steps based on the defined execution order
    unique_steps.sort(key=lambda s: OP_ORDER.get(s.op, 99))
    
    return CleaningPlan(steps=unique_steps)

def remove_additional_properties(schema):
    # This helper removes the additionalProperties key from Pydantic schemas.
    # We do this because the free Gemini Developer API does not allow this key.
    if isinstance(schema, dict):
        schema.pop("additionalProperties", None)
        for key, val in list(schema.items()):
            remove_additional_properties(val)
    elif isinstance(schema, list):
        for item in schema:
            remove_additional_properties(item)
    return schema

def propose_plan_gemini(df, issues):
    # This function calls the Google Gemini API to build a plan.
    # It reads your Google Gemini API key from the environment.
    # It sends the issues list and requests a structured JSON response.
    # We do this to get smart AI plans for free.
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key.startswith("your-"):
        raise ValueError("Google Gemini API key is not configured in .env file.")
        
    from google import genai
    from google.genai import types
    import json
    
    client = genai.Client(api_key=api_key)
    
    # Generate the JSON schema from Pydantic and clean it
    schema_dict = CleaningPlan.model_json_schema()
    schema_dict = remove_additional_properties(schema_dict)
    
    summary = f"Columns: {list(df.columns)}\nRows: {len(df)}\nIssues detected: {issues}"
    
    prompt = f"""
    You are an expert data cleaning agent.
    Analyze the following dataset issues and propose an ordered cleaning plan.
    
    You MUST provide parameter arguments inside the 'params' dictionary for each step:
    - For 'coerce_type', you must include the key 'to' with value 'numeric', 'datetime', or 'category'.
    - For 'fill_missing', you must include the key 'strategy' with value 'mean', 'median', 'mode', or 'constant'.
    - For 'standardize_text', you must include the key 'mode' with value 'lower' or 'title'.
    - For 'remove_outliers', you must include the key 'method' with value 'iqr'.
    
    Only use operations from this list:
    - drop_duplicates (empty params)
    - fill_missing
    - coerce_type
    - strip_whitespace (empty params)
    - standardize_text
    - remove_outliers
    - drop_column (empty params)
    
    Dataset details:
    {summary}
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction="You are a professional data cleaning assistant that generates structured cleaning plans.",
            response_mime_type="application/json",
            response_schema=schema_dict,
        ),
    )
    
    # Parse the response text as JSON and validate it against Pydantic
    data = json.loads(response.text)
    return CleaningPlan.model_validate(data)


def propose_plan_llm(df, issues):
    # This is a hook where you can connect your LangGraph or OpenAI agent.
    # It reads your API key and asks the model to think about the data problems.
    # It uses structured outputs to return a clean list of steps.
    # You can customize this function to implement your custom logic.
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("your-"):
        raise ValueError("OpenAI API key is not configured in .env file.")
        
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    
    summary = f"Columns: {list(df.columns)}\nRows: {len(df)}\nIssues detected: {issues}"
    
    prompt = f"""
    You are an expert data cleaning agent.
    Analyze the following dataset issues and propose an ordered cleaning plan.
    
    You MUST provide parameter arguments inside the 'params' dictionary for each step:
    - For 'coerce_type', you must include the key 'to' with value 'numeric', 'datetime', or 'category'.
    - For 'fill_missing', you must include the key 'strategy' with value 'mean', 'median', 'mode', or 'constant'.
    - For 'standardize_text', you must include the key 'mode' with value 'lower' or 'title'.
    - For 'remove_outliers', you must include the key 'method' with value 'iqr'.
    
    Only use operations from this list:
    - drop_duplicates (empty params)
    - fill_missing
    - coerce_type
    - strip_whitespace (empty params)
    - standardize_text
    - remove_outliers
    - drop_column (empty params)
    
    Dataset details:
    {summary}
    """
    
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a professional data cleaning assistant that generates structured cleaning plans."},
            {"role": "user", "content": prompt}
        ],
        response_format=CleaningPlan,
    )
    
    return completion.choices[0].message.parsed

def propose_plan(df, issues, force_fallback=False):
    # This is the main function called by the application.
    # It tries to run the LLM reasoning first if allowed.
    # If the LLM fails or is disabled, it falls back to the rules.
    # Returns a tuple of (CleaningPlan, warning_message) so the UI can show failures.
    if force_fallback:
        return propose_plan_fallback(df, issues), None

    load_dotenv()
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    warning_message = None

    # Try Google Gemini first since it is free
    if gemini_key and not gemini_key.startswith("your-"):
        try:
            return propose_plan_gemini(df, issues), None
        except Exception as e:
            warning_message = f"Gemini failed: {e}. Falling back to rule-based plan."
            print(warning_message)

    # Try OpenAI next
    if openai_key and not openai_key.startswith("your-"):
        try:
            return propose_plan_llm(df, issues), None
        except Exception as e:
            warning_message = f"OpenAI failed: {e}. Falling back to rule-based plan."
            print(warning_message)

    # If all AI models fail or are not set up, run the fallback rules
    return propose_plan_fallback(df, issues), warning_message
