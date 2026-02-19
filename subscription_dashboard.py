import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Subscriptions",
    page_icon="$",
    layout="wide",
)

# --- Data (parsed from SecondBrain markdown) ---

active_subs = pd.DataFrame([
    {"name": "Anthropic Claude", "type": "AI", "cycle": "Monthly", "cost_monthly": 100.0, "renewal": "Monthly (3rd)"},
    {"name": "OpenAI ChatGPT Plus", "type": "AI", "cycle": "Monthly", "cost_monthly": 20.0, "renewal": "Monthly"},
    {"name": "Gym (Pankaj)", "type": "Health", "cycle": "Monthly", "cost_monthly": 26.0, "renewal": "Monthly"},
    {"name": "Gym (Utkarsha)", "type": "Health", "cycle": "Monthly", "cost_monthly": 13.0, "renewal": "Monthly"},
    {"name": "WHOOP", "type": "Health", "cycle": "Annual", "cost_monthly": 199 / 12, "renewal": "Nov 2026"},
    {"name": "TurboTax", "type": "Tax", "cycle": "Annual", "cost_monthly": 138 / 12, "renewal": "Feb"},
    {"name": "Wispr Flow", "type": "Productivity", "cycle": "Annual", "cost_monthly": 96 / 12, "renewal": "Feb 2026"},
    {"name": "X Premium", "type": "Social", "cycle": "Annual", "cost_monthly": 44.36 / 12, "renewal": "Dec 2026"},
    {"name": "Apple iCloud+", "type": "Storage", "cycle": "Monthly", "cost_monthly": 0.99, "renewal": "Monthly (5th)"},
    {"name": "Airtel IR Pack", "type": "Telecom", "cycle": "Annual", "cost_monthly": 48 / 12, "renewal": "Dec 2026"},
    {"name": "Chase Sapphire Preferred", "type": "Credit Card", "cycle": "Annual", "cost_monthly": 100 / 12, "renewal": "Annual"},
    {"name": "AMEX Platinum", "type": "Credit Card", "cycle": "Annual", "cost_monthly": 896 / 12, "renewal": "Annual"},
    {"name": "Hetzner VPS", "type": "Infrastructure", "cycle": "Monthly", "cost_monthly": 4.0, "renewal": "Monthly (5th)"},
])

active_subs["cost_annual"] = active_subs["cost_monthly"] * 12

student_plans = pd.DataFrame([
    {"name": "Cursor Pro", "normal_price": "$20/mo", "status": "Free (1 yr)", "expiry": "Feb 2027", "action": "Cancel before auto-charge"},
    {"name": "1Password", "normal_price": "$36/yr", "status": "Free (1 yr)", "expiry": "Feb 2027", "action": "Cancel or renew via GitHub Student Pack"},
    {"name": "GitHub Copilot", "normal_price": "$10/mo", "status": "Free", "expiry": "~Feb 2027", "action": "Renewable while student"},
    {"name": "Google Gemini", "normal_price": "$20/mo", "status": "Free", "expiry": "-", "action": "No action needed"},
    {"name": "Perplexity AI", "normal_price": "$20/mo", "status": "Free", "expiry": "Aug 2026", "action": "Cancel before auto-charge"},
])

monthly_2025 = pd.DataFrame([
    {"month": "Jan", "total": 59},
    {"month": "Feb", "total": 293},
    {"month": "Mar", "total": 59.99},
    {"month": "Apr", "total": 59.99},
    {"month": "May", "total": 59.99},
    {"month": "Jun", "total": 59.99},
    {"month": "Jul", "total": 166.40},
    {"month": "Aug", "total": 159.99},
    {"month": "Sep", "total": 67.99},
    {"month": "Oct", "total": 87.99},
    {"month": "Nov", "total": 286.99},
    {"month": "Dec", "total": 373.30},
])

monthly_2026 = pd.DataFrame([
    {"month": "Jan", "total": 159.99},
    {"month": "Feb", "total": 397.99},
    {"month": "Mar", "total": 163.99},
    {"month": "Apr", "total": 163.99},
    {"month": "May", "total": 163.99},
    {"month": "Jun", "total": 163.99},
    {"month": "Jul", "total": 163.99},
    {"month": "Aug", "total": 163.99},
    {"month": "Sep", "total": 163.99},
    {"month": "Oct", "total": 163.99},
    {"month": "Nov", "total": 362.99},
    {"month": "Dec", "total": 1252.35},
])

# --- Category breakdown ---

category_spending = active_subs.groupby("type")["cost_annual"].sum().sort_values(ascending=False).reset_index()
category_spending.columns = ["Category", "Annual Cost"]

# --- Header ---

st.title("Subscription Tracker")

col1, col2, col3 = st.columns(3)
col1.metric("2025 Actual", "$1,735", delta=None)
col2.metric("2026 Projected", "$3,485", delta="+101%", delta_color="inverse")
col3.metric("Monthly Avg (2026)", f"${3485/12:.0f}")

st.divider()

def get_expiry_alerts(plans_df, today_str="2026-02-19"):
    from datetime import datetime, timedelta
    today = datetime.strptime(today_str, "%Y-%m-%d")
    cutoff = today + timedelta(days=180)
    alerts = []
    for _, row in plans_df.iterrows():
        raw = row["expiry"].strip().lstrip("~")
        if raw == "-" or not raw:
            continue
        try:
            expiry = datetime.strptime(raw, "%b %Y")
        except ValueError:
            continue
        if today <= expiry <= cutoff:
            alerts.append(f"{row['name']} expires {row['expiry']} — {row['action']}")
    return alerts


alerts = get_expiry_alerts(student_plans)
if alerts:
    for alert in alerts:
        st.warning(alert)

# --- Tabs ---

tab1, tab2, tab3, tab4 = st.tabs([
    "Monthly Trend",
    "By Category",
    "Active Subs",
    "Student Plans",
])

with tab1:
    year = st.radio("Year", ["2025", "2026"], horizontal=True)
    data = monthly_2025 if year == "2025" else monthly_2026
    st.bar_chart(data, x="month", y="total", color="#4A90D9")

with tab2:
    st.bar_chart(
        category_spending,
        x="Category",
        y="Annual Cost",
        color="#E8734A",
        horizontal=True,
    )

with tab3:
    display_df = active_subs[["name", "type", "cycle", "cost_monthly", "cost_annual", "renewal"]].copy()
    display_df.columns = ["Name", "Type", "Cycle", "$/Month", "$/Year", "Renewal"]
    display_df["$/Month"] = display_df["$/Month"].apply(lambda x: f"${x:.2f}")
    display_df["$/Year"] = display_df["$/Year"].apply(lambda x: f"${x:.2f}")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

with tab4:
    st.dataframe(student_plans, use_container_width=True, hide_index=True)
    savings = (20 + 36/12 + 10 + 20 + 20)  # monthly value of free plans
    st.info(f"Student plans saving you ~${savings:.0f}/month (${savings*12:.0f}/year)")
