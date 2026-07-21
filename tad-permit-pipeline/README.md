# tad-permit-data

# Unified Building Permits Data Pipeline

An automated data extraction, normalization, and AI-enrichment pipeline built to ingest real-time construction and building permit payloads from municipal data portals into a unified local SQLite database. 

This project leverages **Pydantic V2** for active type enforcement and **Hatchet** for high-throughput orchestration to process raw permit descriptions concurrently through OpenRouter LLM engines.

---

## 🏗️ Project Architecture (thus far)

The pipeline is intentionally decoupled into separate layers to maintain high code maintainability:

* **`permit.py`**: The **Data Ingestion Schema Layer**. Holds the single source of truth layout for raw Socrata payloads using Pydantic.
* **`models.py`**: The **AI Output Schema Layer**. Defines the structured data output layout for our LLM responses.
* **`sources/`**: The **Jurisdiction Adapter Layer**. Every city/authority the pipeline ingests is a small adapter registered in `sources/registry.py` — either a `SocrataAPISource` (one API record = one permit, via a mapper function) or a `PDFLedgerSource` (one PDF page = zero-or-more permits, via LLM extraction). See "Adding a New Jurisdiction" below.
* **`database.py`**: The **Storage Engine Layer**. Handles the SQLite connection lifecycle, database creation scripts, and standard SQL validation rules.
* **`llm_processor.py`**: The **AI Engine Layer**. Manages structured inference requests to OpenRouter models (such as Gemini 2.5 Flash), with retry/backoff on transient failures.
* **`dataloader.py`**: The **Ingestion Orchestrator**. Looks up the requested jurisdiction's adapter, fetches/maps records, and pushes events to the background workflow.
* **`workflow.py`**: The **Hatchet Worker Layer**. Listens for workflow events and manages concurrent, resilient data enrichment and database writes.
* **`dashboard.py`**: The **Lookup UI Layer**. A read-only Streamlit app for searching/filtering the unified `permits` table.
* **`logging_setup.py`**: Shared logging config (console + rotating `pipeline.log` file) used by every module above instead of ad-hoc `print()` calls.
* **`eval/`**: The **Quality Eval Layer**. Scores `llm_processor.py`'s live output against hand-labeled golden cases to catch extraction/enrichment quality regressions. See `eval/README.md`.

---

## 🔌 Adding a New Jurisdiction

Nothing outside `sources/registry.py` needs to change to onboard a new city.

**If it's a Socrata (or Socrata-shaped JSON) API**, add an entry using the generic adapter and a small mapper function that turns one raw record into the fields `PermitSchemaV2` expects:

```python
"denver": SocrataAPISource(
    name="denver",
    url="https://data.denvergov.org/api/v3/views/xxxx/query.json",
    date_column="issued_date",
    mapper_func=map_denver_to_schema,  # write this next to map_chicago_to_schema
),
```

**If it's a monthly PDF ledger**, point the generic PDF adapter at a folder — no mapper needed, since the LLM reads each page and finds every permit listed on it:

```python
"somecity": PDFLedgerSource(name="somecity", folder_path="./somecity_pdfs"),
```

Then run it the same way as any other jurisdiction: `uv run python dataloader.py somecity`.

---

## 📊 Unified Database Schema

The incoming datasets are normalized into a single database table (`building_permits`). Field mappings accommodate differences between cities.

### Target Layout Blueprint

| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `id` | `INTEGER` | Primary Key, Auto-incremented tracking number. |
| `permit_id` | `TEXT` | Unique identifier assigned by the source city registry. |
| `jurisdiction` | `TEXT` | The city name context (e.g., 'Chicago', 'NYC'). |
| `source_url` | `TEXT` | Direct link origin source endpoint location context. |
| `source_format` | `TEXT` | Format of origin registry ingestion system (e.g., 'API', 'PDF').|
| `extracted_at` | `TIMESTAMP`| Chronological processing audit timestamp record. |
| `filing_date` | `TEXT` | Chronological date tracking stamp for the application filing. |
| `permit_type_raw` | `TEXT` | Original, un-normalized string categorizing the permit type. |
| `permit_type_normalized`| `TEXT` | Cleaned, universally mapped taxonomy grouping. |
| `address` | `TEXT` | Combined full physical street location entry. |
| `owner_name` | `TEXT` | Name of the recorded building/property owner. |
| `contractor_name` | `TEXT` | Registered corporate name of the designated builder. |
| `valuation` | `REAL` | Total calculated financial assessment/cost estimation. |
| `square_footage` | `REAL` | Total interior physical tracking context. |
| `raw_scope_of_work` | `TEXT` | Unaltered original textual transcription profile of intended task. |
| `scope_summary` | `TEXT` | High-level, LLM-generated summary of the `raw_scope_of_work`. |
| `building_systems` | `TEXT` | A serialized JSON array string listing all construction systems or materials mentioned. |

> 💡 **Integrity Rules:** The table explicitly declares a database-level multi-column constraint: `UNIQUE(permit_id, jurisdiction)`. This structural rule acts as a hardware ledger constraint that silently filters out automated pipeline duplicate entries via SQL's `INSERT OR IGNORE` directive.

---

## 🛠️ Installation & Setup

### 1. Prerequisites
Ensure you have Python 3.10+ and the **`uv`** package manager installed.

### 2. Install Project Dependencies
This project's dependencies (including `streamlit`/`pandas` for the lookup dashboard) are declared in `pyproject.toml`. Install them with:

```bash
uv sync
```

### 3. Environment Keys Configuration
Copy `.env.example` to `.env` in the project workspace and fill in your unique API credentials (note: the pipeline reads `OPEN_ROUTER_KEY`, not `OPENROUTER_API_KEY`):

```bash
cp .env.example .env
```

```bash
SOCRATA_APP_TOKEN="your_actual_socrata_token_here"
OPEN_ROUTER_KEY="your_actual_openrouter_token_here"
HATCHET_CLIENT_TOKEN="your_actual_hatchet_token_here"
```

`.env` is gitignored — never commit real credentials. If credentials were ever committed to this repo's history, rotate them; being in history means they're compromised even after removal.

## 🚀 Execution Guide
This system uses a decoupled trigger-and-worker model. To run the full pipeline, you must operate two processes in separate terminal sessions:

### Step 1: Start the Hatchet Background Worker
In your first terminal tab, spin up the background engine to listen for job events and run concurrent OpenRouter extractions:

```bash
uv run python workflow.py
```

### Step 2: Trigger Ingestion or Backfills
In a separate terminal tab, run the ingestion dataloader for whichever jurisdiction you want (see `sources/registry.py` for the full list, or run with no arguments to see them):

```bash
uv run python dataloader.py chicago --size 100
uv run python dataloader.py nyc --size 100
uv run python dataloader.py allen --size 100   # PDF ledger ingestion
```

Ingestion failures (bad records, DB conflicts, an unreachable API, an offline worker) are logged to the console and to `pipeline.log` and skip only the affected record — they don't stop the batch.

### Step 3: Browse & Search Permits
Launch the read-only lookup dashboard to filter permits by jurisdiction, type, date range, valuation, or free-text search:

```bash
uv run streamlit run dashboard.py
```

### Step 4: Evaluate Extraction Quality
Run the LLM eval harness against a golden set of hand-labeled cases (including real Allen ledger pages) to catch quality regressions from prompt or model changes — see `eval/README.md` for details:

```bash
uv run python -m eval.harness
```
