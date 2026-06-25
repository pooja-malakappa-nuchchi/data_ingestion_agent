# CleanSweep — AI-Powered Data Cleaning Agent

CleanSweep is an interactive data cleaning assistant built with Python and Streamlit. It profiles messy CSV datasets, proposes an ordered cleaning plan using Google Gemini AI or rule-based fallback logic, and applies changes only after explicit human approval. Every step is logged, auditable, and reversible.

**IMPORTANT** This is a working prototype. The core architecture, AI plan generation, human approval gate, deterministic execution in tools.py, and self-correction loop is designed with production principles in mind. To take it to production I would add PostgreSQL for session persistence, replace Streamlit with FastAPI + React, add authentication, chunked processing for large files, and a proper logging system. But for demonstrating the approach and the AI integration, the prototype covers the need.

---

## The Problem It Solves

Data preparation takes up a massive portion of time in data engineering and data science. Two common approaches both have serious flaws:

- **Fully automatic cleaning** — fast but dangerous. Systems make assumptions that silently corrupt data (e.g. filling 90% of a column with a fabricated median).
- **Manual cleaning** — accurate but slow, repetitive, and error-prone at scale.

CleanSweep sits in between — AI reasons about what should be cleaned, humans approve each step, and deterministic code executes the changes safely.

---

## Core Design Principle — Separation of Reasoning and Execution

The AI (or fallback rules) only produces a **plan** — a structured list of steps with reasons. It never touches the dataframe directly. All actual data modifications are performed by a fixed, tested library of pure pandas functions in `agent/tools.py`.

This means:
- The AI cannot corrupt data directly
- Every change is deterministic and reproducible
- Every step is logged with its outcome
- The user can approve or reject individual steps

---

## Tech Stack

| Technology | Purpose | Why This Over Alternatives |
|---|---|---|
| **Streamlit** | Web dashboard | Pure Python — no frontend code needed. Fastest path from data logic to interactive UI. Flask/React would take days for the same result. |
| **Pandas** | Data loading and cleaning | Industry standard for tabular data in Python. No viable alternative for this use case. |
| **Google Gemini 2.5 Flash** | AI plan generation | Has a free tier with structured output support (`response_schema`). Allows demo without a paid API key. OpenAI and Claude are paid. |
| **Pydantic v2** | Structured output validation | Automatically generates JSON Schema from Python classes. Used both to enforce Gemini's response format and to validate the returned plan. |
| **python-dotenv** | API key management | Keeps secrets out of code. Reads from `.env` file so API keys are never committed to GitHub. |
| **openpyxl** | Excel export | Required by pandas to write `.xlsx` files for the comparison report. |
| **word2number** | Word-form number conversion | Converts text like "Seventy-Two Thousand" to 72000 before numeric coercion, preventing valid values from becoming NaN. |

---

## Why Gemini Despite Having Other Options

| Option | Reason Not Used |
|---|---|
| OpenAI GPT-4o | Paid per call — requires credit card |
| Claude (Anthropic) | Paid — no free tier |
| Llama 3 (local) | Requires GPU, complex local setup |
| LangChain | complex for this use case |
| LangGraph | Designed for multi-node AI graphs with conditional routing. The current flow is linear enough that plain Python functions cover it. Natural next step if the agent needs multi-round autonomous reasoning. |

Gemini 2.5 Flash was chosen because it is **free**, supports **structured JSON output** via `response_schema`, which is powerful.

---

## How It Works — Step by Step

```
Upload CSV
    ↓
inspect.py — scans for issues (duplicates, missing values, mixed case, etc.)
    ↓
propose.py — AI or fallback rules generate an ordered cleaning plan
    ↓
app.py — shows plan to user, each step has a checkbox (unchecked by default)
    ↓
User ticks the steps they want to apply
    ↓
apply.py — runs only approved steps, logs each outcome
    ↓
validate.py — checks cleaned data for remaining issues
    ↓
(if duplicates remain) self-correction loop retries up to 3 times
    ↓
Download cleaned CSV or Excel comparison report
```

---

## AI Mode vs Fallback Mode

The sidebar has a checkbox: **"Use AI Reasoning (Gemini / OpenAI)"** — unchecked by default.

| | Fallback (rules) | Gemini (AI) |
|---|---|---|
| How it decides | Fixed if/elif rules per issue type | Reads column names, row count, and issues — reasons about context |
| `standardize_text` suggested | Only if mixed case detected | Can suggest based on column name |
| `drop_column` suggested | Only if 90%+ empty | Can suggest for ID or useless columns |
| Execution order | Enforced by OP_ORDER | Decided by Gemini |
| Fill strategy | Median for numbers, mode for text | Chooses mean/median/mode per column |


**Important:** Toggling the checkbox regenerates the plan immediately. If you upload a file with the checkbox off, then turn it on, a fresh AI plan is generated automatically.

---

## File Structure and Why Each File Exists

```
data_ingestion_agent/
├── app.py                  # Main Streamlit dashboard
├── requirements.txt        # Python package dependencies
├── .env                    # API keys (never committed to GitHub)
├── agent/
│   ├── inspect.py          # Issue detection
│   ├── propose.py          # Plan generation (AI + fallback)
│   ├── apply.py            # Plan execution
│   ├── validate.py         # Post-clean quality checks
│   ├── tools.py            # Cleaning operations library
│   └── compare.py          # Excel comparison report builder
├── tests/
│   ├── test_tools.py       # Unit tests for all cleaning tool functions
│   └── test_inspect.py     # Unit tests for issue detection logic
└── data/
    └── make_messy.py       # Test data generator
```

