# tad-permit-data

# Unified Building Permits Data Pipeline

An automated data extraction, normalization, and AI-enrichment pipeline built to ingest real-time construction and building permit payloads from municipal data portals into a unified local SQLite database. 

This project leverages **Pydantic V2** for active type enforcement and **Hatchet** for high-throughput orchestration to process raw permit descriptions concurrently through OpenRouter LLM engines.

---

## 🏗️ Project Architecture (thus far)

The pipeline is intentionally decoupled into separate layers to maintain high code maintainability:

* **`permit.py`**: The **Data Ingestion Schema Layer**. Holds the single source of truth layout for raw Socrata payloads using Pydantic.
* **`models.py`**: The **AI Output Schema Layer**. Defines the structured data output layout for our LLM responses.
* **`sources/`**: The **Jurisdiction Adapter Layer**. Every city/authority the pipeline ingests is a small adapter registered in `sources/registry.py` — a `SocrataAPISource` or `ArcGISFeatureSource` (one API record = one permit, via a `FieldMapping`) or a `PDFLedgerSource` (one PDF page = zero-or-more permits, via LLM extraction). See "Adding a New Jurisdiction" below.
* **`database.py`**: The **Storage Engine Layer**. Handles the SQLite connection lifecycle, database creation scripts, and standard SQL validation rules.
* **`llm_processor.py`**: The **AI Engine Layer**. Manages structured inference requests to OpenRouter models (such as Gemini 2.5 Flash), with retry/backoff on transient failures.
* **`dataloader.py`**: The **Ingestion Orchestrator**. Looks up the requested jurisdiction's adapter, fetches/maps records, and pushes *batched* events to the background workflow -- see "Hatchet Event Batching" below.
* **`workflow.py`**: The **Hatchet Worker Layer**. Listens for batched workflow events and manages concurrent, resilient data enrichment and database writes.
* **`../tad-permit-dashboard/`** (sibling project): The **Lookup UI Layer**. A read-only Next.js app for searching/filtering the unified `permits` table -- reads `permits.db` directly, no separate API server. See its own README for setup.
* **`logging_setup.py`**: Shared logging config (console + rotating `pipeline.log` file) used by every module above instead of ad-hoc `print()` calls.
* **`eval/`**: The **Quality Eval Layer**. Scores `llm_processor.py`'s live output against hand-labeled golden cases to catch extraction/enrichment quality regressions. See `eval/README.md`.
* **`permit_types.py`**: The **Taxonomy Layer**. One fixed set of permit-type categories (`New Construction`, `Alteration`, `Demolition`, etc.) and a `normalize_permit_type()` keyword matcher every source maps into — this is what makes `permit_type_normalized` actually comparable/filterable across jurisdictions instead of each source inventing its own values.
* **`geo.py`**: The **Coordinate Extraction Layer**. Best-effort `latitude`/`longitude` extraction from a source's raw API payload, tolerant of the handful of shapes Socrata datasets use for point geometry, plus an address-based geocoding fallback (via the free US Census Bureau geocoder) for whenever coordinates aren't provided directly — always for PDF ledgers (which have no geometry field to extract from at all), or for an API record with a missing/malformed one.

---

## 🔌 Adding a New Jurisdiction

Nothing outside `sources/registry.py` needs to change to onboard a new city.

**If it's a Socrata (or Socrata-shaped JSON) API**, most cities need no custom code at all -- just a declarative `FieldMapping` (see `sources/field_mapping.py`) naming which raw field(s) hold each piece of `PermitSchemaV2` (a single field, or an ordered list of candidates to try in turn), and `build_mapper()` generates the actual mapper function from it:

```python
DENVER_MAPPING = FieldMapping(
    jurisdiction="denver",
    source_url="https://data.denvergov.org/resource/xxxx.json",
    permit_id_field="permit_number",
    address_fields=("address",),  # already a complete address? use as-is
    date_fields=("issue_date",),
    permit_type_fields=("permit_class",),
    valuation_field="valuation",
    scope_fields=("description",),
)

"denver": SocrataAPISource(
    name="denver",
    url="https://data.denvergov.org/api/v3/views/xxxx/query.json",
    date_column="issued_date",
    mapper_func=build_mapper(DENVER_MAPPING),
),
```

