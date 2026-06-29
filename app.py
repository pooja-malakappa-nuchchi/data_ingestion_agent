# This file is the main web dashboard for our cleaning system.
# It uses the Streamlit library to show all buttons and charts.
# It manages the steps of loading data, viewing errors, and cleaning.
# It uses memory slots to keep the data from resetting when buttons are clicked.
# The AI checkbox defaults to False — all checkboxes for cleaning steps default to False too.
# The plan is regenerated whenever the AI checkbox is toggled to reflect the correct mode.
# We do this to give the user a simple, interactive way to clean their files.

import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv

# Import our custom agent modules
from agent.inspect import inspect_dataframe
from agent.propose import propose_plan
from agent.apply import apply_plan
from agent.validate import validate_data, run_with_self_correction
from agent.compare import create_comparison_excel

# Load environment configuration
load_dotenv()

# Page configuration for premium styling
st.set_page_config(
    page_title="CleanSweep | Data-Cleaning Agent",
    page_icon="🧼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for enhanced aesthetics
st.markdown("""
<style>
    .main-title {
        font-size: 2.5rem;
        color: #1F4E79;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        font-size: 1.1rem;
        color: #555555;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #F8F9FA;
        border-radius: 8px;
        padding: 1rem;
        border: 1px solid #E9ECEF;
        text-align: center;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1F4E79;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #6C757D;
    }
    .status-badge {
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-pass { background-color: #D4EDDA; color: #155724; }
    .badge-warn { background-color: #FFF3CD; color: #856404; }
    .badge-fail { background-color: #F8D7DA; color: #721C24; }
</style>
""", unsafe_allow_html=True)

# Helper function to reset application memory
def reset_cleaning_state():
    # This helper clears previous data from memory when a new file is uploaded.
    # We do this to ensure we do not show old reports for a new file.
    for key in ["raw_df", "issues", "plan", "cleaned_df", "execution_log", "validation_results", "validation_overall", "retry_count"]:
        if key in st.session_state:
            st.session_state[key] = None

# Header block
st.markdown('<div class="main-title">🧼 CleanSweep</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">A smart data-cleaning agent that reasons about issues and executes safe, deterministic code.</div>', unsafe_allow_html=True)

# Sidebar controls
st.sidebar.header("📁 Import Dataset")
uploaded_file = st.sidebar.file_uploader("Upload a messy CSV file", type=["csv"])

# Detect file change to reset the cleaning state
if uploaded_file:
    # Check file size (limit to 200MB)
    if uploaded_file.size > 200 * 1024 * 1024:
        st.error("File is too large! Please upload a file smaller than 200MB.")
        st.stop()
        
    current_file_id = uploaded_file.file_id
    if "last_file_id" not in st.session_state or st.session_state.last_file_id != current_file_id:
        reset_cleaning_state()
        st.session_state.last_file_id = current_file_id

st.sidebar.markdown("---")
st.sidebar.header("🤖 Reasoning Settings")
use_llm = st.sidebar.checkbox("Use AI Reasoning (Gemini / OpenAI)", value=False, help="Uses Google Gemini or OpenAI GPT to decide how to clean. Requires GEMINI_API_KEY or OPENAI_API_KEY in .env.")

# Check for API key if user enabled LLM
if use_llm:
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    has_gemini = gemini_key and not gemini_key.startswith("your-")
    has_openai = openai_key and not openai_key.startswith("your-")
    
    if not has_gemini and not has_openai:
        st.sidebar.warning("⚠️ No AI API key configured in .env. Falling back to rules.")
    elif has_gemini:
        st.sidebar.success("✅ Google Gemini API key active.")
    elif has_openai:
        st.sidebar.success("✅ OpenAI API key active.")

# Main Application Flow
if uploaded_file is not None:
    # 1. Load Raw Data
    if "raw_df" not in st.session_state or st.session_state.raw_df is None:
        try:
            # Load raw data and preserve original formats where possible
            st.session_state.raw_df = pd.read_csv(uploaded_file)
        except Exception as e:
            st.error(f"Error reading the CSV file: {e}")
            st.stop()
            
    raw_df = st.session_state.raw_df
    
    # 2. Inspect Raw Data
    if "issues" not in st.session_state or st.session_state.issues is None:
        with st.spinner("Analyzing dataset anomalies..."):
            st.session_state.issues = inspect_dataframe(raw_df)
            
    issues = st.session_state.issues
    
    # Show dataset quick metrics in sidebar
    st.sidebar.markdown("---")
    st.sidebar.header("📊 Dataset Overview")
    st.sidebar.markdown(f"**Total Rows:** {len(raw_df)}")
    st.sidebar.markdown(f"**Total Columns:** {len(raw_df.columns)}")
    st.sidebar.markdown(f"**Detected Issues:** {len(issues)}")
    
    # 3. Propose Plan
    if "plan" not in st.session_state or st.session_state.plan is None \
            or st.session_state.get("last_use_llm") != use_llm:
        with st.spinner("Generating cleaning plan..."):
            plan_result, plan_warning = propose_plan(raw_df, issues, force_fallback=not use_llm)
            st.session_state.plan = plan_result
            st.session_state.plan_warning = plan_warning
            st.session_state.last_use_llm = use_llm

    if st.session_state.get("plan_warning"):
        st.warning(f"⚠️ {st.session_state.plan_warning}")

    plan = st.session_state.plan
    
    # Display raw data preview and issue report
    col_left, col_right = st.columns([3, 2])
    
    with col_left:
        st.subheader("Raw Data Preview")
        st.dataframe(raw_df.head(10), use_container_width=True)
        
    with col_right:
        st.subheader("Detected Anomalies")
        if len(issues) == 0:
            st.success("🎉 No issues detected! Your dataset looks clean.")
        else:
            # Build issues table
            issues_table = []
            for iss in issues:
                col_name = iss["column"] if iss["column"] is not None else "Entire Table"
                issues_table.append({
                    "Column": col_name,
                    "Issue Type": iss["issue"].replace("_", " ").title(),
                    "Details": iss["detail"],
                    "Why It Matters": iss["why"]
                })
            st.dataframe(pd.DataFrame(issues_table), use_container_width=True, hide_index=True)
            
    st.markdown("---")
    
    # 4. Present cleaning plan with user permission gate
    st.subheader("📋 Proposed Cleaning Steps")
    st.info(f"**Agent Reasoning:** {plan.plan_reasoning}")
    st.markdown("Review and approve the operations below. Only checked steps will be applied to the dataset.")
    
    if not plan.steps:
        st.info("No cleaning steps needed for this dataset.")
        approved_indices = []
    else:
        # Create a container for the checkboxes
        approved_indices = []
        
        # Display plan steps with checkmarks
        for idx, step in enumerate(plan.steps):
            col_target = step.column if step.column is not None else "Entire Table"
            title = f"Apply **{step.op.replace('_', ' ').upper()}** to **{col_target}**"
            
            # Interactive permission checkbox
            is_approved = st.checkbox(title, value=False, key=f"step_approve_{idx}")
            if is_approved:
                approved_indices.append(idx)
                
            st.markdown(f"👉 **Why:** {step.reason}")
            if step.params:
                st.markdown(f"🔧 **Parameters:** `{step.params}`")
            st.markdown("<br>", unsafe_allow_html=True)
            
    st.markdown("---")
    
    # 5. Apply and Validate trigger button
    if st.button("🧼 Apply Approved Steps", type="primary"):
        with st.spinner("Executing cleaning pipeline and validating results..."):
            # Run application pipeline with self-correction loop
            clean_df, execution_log, val_res, retries = run_with_self_correction(
                raw_df, plan.steps, approved_indices, retry_cap=3
            )
            
            # Save results back to session state
            st.session_state.cleaned_df = clean_df
            st.session_state.execution_log = execution_log
            st.session_state.validation_results = val_res
            st.session_state.retry_count = retries
            
    # Show cleaning execution results if we have them
    if "cleaned_df" in st.session_state and st.session_state.cleaned_df is not None:
        cleaned_df = st.session_state.cleaned_df
        execution_log = st.session_state.execution_log
        validation_results = st.session_state.validation_results
        retries = st.session_state.retry_count
        
        st.subheader("🧹 Cleaning Execution Report")
        if retries > 1:
            st.info(f"🔄 Self-correction loop triggered! Ran {retries} cleaning iterations to resolve hard validation issues.")
            
        # Display the log of changes
        log_rows = []
        for entry in execution_log:
            col_name = entry["column"] if entry["column"] is not None else "Entire Table"
            log_rows.append({
                "Operation": entry["op"],
                "Column": col_name,
                "Parameters": str(entry["params"]),
                "Status": entry["status"].upper(),
                "Outcome / Details": entry["message"]
            })
        st.dataframe(pd.DataFrame(log_rows), use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Display quality validation results
        st.subheader("✅ Data Quality Validation Checks")
        
        val_cols = st.columns(3)
        
        # Duplicates Card
        with val_cols[0]:
            dup_res = validation_results["duplicates"]
            badge_class = "badge-pass" if dup_res["status"] == "pass" else "badge-fail"
            st.markdown(f"""
            <div class="metric-card">
                <span class="status-badge {badge_class}">{dup_res["status"].upper()}</span>
                <div class="metric-value">Duplicates</div>
                <div class="metric-label">{dup_res["message"]}</div>
            </div>
            """, unsafe_allow_html=True)
            
        # Missing Card
        with val_cols[1]:
            miss_res = validation_results["missing"]
            badge_class = "badge-pass" if miss_res["status"] == "pass" else "badge-warn"
            st.markdown(f"""
            <div class="metric-card">
                <span class="status-badge {badge_class}">{miss_res["status"].upper()}</span>
                <div class="metric-value">Missing Data</div>
                <div class="metric-label">{miss_res["message"]}</div>
            </div>
            """, unsafe_allow_html=True)
            
        # Row Loss Card
        with val_cols[2]:
            loss_res = validation_results["row_loss"]
            badge_class = "badge-pass" if loss_res["status"] == "pass" else ("badge-fail" if loss_res["status"] == "fail" else "badge-warn")
            st.markdown(f"""
            <div class="metric-card">
                <span class="status-badge {badge_class}">{loss_res["status"].upper()}</span>
                <div class="metric-value">Row Retention</div>
                <div class="metric-label">{loss_res["message"]}</div>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("---")
        
        # Before and after side by side comparison
        st.subheader("🔄 Before and After Comparison")
        col_b, col_a = st.columns(2)
        
        with col_b:
            st.markdown("#### Raw Data Preview")
            st.dataframe(raw_df.head(10), use_container_width=True)
            
        with col_a:
            st.markdown("#### Cleaned Data Preview")
            st.dataframe(cleaned_df.head(10), use_container_width=True)
            
        st.markdown("---")
        
        # Download files section
        st.subheader("📥 Export Cleaned Outputs")
        col_dl1, col_dl2 = st.columns(2)
        
        # Button 1: Cleaned CSV File
        with col_dl1:
            csv_data = cleaned_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Clean Dataset (CSV)",
                data=csv_data,
                file_name="cleaned_dataset.csv",
                mime="text/csv",
                use_container_width=True
            )
            
        # Button 2: Comparison Excel Workbook
        with col_dl2:
            with st.spinner("Generating comparison workbook..."):
                excel_data = create_comparison_excel(raw_df, cleaned_df, execution_log, plan.plan_reasoning)
            st.download_button(
                label="📊 Download Comparison Report (Excel)",
                data=excel_data,
                file_name="cleaning_comparison_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
else:
    st.info("Please upload a CSV file in the sidebar to begin data cleaning.")
    
    # Instructions panel when no file is uploaded
    st.subheader("How it works")
    st.markdown("""
    1. **Upload a messy dataset** using the folder upload on the left sidebar.
    2. **Inspect detected errors** profiled automatically through deterministic rules.
    3. **Review the suggested cleaning steps** and toggle items to approve or skip.
    4. **Apply approved corrections** to run the tested cleaning functions and validate row health.
    5. **Export your outputs** as a cleaned CSV file or an Excel audit workbook.
    """)
    
    # Try out messy test data recommendation
    if os.path.exists(os.path.join("data", "messy_data.csv")):
        st.markdown("💡 **Tip:** We have generated a messy sample file for you! You can find it at `data/messy_data.csv` in your project folder.")