### `agent/inspect.py`
Scans the dataframe and returns a list of detected issues. Checks for:
- Duplicate rows
- Missing values (flags columns with 90%+ missing as `nearly_empty` — separate from normal missing)
- Whitespace — leading, trailing, and multiple internal spaces
- Mixed case — same value in different capitalizations (e.g. Alice/alice/ALicE), skips columns with alphanumeric codes like A10023f
- Numbers stored as text
- Outliers using IQR — skips columns where 90%+ of values are unique (ID columns)

Kept separate from proposal logic so detection and decision-making are independently testable.

### `agent/propose.py`
Takes the issues list and produces a `CleaningPlan` — a Pydantic-validated list of `CleaningStep` objects.

- `propose_plan_gemini()` — calls Gemini API with a structured schema, returns AI-reasoned plan
- `propose_plan_fallback()` — maps each issue type to a fixed cleaning action using if/elif rules
- `propose_plan()` — entry point: tries Gemini first, falls back to rules if AI fails or is disabled

The fallback uses `OP_ORDER` to enforce correct execution sequence:
1. `strip_whitespace` — clean spaces first
2. `standardize_text` — normalize case (Alice/alice → alice)
3. `drop_duplicates` — now catches case-normalized duplicates correctly
4. `coerce_type` — convert text to numbers or dates
5. `remove_outliers` — remove extremes before calculating fill values
6. `fill_missing` — fill with clean median (not contaminated by outliers)
7. `drop_column` — remove useless columns last

### `agent/apply.py`
Loops through plan steps and runs only the ones the user approved. Key behaviours:
- `drop_duplicates` never receives a `column` argument — it operates on the whole table
- Default params are applied if AI forgets to include them (e.g. `strategy: median` for `fill_missing`)
- Each step is wrapped in try/except — one failing step does not stop the rest of the pipeline
- Every step is logged with status: `applied`, `skipped`, or `error`

### `agent/validate.py`
Runs three quality checks after cleaning:
- **Duplicates** — hard failure if any remain
- **Missing values** — warning if any remain
- **Row loss** — warning if more than 30% of rows were removed

Also contains `run_with_self_correction()` — a retry loop that detects duplicate failures and automatically inserts a `drop_duplicates` step, retrying up to 3 times.

### `agent/tools.py`
The only file that directly modifies dataframes. Each function:
- Takes a dataframe and parameters
- Returns a new dataframe and a message string
- Never mutates the input dataframe

`strip_whitespace` uses `re.sub(r' +', ' ', x.strip())` to handle both leading/trailing and multiple internal spaces in one pass.

`coerce_type` first attempts `word2number` conversion on string values before calling `pd.to_numeric` — so "Seventy-Two Thousand" correctly becomes 72000 instead of NaN.

### `agent/compare.py`
Builds a multi-sheet Excel workbook with:
- Raw vs cleaned data samples side by side
- Column-level statistics comparison
- Execution log of every step

### `app.py`
Orchestrates the full pipeline using Streamlit session state. Key decisions:
- All cleaning step checkboxes default to **unchecked** — user must read and approve each step
- Plan is regenerated when the AI checkbox is toggled — prevents stale fallback plan being reused after enabling AI
- File change detection resets all session state so previous results never leak into a new file's analysis

---

## Getting Started — Complete Setup From Scratch

### Prerequisites
- Python 3.9 or higher installed
- Git installed
- A Google Gemini API key (free at [aistudio.google.com](https://aistudio.google.com)) — optional, app works without it

### Step 1 — Clone the repository
```bash
git clone https://github.com/pooja-malakappa-nuchchi/data_ingestion_agent.git
cd data_ingestion_agent
```

### Step 2 — Create a virtual environment
```bash
python -m venv venv
```

Activate it:
- **Windows:** `venv\Scripts\activate`
- **Mac/Linux:** `source venv/bin/activate`

### Step 3 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 4 — Set up your API key (optional)
Create a file called `.env` in the root folder:
```
GEMINI_API_KEY=your_actual_key_here
```
If you skip this step, the app still works using rule-based fallback. AI features are just disabled.

### Step 5 — Generate test data (optional)
```bash
python data/make_messy.py
```
This creates `data/messy_data.csv` — a sample CSV with intentional problems (duplicates, missing values, mixed case, word-form numbers, outliers) for testing.

### Step 6 — Run the app
```bash
streamlit run app.py
```

The app opens automatically in your browser at `http://localhost:8501`.

---

## Using the App

1. **Upload a CSV** using the sidebar file uploader
2. **Review detected issues** in the Anomalies table
3. **Enable AI reasoning** (optional) — tick the checkbox in the sidebar, confirm green key indicator appears
4. **Review the proposed cleaning steps** — each step shows what it does and why
5. **Tick the steps you want to apply** — unchecked by default, you are in control
6. **Click "Apply Approved Steps"** — pipeline runs and validation checks execute
7. **Review the execution report and quality checks**
8. **Download** the cleaned CSV or the Excel comparison report

---

## Known Limitations

- **Word-form numbers with spaces removed** — "NewYork" vs "New York" cannot be split by rules alone. Gemini handles this; fallback cannot.
- **No session persistence** — if the browser closes mid-clean, all progress is lost. There is no database or disk storage.
- **Gemini failures are silent** — if the AI call fails, the app falls back to rules without showing a warning in the UI. The error is printed to the terminal only.
- **IQR outlier detection** — may flag legitimate values in heavily skewed distributions. User should review before approving outlier removal steps.

## Future Work
- **Support for non-CSV formats** — only `.csv` files are accepted. Excel, JSON, and Parquet are not currently supported.
- **Database** - DB can be introduced (based on use case) the cleaned data can later be can be used for further process like to train models or any future use.
- **Make production ready based on use case**