Only reach for a hand-written `mapper_func` (as Chicago/Austin used to have, and NYC still partly does via `scope_builder`) when a field genuinely needs logic a flat mapping can't express -- e.g. NYC's scope text is built from two labeled fields, not "pick one and truncate." See `sources/registry.py` for the real Chicago/NYC/Austin/Seattle/LA configs, and `tests/test_field_mapping.py` for regression coverage confirming the generic mapper reproduces the pre-refactor behavior exactly.

**If it's an ArcGIS REST `FeatureServer`/`MapServer` layer** (common for mid-size cities/counties that publish permits as a GIS layer rather than a Socrata portal), it's the same `FieldMapping` plus `ArcGISFeatureSource` (see `sources/arcgis.py`) instead of `SocrataAPISource` -- DC is a real example, onboarded this way against `FeatureServer` layer 17:

```python
"dc": ArcGISFeatureSource(
    name="dc",
    url="https://maps2.dcgis.dc.gov/dcgis/rest/services/FEEDS/DCRA/FeatureServer/17",
    date_column="ISSUE_DATE",
    mapper_func=build_mapper(DC_MAPPING),
),
```

`url` must include the numeric layer ID (a service can host several layers; only one is usually the permits table). Unlike Socrata, ArcGIS splits each record into `attributes` and a separate point `geometry` (`{"x": lon, "y": lat}`) -- `ArcGISFeatureSource` flattens that into plain top-level `latitude`/`longitude` at fetch time, the same shape `geo.extract_lat_lon()` already checks first, so no `point_fields` config is ever needed for an ArcGIS source. Two other real differences already found and handled: ArcGIS date fields are Unix epoch milliseconds (an int), not an ISO string like Socrata's (`sources/field_mapping.py`'s `_safe_date()` detects and converts both); and ArcGIS returns geometry in the layer's *native* spatial reference (often a projected local system, e.g. State Plane feet) unless `outSR=4326` (WGS84) is explicitly requested -- DC's coordinates came back `null` for every sample until this was added, since out-of-range projected values fail `geo._valid()`'s sanity check silently rather than erroring.

**Drafting that `FieldMapping` by hand is still the slow part** -- `onboard_jurisdiction.py` speeds it up for either platform: point it at a Socrata resource URL or an ArcGIS layer URL and it fetches the dataset's column metadata (field names/types/descriptions -- stronger signal than a raw sample record alone) plus a few real rows, asks an LLM to propose a mapping, then immediately runs that proposal against the real rows and prints the result plus a list of things worth double-checking (an unmapped required field, a permit type that normalized to `"Other"` and may need a new `permit_types.py` entry, an empty owner/valuation field worth confirming is real).

```bash
uv run python onboard_jurisdiction.py denver https://data.denvergov.org/resource/xxxx.json
uv run python onboard_jurisdiction.py dc https://maps2.dcgis.dc.gov/dcgis/rest/services/FEEDS/DCRA/FeatureServer/17
```

It only prints a draft -- it never touches `sources/registry.py` itself. Two real bugs already slipped past careful *manual* mapping in this project (NYC's config initially missing `valuation_field`; LA's `"Bldg-New"` falling into `"Other"`), and neither would've been caught by clever field-matching alone -- only by looking at real mapped output. This tool exists to make that review faster, not to skip it.

**If it's a monthly PDF ledger**, point the generic PDF adapter at a folder — no mapper needed, since the LLM reads each page and finds every permit listed on it:

```python
"somecity": PDFLedgerSource(name="somecity", folder_path="./somecity_pdfs"),
```

If the city's ledger has quirks the generic extraction prompt won't know about on its own (a specific permit-number pattern, category names, formatting to ignore), pass optional `extraction_hints` — see the `allen` entry in `sources/registry.py`. Leave it unset until you've actually seen the new city's real output and know it needs tuning; a guessed hint for an unseen format is as likely to hurt as help.

Then run it the same way as any other jurisdiction: `uv run python dataloader.py somecity`.

---

## 📊 Unified Database Schema

