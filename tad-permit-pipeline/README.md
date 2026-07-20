# tad-permit-data

# Unified Building Permits Data Pipeline

An automated data extraction, normalization, and AI-enrichment pipeline built to ingest real-time construction and building permit payloads from municipal data portals into a unified local SQLite database. 

This project leverages **Pydantic V2** for active type enforcement and **Hatchet** for high-throughput orchestration to process raw permit descriptions concurrently through OpenRouter LLM engines.

---

## 🏗️ Project Architecture (thus far)

The pipeline is intentionally decoupled into separate layers to maintain high code maintainability:

* **`permit.py`**: The **Data Ingestion Schema Layer**. Holds the single source of truth layout for raw Socrata payloads using Pydantic.
* **`models.py`**: The **AI Output Schema Layer**. Defines the structured data output layout for our LLM responses.
* **`database.py`**: The **Storage Engine Layer**. Handles the SQLite connection lifecycle, database creation scripts, and standard SQL validation rules.
* **`llm_processor.py`**: The **AI Engine Layer**. Manages structured inference requests to OpenRouter models (such as Gemini 2.5 Flash).
* **`dataloader.py`**: The **Ingestion Orchestrator**. Queries live city open data endpoints, maps raw fields, and pushes events to the background workflow.
* **`workflow.py`**: The **Hatchet Worker Layer**. Listens for workflow events and manages concurrent, resilient data enrichment and database writes.

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
Manage your virtual environment sandbox and project extensions natively using `uv`:

```bash
uv pip install requests pydantic python-dotenv openai hatchet-sdk
```

### 3. Environment Keys Configuration
Create a file named .env in the root folder of your project workspace and apply your unique API credentials:

```bash
SOCRATA_APP_TOKEN="your_actual_socrata_token_here"
OPENROUTER_API_KEY="your_actual_openrouter_token_here"
HATCHET_CLIENT_TOKEN="your_actual_hatchet_token_here"
```

## 🚀 Execution Guide
This system uses a decoupled trigger-and-worker model. To run the full pipeline, you must operate two processes in separate terminal sessions:

### Step 1: Start the Hatchet Background Worker
In your first terminal tab, spin up the background engine to listen for job events and run concurrent OpenRouter extractions:

```bash
uv run python workflow.py
```

### Step 2: Trigger Ingestion or Backfills
In a separate terminal tab, execute your ingestion dataloader to pull live municipal records and hand them off to the queue:

```bash
uv run python dataloader.py
```
