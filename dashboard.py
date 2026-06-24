

import streamlit as st

# --- USERS ---
USERS = {
    "agent1": "1234",
    "manager": "admin"
}

def login():
    st.title("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username in USERS and USERS[username] == password:
            st.session_state["authenticated"] = True
            st.session_state["user"] = username
            st.rerun()
        else:
            st.error("Invalid credentials")

# --- SESSION STATE ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# --- BLOCK APP ---
if not st.session_state["authenticated"]:
    login()
    st.stop()

import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# === CONFIG ===
file_path = r"C:\operations\processed_report.xlsx"
csv_input_folder = r"C:\Operations"

st.set_page_config(page_title="Operations Dashboard", layout="wide")
st.title("📊 Exception Dashboard")

# === AUTO REFRESH ===
st_autorefresh(interval=30 * 1000, key="refresh")

# === FILE MODIFIED TIME ===
def get_file_modified_time():
    return os.path.getmtime(file_path)

# === GET LATEST CSV INPUT FILE ===
def get_latest_csv_file():
    if not os.path.exists(csv_input_folder):
        return None

    files = [
        f for f in os.listdir(csv_input_folder)
        if f.lower().endswith(".csv")
    ]

    if not files:
        return None

    latest = max(
        files,
        key=lambda x: os.path.getmtime(os.path.join(csv_input_folder, x))
    )

    return os.path.join(csv_input_folder, latest)

# === SAFE READ ===
def safe_read(sheet):
    for _ in range(5):
        try:
            return pd.read_excel(file_path, sheet_name=sheet)
        except:
            time.sleep(1)
    raise Exception(f"File locked: {sheet}")

# === BUILD CREATED AND PAID EXCEPTIONS FROM CSV ===
def build_created_and_paid_exceptions(csv_df, target_columns):
    target_columns = list(target_columns)

    if csv_df.empty:
        return pd.DataFrame(columns=target_columns)

    required_cols = ["status", "payingpartner", "lcbalance"]

    if not all(col in csv_df.columns for col in required_cols):
        return pd.DataFrame(columns=target_columns)

    created_and_paid = csv_df[
        (csv_df["status"].astype(str).str.strip().str.upper() == "CREATED") &
        (csv_df["payingpartner"].astype(str).str.strip().str.upper() == "PAYAT") &
        (pd.to_numeric(csv_df["lcbalance"], errors="coerce").fillna(0) == 0)
    ].copy()

    if created_and_paid.empty:
        return pd.DataFrame(columns=target_columns)

    if "serialno" in created_and_paid.columns:
        created_and_paid["serialno"] = created_and_paid["serialno"].astype(str).str.strip()
        created_and_paid = created_and_paid.drop_duplicates("serialno", keep="last")

    exception_df = pd.DataFrame()

    for col in target_columns:
        if col in created_and_paid.columns:
            exception_df[col] = created_and_paid[col]
        else:
            exception_df[col] = ""

    exception_df["status"] = "CREATED AND PAID"

    if "payingpartner" in exception_df.columns:
        exception_df["payingpartner"] = created_and_paid["payingpartner"].astype(str).str.strip()

    if "transaction amount" in exception_df.columns and "lctotal" in created_and_paid.columns:
        exception_df["transaction amount"] = pd.to_numeric(
            created_and_paid["lctotal"],
            errors="coerce"
        ).fillna(0)

    if "short paid" in exception_df.columns and "lcbalance" in created_and_paid.columns:
        exception_df["short paid"] = pd.to_numeric(
            created_and_paid["lcbalance"],
            errors="coerce"
        ).fillna(0)

    if "date" in exception_df.columns and "date" in created_and_paid.columns:
        exception_df["date"] = pd.to_datetime(created_and_paid["date"], errors="coerce")

    return exception_df


# LOAD DATA

@st.cache_data
def load_data(file_mtime, csv_file_path, csv_file_mtime):
    log_df = safe_read("Exception_Log")
    summary_df = safe_read("Exception_Summary")
    live_df = safe_read("Exceptions")

    log_df.columns = log_df.columns.str.lower().str.strip()
    live_df.columns = live_df.columns.str.lower().str.strip()

    csv_df = pd.DataFrame()
    payingpartner_map = {}

    if csv_file_path:
        csv_df = pd.read_csv(csv_file_path)
        csv_df.columns = csv_df.columns.str.lower().str.strip()

        if "serialno" in csv_df.columns and "payingpartner" in csv_df.columns:
            csv_df["serialno"] = csv_df["serialno"].astype(str).str.strip()
            csv_df["payingpartner"] = csv_df["payingpartner"].astype(str).str.strip()

            payingpartner_map = (
                csv_df.drop_duplicates("serialno", keep="last")
                .set_index("serialno")["payingpartner"]
                .to_dict()
            )

    for df in [log_df, live_df]:
        if "serialno" in df.columns:
            df["serialno"] = df["serialno"].astype(str).str.strip()
            df["payingpartner"] = df["serialno"].map(payingpartner_map).fillna("")
        else:
            df["payingpartner"] = ""

    created_and_paid_live = build_created_and_paid_exceptions(csv_df, live_df.columns)
    created_and_paid_log = build_created_and_paid_exceptions(csv_df, log_df.columns)

    if not created_and_paid_live.empty:
        if "serialno" in live_df.columns and "serialno" in created_and_paid_live.columns:
            live_df = live_df[
                ~live_df["serialno"].astype(str).str.strip().isin(
                    created_and_paid_live["serialno"].astype(str).str.strip()
                )
            ]

        live_df = pd.concat([live_df, created_and_paid_live], ignore_index=True)

    if not created_and_paid_log.empty:
        if "serialno" in log_df.columns and "serialno" in created_and_paid_log.columns:
            log_df = log_df[
                ~log_df["serialno"].astype(str).str.strip().isin(
                    created_and_paid_log["serialno"].astype(str).str.strip()
                )
            ]

        log_df = pd.concat([log_df, created_and_paid_log], ignore_index=True)

    # DATE
    possible_dates = ["date", "transaction date", "created date"]
    for df in [log_df, live_df]:
        date_col = next((c for c in possible_dates if c in df.columns), None)
        if date_col:
            df["date"] = pd.to_datetime(df[date_col], errors="coerce")

    return log_df, summary_df, live_df

# LOAD
file_mtime = get_file_modified_time()

csv_file_path = get_latest_csv_file()
csv_file_mtime = os.path.getmtime(csv_file_path) if csv_file_path else 0

log_df, summary_df, live_df = load_data(file_mtime, csv_file_path, csv_file_mtime)

st.caption(f"Last updated: {datetime.fromtimestamp(file_mtime)}")

if csv_file_path:
    st.caption(f"CSV checked for CREATED AND PAID: {os.path.basename(csv_file_path)}")


# FILTERS

st.sidebar.header("Filters")

# === DATE FILTER ===
min_date = pd.concat([log_df["date"], live_df["date"]]).min()
max_date = pd.concat([log_df["date"], live_df["date"]]).max()

date_range = st.sidebar.date_input("Date Range", [min_date, max_date])


# 🔥 FIXED STATUS FILTER (FROM FULL HISTORY)

all_statuses = sorted(log_df["status"].dropna().unique())

# Count from LIVE (current report)
live_counts = live_df["status"].value_counts().to_dict()

# Create labels with counts
status_labels = [
    f"{status} ({live_counts.get(status, 0)})"
    for status in all_statuses
]

# Map label → actual status
label_to_status = dict(zip(status_labels, all_statuses))

selected_labels = st.sidebar.multiselect(
    "Select Status",
    options=status_labels,
    default=status_labels
)

# Convert back to real statuses
status_filter = [label_to_status[label] for label in selected_labels]


# APPLY FILTERS

filtered_log = log_df.copy()
filtered_live = live_df.copy()

# Status filter
filtered_live = filtered_live[filtered_live["status"].isin(status_filter)]
filtered_log = filtered_log[filtered_log["status"].isin(status_filter)]

# Date filter
if len(date_range) == 2:
    start, end = date_range

    filtered_log = filtered_log[
        (filtered_log["date"] >= pd.to_datetime(start)) &
        (filtered_log["date"] <= pd.to_datetime(end))
    ]

    filtered_live = filtered_live[
        (filtered_live["date"] >= pd.to_datetime(start)) &
        (filtered_live["date"] <= pd.to_datetime(end))
    ]


# KPI CALCULATIONS

total_logged = len(filtered_log)
pending = len(filtered_live)

solved = filtered_log[
    ~filtered_log['serialno'].isin(filtered_live['serialno'])
]['serialno'].nunique()

# KPI DISPLAY
col1, col2, col3 = st.columns(3)

col1.metric("Total Exceptions Logged", total_logged)
col2.metric("Pending Exceptions", pending)
col3.metric("Solved Exceptions", solved)


# CHART

st.subheader("Exceptions by Category")

chart_data = filtered_live['status'].value_counts().sort_values()
st.bar_chart(chart_data)


# LIVE EXCEPTIONS

st.subheader("🚨 Live Exceptions (Current)")
st.dataframe(filtered_live, use_container_width=True)


# DETAILED LOG

st.subheader("📄 Detailed Exception Log")
st.dataframe(filtered_log, use_container_width=True)


# SUMMARY

st.subheader("📊 Summary (All Time)")
st.dataframe(summary_df, use_container_width=True)


# STATUS


st.success("🟢 Dashboard synced with latest processed report")