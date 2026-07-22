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
  `PermitDetail`, `NavTabs`, plus a small reusable `CheckboxGroup`.
- `src/lib/usePermits.ts` -- shared fetch/filter/options state, used by both
  the table page (`/`) and the map page (`/map`) so they stay in sync
  without duplicating the fetch-and-filter logic.

## Map view (`/map`)

Plots permits with known coordinates using `react-leaflet` + OpenStreetMap
tiles (free, no API key). Hover a point for a quick tooltip; click one to
populate the same detail panel the table page uses. Colored by
jurisdiction, using a palette assigned by sorted position rather than a
hardcoded name -> color map, so a newly-registered jurisdiction just gets
the next color automatically.

Nearby permits cluster into a numbered bubble at lower zoom levels
(`leaflet.markercluster`) and split apart as you zoom in -- without this, a
dense area (e.g. downtown Chicago) would render as a pile of overlapping,
unclickable dots once real ingestion volume backfills coordinates.

**Coordinate coverage is partial and source-dependent:**
- Chicago/NYC/Austin (API sources) capture `latitude`/`longitude` from their
  Socrata payloads on ingestion -- see `tad-permit-pipeline/geo.py`. The
  exact field names used weren't verified against live API responses (no
  network access to those hosts in the environment this was built in), so
  actual coverage may be lower than expected until confirmed against a real
  ingestion run.
- Allen (PDF ledger) permits have no geometry field to extract coordinates
  from directly, but get a best-effort address-based geocode instead (via
  the free US Census Bureau geocoder, combining the permit's street address
  with Allen's known city/state) -- see `tad-permit-pipeline/geo.py`. This
  is the same fallback API sources get when their raw payload is missing or
  has a malformed geometry field. It can still come back empty for a bad or
  ambiguous address, or if the geocoder is unreachable.
- Permits ingested *before* this feature existed have `NULL` coordinates
  regardless of source, since the column didn't exist yet when they were
  written. Re-run ingestion to backfill them.

The map page shows a "N of M have no location data yet" count so this
limitation is visible in the UI rather than silently dropping permits.

Markers are `L.divIcon`s (plain HTML/CSS colored circles) rather than
Leaflet's default image-based marker, for two reasons: it avoids a
well-known Leaflet+bundler gotcha (default marker icon assets not resolving
correctly through Next.js's build), and `leaflet.markercluster` only
clusters `L.Marker`-like layers -- the SVG `CircleMarker`s used before
clustering was added aren't compatible with it.
