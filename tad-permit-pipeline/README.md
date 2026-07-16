# tad-permit-data

# Unified Building Permits Data Pipeline

An automated data extraction and normalization pipeline built to ingest real-time construction and building permit payloads from municipal data portals (such as Chicago and New York City) into a unified local SQLite database. 

This project leverages **Pydantic V2** for active type enforcement and data parsing, ensuring unstructured or unpredictable API streams are completely sanitized before long-term storage.

---

## 🏗️ Project Architecture (thus far)

The pipeline is intentionally decoupled into separate layers to maintain high code maintainability:

* **`permit.py`**: The **Data Modeling Layer**. Holds the single source of truth schema layout using Pydantic.
* **`database.py`**: The **Storage Engine Layer**. Handles the SQLite connection lifecycle, database creation scripts, and standard SQL validation rules.
* **`dataloader.py`**: The **Orchestration Layer**. Sends secure network queries via `requests` to active city open data endpoints, maps raw field keys to our core schema model, and triggers database insertions.

---

## 📊 Unified Database Schema

The incoming datasets are normalized into a single database table (`building_permits`). Field mappings accommodate differences between cities (e.g., matching Chicago's `reported_cost` and NYC's `estimated_job_costs` into a unified `valuation` column).

### Target Layout Blueprint

| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `id` | `INTEGER` | Primary Key, Auto-incremented tracking number. |
| `permit_id` | `TEXT` | Unique identifier assigned by the source city registry. |
| `jurisdiction` | `TEXT` | The city name context (e.g., 'Chicago', 'NYC'). |
| `source_format` | `TEXT` | Format of origin registry ingestion system (e.g., 'API', 'PDF').|
| `filing_date` | `TEXT` | Chronological date tracking stamp for the application filing. |
| `permit_type` | `TEXT` | Normalized classification of targeted construction work. |
| `address` | `TEXT` | Combined/Geocoded full physical street location entry. |
| `owner_name` | `TEXT` | Name of the recorded building/property owner. |
| `contractor_name` | `TEXT` | Registered corporate name of the designated builder. |
| `valuation` | `REAL` | Total calculated financial assessment/cost estimation. |
| `square_footage` | `REAL` | Total interior physical tracking context (*Unused for API sources*). |
| `raw_scope_of_work` | `TEXT` | Unaltered original textual transcription profile of intended task. |
| `model_scope_summary` | `TEXT` | One sentance LLM-generated summary of raw_scope_of_work |
| `materials_systems_mentioned` | `LIST` | List of all materials and/or structural systems mentioned in permit log |

> 💡 **Integrity Rules:** The table explicitly declares a database-level multi-column constraint: `UNIQUE(permit_id, jurisdiction)`. This structural rule acts as a hardware ledger constraint that silently filters out automated pipeline duplicate entries via SQL's `INSERT OR IGNORE` directive.

---

## 🛠️ Installation & Setup

### 1. Prerequisites
Ensure you have Python 3.10+ installed on your computer.

### 2. Clone and Setup Environment
Navigate to your project directory and configure a clean sandbox virtual environment:

```bash
python -m venv venv

# Activate on Mac/Linux
source venv/bin/activate

# Activate on Windows
.\venv\Scripts\activate
```

### 3. Install Third-Party Extensions
Install core data handling libraries:

```bash
pip install requests pydantic python-dotenv
```

### 4. Environment Keys configuration
Create a file named `.env` in the root folder of your project workspace and apply your unique Socrata API token identifier:

```bash
SOCRATA_APP_TOKEN="your_actual_token_here"
```
---

## 🚀 Execution Guide

Run the data orchestrator function to dynamically query city portal APIs, map objects via memory-safe models, and populate your database:

```bash
python dataloader.py
```

### Reviewing Local Ingestion
To verify your active dataset states directly inside your terminal, execute your internal read utility script:

```bash
python view_db.py
```