The incoming datasets are normalized into a single database table (`permits`). Field mappings accommodate differences between cities.

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
| `permit_type_normalized`| `TEXT` | One of a fixed taxonomy (see `permit_types.py`): `New Construction`, `Alteration`, `Demolition`, `Electrical`, `Plumbing`, `Mechanical`, `Roofing`, `Certificate of Occupancy`, `Sign`, `Fire/Life Safety`, `Other`. Always derived by `normalize_permit_type()`, never sourced directly. |
| `address` | `TEXT` | Combined full physical street location entry. |
| `owner_name` | `TEXT` | Name of the recorded building/property owner. |
| `contractor_name` | `TEXT` | Registered corporate name of the designated builder. |
| `valuation` | `REAL` | Total calculated financial assessment/cost estimation. |
| `square_footage` | `REAL` | Total interior physical tracking context. |
| `latitude` / `longitude` | `REAL` | Site coordinates -- from the source's raw payload when available, otherwise geocoded from `address` + jurisdiction as a fallback (see `geo.py`). Still `NULL` when even geocoding fails (bad/ambiguous address, geocoder unreachable) or for rows ingested before this column existed, until re-ingested. |
| `raw_scope_of_work` | `TEXT` | Unaltered original textual transcription profile of intended task. |
| `scope_summary` | `TEXT` | High-level, LLM-generated summary of the `raw_scope_of_work`. |
| `building_systems` | `TEXT` | A serialized JSON array string listing all construction systems or materials mentioned. |

> 💡 **Integrity Rules:** The table explicitly declares a database-level multi-column constraint: `UNIQUE(permit_id, jurisdiction)`. This structural rule acts as a hardware ledger constraint that silently filters out automated pipeline duplicate entries via SQL's `INSERT OR IGNORE` directive.

---

## 🛠️ Installation & Setup

### 1. Prerequisites
Ensure you have Python 3.10+ and the **`uv`** package manager installed.

### 2. Install Project Dependencies
This project's dependencies are declared in `pyproject.toml`. Install them with:

```bash
uv sync
```

### 3. Environment Keys Configuration
Set up environment variables and API credentials (note: the pipeline reads `OPEN_ROUTER_KEY`, not `OPENROUTER_API_KEY`):

```bash
cp .env.example .env
```

```bash
SOCRATA_APP_TOKEN="your_actual_socrata_token_here"
OPEN_ROUTER_KEY="your_actual_openrouter_token_here"
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
In a separate terminal tab, run the ingestion dataloader for whichever jurisdiction you want (see `sources/registry.py` for the full list, or run with no arguments to see them):

```bash
uv run python dataloader.py chicago --size 100
uv run python dataloader.py nyc --size 100
uv run python dataloader.py allen --size 100   # PDF ledger ingestion
```

Ingestion failures (bad records, DB conflicts, an unreachable API, an offline worker) are logged to the console and to `pipeline.log` and skip only the affected record — they don't stop the batch.

### Hatchet Event Batching

Hatchet event volume is decoupled from data volume, which matters if you're on a plan with an event/run limit and want to run ingestion on a schedule rather than by hand:

* **API sources** (Chicago/NYC/Austin/Seattle/LA/DC): every newly-inserted permit from one `dataloader.py` run is collected and pushed as a single `permit:enrich_batch` event (chunked at `ENRICH_BATCH_SIZE` permits per event, purely a payload-size margin) instead of one `permit:enrich` event per permit. Duplicate/already-ingested permits never trigger an event at all (`INSERT OR IGNORE` + a `was_inserted` check), so a scheduled re-run's event cost scales with *new* permits only, not the `--size` fetched.
* **PDF sources** (Allen/Naperville): every page queued for one file goes out as a single `pdf:process_batch` event instead of one event per page -- a 96-page monthly ledger costs 1 event, not 96.
* **PDF resumable cursor**: `PDFLedgerSource.iter_pages()` resumes from the last page it successfully queued (tracked in the `ingestion_cursors` table, via `database.get_pdf_cursor()`/`update_pdf_cursor()`) instead of always restarting at page 1 of the first file. Without this, a repeated run -- scheduled or just re-run by hand -- would re-read and re-queue an event for the exact same pages every time, since there was previously no memory of prior progress at all. The cursor advances only after a batch is *successfully* pushed, so a failed Hatchet push gets retried next run rather than silently skipped.

See `tests/test_dataloader.py`, `tests/test_workflow.py`, `tests/test_pdf_ledger.py`, and `tests/test_database_cursor.py` for coverage of the batching and resume behavior.

### Step 3: Browse & Search Permits
The lookup dashboard lives in the sibling `tad-permit-dashboard/` Next.js project (reads `permits.db` directly, no ingestion changes needed). See `../tad-permit-dashboard/README.md`, or briefly:

```bash
cd ../tad-permit-dashboard
npm install
npm run dev
```

### Step 4: Evaluate Extraction Quality
Run the LLM eval harness against a golden set of hand-labeled cases (including real Allen ledger pages) to catch quality regressions from prompt or model changes — see `eval/README.md` for details:

```bash
uv run python -m eval.harness
```
