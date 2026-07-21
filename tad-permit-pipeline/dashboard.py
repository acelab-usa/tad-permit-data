"""dashboard.py -- Read-only permit lookup UI.

Run with:
    uv run streamlit run dashboard.py

Lets anyone search/filter the unified `permits` table without writing SQL:
by jurisdiction, permit type, date range, valuation, or free-text search
across address/owner/contractor/permit id.
"""
import json
import sqlite3

import pandas as pd
import streamlit as st

import database

st.set_page_config(page_title="Permit Lookup", page_icon="\U0001F3D7️", layout="wide")


@st.cache_data(ttl=30)
def load_permits() -> pd.DataFrame:
    try:
        conn = database.get_connection()
        try:
            df = pd.read_sql_query("SELECT * FROM permits", conn)
        finally:
            conn.close()
    except sqlite3.OperationalError:
        # DB file exists but the table doesn't (e.g. init_db() never ran), or
        # the file doesn't exist yet -- either way, treat it as "no data".
        return pd.DataFrame()

    if df.empty:
        return df

    df["filing_date"] = pd.to_datetime(df["filing_date"], errors="coerce")
    df["extracted_at"] = pd.to_datetime(df["extracted_at"], errors="coerce")
    return df


def parse_building_systems(raw_json: str) -> list[str]:
    if not raw_json:
        return []
    try:
        parsed = json.loads(raw_json)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


st.title("\U0001F3D7️ Permit Lookup")

col_refresh, _ = st.columns([1, 5])
with col_refresh:
    if st.button("\U0001F504 Refresh data"):
        load_permits.clear()

permits_df = load_permits()

if permits_df.empty:
    st.info(
        "No permits found in the database yet. Run the ingestion pipeline "
        "first (`uv run python dataloader.py <jurisdiction>`), then refresh."
    )
    st.stop()

# --- Sidebar filters ---------------------------------------------------
st.sidebar.header("Filters")

jurisdictions = sorted(permits_df["jurisdiction"].dropna().unique().tolist())
selected_jurisdictions = st.sidebar.multiselect("Jurisdiction", jurisdictions, default=jurisdictions)

permit_types = sorted(permits_df["permit_type_normalized"].dropna().unique().tolist())
selected_types = st.sidebar.multiselect("Permit type", permit_types, default=permit_types)

search_text = st.sidebar.text_input(
    "Search (address, owner, contractor, permit #)", placeholder="e.g. 123 Main St"
)

valid_dates = permits_df["filing_date"].dropna()
if not valid_dates.empty:
    min_date, max_date = valid_dates.min().date(), valid_dates.max().date()
    date_range = st.sidebar.date_input("Filing date range", value=(min_date, max_date))
else:
    date_range = None

valid_valuations = permits_df["valuation"].dropna()
if not valid_valuations.empty:
    min_val, max_val = float(valid_valuations.min()), float(valid_valuations.max())
    if min_val < max_val:
        val_range = st.sidebar.slider("Valuation range ($)", min_val, max_val, (min_val, max_val))
    else:
        val_range = None
else:
    val_range = None

# --- Apply filters -------------------------------------------------------
filtered = permits_df.copy()

if selected_jurisdictions:
    filtered = filtered[filtered["jurisdiction"].isin(selected_jurisdictions)]
if selected_types:
    filtered = filtered[
        filtered["permit_type_normalized"].isin(selected_types) | filtered["permit_type_normalized"].isna()
    ]

if search_text:
    needle = search_text.strip().lower()
    haystack_cols = ["address", "owner_name", "contractor_name", "permit_id"]
    mask = False
    for col in haystack_cols:
        mask = mask | filtered[col].fillna("").str.lower().str.contains(needle, regex=False)
    filtered = filtered[mask]

if date_range and isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
    filtered = filtered[
        filtered["filing_date"].isna()
        | ((filtered["filing_date"].dt.date >= start) & (filtered["filing_date"].dt.date <= end))
    ]

if val_range:
    low, high = val_range
    filtered = filtered[filtered["valuation"].isna() | ((filtered["valuation"] >= low) & (filtered["valuation"] <= high))]

# --- Summary metrics ------------------------------------------------------
m1, m2, m3, m4 = st.columns(4)
m1.metric("Permits matched", f"{len(filtered):,}")
m2.metric("Jurisdictions", filtered["jurisdiction"].nunique())
m3.metric("Total valuation", f"${filtered['valuation'].fillna(0).sum():,.0f}")
m4.metric("Avg valuation", f"${filtered['valuation'].dropna().mean():,.0f}" if filtered["valuation"].notna().any() else "N/A")

# --- Results table --------------------------------------------------------
display_cols = [
    "permit_id", "jurisdiction", "filing_date", "permit_type_normalized",
    "address", "owner_name", "contractor_name", "valuation", "square_footage", "scope_summary",
]
st.dataframe(
    filtered[display_cols].sort_values("filing_date", ascending=False, na_position="last"),
    use_container_width=True,
    hide_index=True,
)

# --- Detail view ------------------------------------------------------
st.subheader("Permit detail")
if filtered.empty:
    st.caption("No permits match the current filters.")
else:
    options = filtered.apply(
        lambda r: f"{r['permit_id']} -- {r['jurisdiction']} -- {r['address']}", axis=1
    ).tolist()
    choice = st.selectbox("Select a permit to inspect", options)
    if choice:
        idx = options.index(choice)
        row = filtered.iloc[idx]

        left, right = st.columns(2)
        with left:
            st.write("**Owner:**", row["owner_name"] or "—")
            st.write("**Contractor:**", row["contractor_name"] or "—")
            st.write("**Source:**", f"{row['source_format']} ({row['source_url'] or 'n/a'})")
            st.write("**Extracted at:**", row["extracted_at"])
        with right:
            systems = parse_building_systems(row["building_systems"])
            st.write("**Building systems:**", ", ".join(systems) if systems else "—")
            st.write("**Permit type (raw):**", row["permit_type_raw"] or "—")

        st.write("**Scope summary:**")
        st.write(row["scope_summary"] or "—")
        with st.expander("Raw scope of work"):
            st.write(row["raw_scope_of_work"] or "—")
