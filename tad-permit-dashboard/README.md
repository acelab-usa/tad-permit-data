# tad-permit-dashboard

Read-only lookup UI for the unified permits table produced by the
`tad-permit-pipeline` ingestion pipeline (a sibling Python project). This
replaces the earlier Streamlit dashboard -- same filters/table/detail-view
functionality, now as a Next.js app.

It reads `permits.db` directly (via `sql.js`, a pure-WASM SQLite build) --
there's no separate API server, and no changes to ingestion, enrichment, or
normalization, which all still live in the Python project.

`sql.js` was chosen deliberately over `better-sqlite3`: the latter is a
native addon requiring a per-machine compiled binary, which segfaulted
outright on at least one contributor's machine (a broken local
node-gyp/toolchain setup, unrelated to this app's code) -- `sql.js` needs no
native compilation at all, so that whole class of "works on my machine"
failure can't recur. The tradeoff is it loads the whole file into memory per
read rather than holding an open file handle; irrelevant at this table's
size (a few hundred KB).

## Setup

```bash
npm install
```

By default this reads `../tad-permit-pipeline/permits.db` (i.e. the two
projects checked out as siblings). Override with an env var if that's not
your layout:

```bash
# .env.local
PERMITS_DB_PATH=/absolute/path/to/permits.db
```

## Run

```bash
npm run dev
```

Then open http://localhost:3000. There's nothing to start on the Python
side for this app specifically -- just make sure `permits.db` has been
created and populated (`uv run python dataloader.py <jurisdiction>` in
`tad-permit-pipeline/`).

## Architecture

- `src/lib/db.ts` -- reads `permits.db` into memory and opens it via `sql.js`
  (pure WASM, no native compilation). Re-reads the file on every call rather
  than holding a persistent connection, so it always reflects the current
  state of the file with no manual cache invalidation needed.
- `src/app/api/permits/route.ts` -- one route, returns the whole `permits`
  table as JSON. The table is a few hundred rows, so this loads once and
  filters happen client-side (same approach the Streamlit version used with
  a pandas dataframe) rather than a query-param-driven filtered endpoint.
- `src/lib/filters.ts` -- pure filtering logic, mirrors the Streamlit
  version's semantics exactly (e.g. a permit with a missing
  `valuation`/`filing_date` still passes the valuation/date filters rather
  than being excluded).
- `src/lib/permit-types.ts` / `src/lib/jurisdictions.ts` -- mirror
  `tad-permit-pipeline/permit_types.py`'s `PERMIT_TYPE_TAXONOMY` and
  `sources/registry.py`'s registered adapters, respectively. **These can't
  import the Python source of truth directly**, so if either changes on the
  Python side (a new jurisdiction adapter, a taxonomy category), update the
  matching file here too. This is what makes the jurisdiction/permit-type
  filters show every registered option -- including ones with zero ingested
  rows yet -- instead of only what's currently in the data.
- `src/components/` -- `Filters`, `MetricsRow`, `PermitsTable`,
  `PermitDetail`, plus a small reusable `CheckboxGroup`.

## Not yet built

An interactive map view (permit locations, hover tooltips, click-to-select)
is planned as a follow-up once this lookup-table migration is done -- see
the pipeline's README/commit history for context. `pydeck`'s Streamlit
integration was prototyped for this but shelved in favor of the Next.js
migration; the JS equivalent would be deck.gl or MapLibre GL.
