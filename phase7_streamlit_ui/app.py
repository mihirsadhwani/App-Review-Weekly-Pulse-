import sys
import os
import streamlit as st
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime

# Fix for Streamlit Cloud: Add project root to sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Direct imports of service classes for Streamlit Cloud compatibility
from phase1_review_collection.services.collector import PlayStoreCollector
from phase2_review_cleaning.services.cleaner import ReviewCleaner
from phase3_theme_analysis.services.analyzer import ThemeAnalyzer
from phase4_insight_generation.services.insight_generator import InsightGenerator
from phase5_weekly_pulse.services.pulse_generator import PulseGenerator
from phase6_email_delivery.services.email_sender import EmailSender

# --- Data Paths ---
RAW_REVIEWS_PATH = "phase1_review_collection/raw_reviews.json"
REVIEWS_CLEANED_PATH = "phase2_review_cleaning/filtered_reviews.json"
THEME_MAP_PATH = "phase3_theme_analysis/theme_map.json"
INSIGHTS_PATH = "phase4_insight_generation/insights.json"
PULSE_MD_PATH = "phase5_weekly_pulse/weekly_pulse.md"
PULSE_TXT_PATH = "phase5_weekly_pulse/weekly_pulse.txt"
EMAIL_MD_PATH = "phase6_email_delivery/email_draft.md"
EMAIL_TXT_PATH = "phase6_email_delivery/email_draft.txt"

# --- Page Config (Light Mode, Collapsed Sidebar) ---
st.set_page_config(
    page_title="Groww Weekly Review Pulse Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Global CSS ---
st.markdown("""
<style>
    /* Import Google Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Root variables */
    :root {
        --bg-primary: #F7F8FA;
        --bg-card: #FFFFFF;
        --border-color: #E8EBF0;
        --text-primary: #1A1D26;
        --text-secondary: #6B7280;
        --accent-green: #00B386;
        --accent-green-hover: #009973;
    }

    /* Base App */
    .stApp {
        background-color: var(--bg-primary) !important;
        font-family: 'Inter', sans-serif !important;
    }

    /* Hide default Streamlit menu & footer */
    #MainMenu, footer, header {visibility: hidden;}

    /* Card container */
    .ui-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 16px;
    }
    .ui-card h3 {
        font-size: 15px;
        font-weight: 600;
        color: var(--text-primary);
        margin: 0 0 16px 0;
    }

    /* Theme percentage cards */
    .theme-pct-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 10px;
        padding: 16px 12px;
        text-align: center;
        transition: box-shadow 0.2s ease;
    }
    .theme-pct-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    }
    .theme-pct-card .theme-icon {
        width: 36px;
        height: 36px;
        border-radius: 8px;
        margin: 0 auto 8px auto;
    }
    .theme-pct-card .theme-label {
        font-size: 12px;
        color: var(--text-secondary);
        margin-bottom: 4px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .theme-pct-card .theme-value {
        font-size: 22px;
        font-weight: 700;
        color: var(--text-primary);
    }

    /* Metric mini cards */
    .metric-mini {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 10px;
        padding: 14px 18px;
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 10px;
    }
    .metric-mini .metric-icon {
        font-size: 22px;
    }
    .metric-mini .metric-info .metric-label {
        font-size: 11px;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-mini .metric-info .metric-val {
        font-size: 18px;
        font-weight: 700;
        color: var(--text-primary);
    }

    /* Buttons */
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        font-size: 14px;
        padding: 10px 20px;
        transition: all 0.2s ease;
        border: none;
    }

    /* Header styling */
    .dashboard-header {
        padding: 8px 0 4px 0;
    }
    .dashboard-header h1 {
        font-size: 26px;
        font-weight: 700;
        color: var(--text-primary);
        margin: 0;
    }
    .dashboard-header p {
        font-size: 14px;
        color: var(--text-secondary);
        margin: 4px 0 0 0;
    }

    /* Section titles */
    .section-title {
        font-size: 15px;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 12px;
    }

    /* Responsive: stack on small screens */
    @media (max-width: 768px) {
        .stButton > button {
            font-size: 13px;
            padding: 12px 16px;
        }
    }
</style>
""", unsafe_allow_html=True)

# --- Load existing data ---
theme_map_data = None
insights_data = None
pulse_md_content = None
reviews_data = None

if os.path.exists(THEME_MAP_PATH):
    with open(THEME_MAP_PATH, "r", encoding="utf-8") as f:
        theme_map_data = json.load(f)

if os.path.exists(INSIGHTS_PATH):
    with open(INSIGHTS_PATH, "r", encoding="utf-8") as f:
        insights_data = json.load(f)

if os.path.exists(PULSE_MD_PATH):
    with open(PULSE_MD_PATH, "r", encoding="utf-8") as f:
        pulse_md_content = f.read()

if os.path.exists(REVIEWS_CLEANED_PATH):
    with open(REVIEWS_CLEANED_PATH, "r", encoding="utf-8") as f:
        reviews_data = json.load(f)

# --- Header ---
st.markdown("""
<div class="dashboard-header">
    <h1>📊 Groww Weekly Review Pulse Dashboard</h1>
    <p>AI-powered analysis of Groww Play Store reviews</p>
</div>
""", unsafe_allow_html=True)
st.markdown("")

# --- Metrics Row ---
review_count = reviews_data.get('review_count', 0) if (reviews_data and isinstance(reviews_data, dict)) else 0
theme_count = theme_map_data.get('theme_count', 0) if theme_map_data else 0
insight_count = len(insights_data.get('action_ideas', [])) if insights_data else 0
if os.path.exists(PULSE_MD_PATH):
    mtime = os.path.getmtime(PULSE_MD_PATH)
    last_run_str = datetime.datetime.fromtimestamp(mtime).strftime('%d %b %Y, %H:%M')
else:
    last_run_str = "—"

mc1, mc2, mc3, mc4 = st.columns(4)
with mc1:
    st.markdown(f"""
    <div class="metric-mini">
        <div class="metric-icon">📝</div>
        <div class="metric-info">
            <div class="metric-label">Reviews</div>
            <div class="metric-val">{review_count}</div>
        </div>
    </div>""", unsafe_allow_html=True)
with mc2:
    st.markdown(f"""
    <div class="metric-mini">
        <div class="metric-icon">🏷️</div>
        <div class="metric-info">
            <div class="metric-label">Themes</div>
            <div class="metric-val">{theme_count}</div>
        </div>
    </div>""", unsafe_allow_html=True)
with mc3:
    st.markdown(f"""
    <div class="metric-mini">
        <div class="metric-icon">💡</div>
        <div class="metric-info">
            <div class="metric-label">Insights</div>
            <div class="metric-val">{insight_count}</div>
        </div>
    </div>""", unsafe_allow_html=True)
with mc4:
    st.markdown(f"""
    <div class="metric-mini">
        <div class="metric-icon">🕒</div>
        <div class="metric-info">
            <div class="metric-label">Last Run</div>
            <div class="metric-val">{last_run_str}</div>
        </div>
    </div>""", unsafe_allow_html=True)

st.markdown("")

# ============================================================
# MAIN TWO-COLUMN LAYOUT
# Left: Chart + Theme Cards | Right: Controls + Actions
# ============================================================
left_col, right_col = st.columns([3, 2], gap="large")

# --- LEFT COLUMN: Theme Distribution ---
with left_col:
    st.markdown('<div class="section-title">Theme Distribution</div>', unsafe_allow_html=True)

    if theme_map_data and 'themes' in theme_map_data:
        themes_list = theme_map_data['themes']
        theme_labels = [t.get('label', t.get('theme_id', 'Unknown')) for t in themes_list]
        theme_counts = [t.get('review_count', len(t.get('reviews', []))) for t in themes_list]
        total_mentions = sum(theme_counts) if sum(theme_counts) > 0 else 1

        # Color palette
        palette = ['#00B386', '#5B5EA6', '#F0A500', '#E84855', '#3AAFB9']

        # Donut Chart
        fig = go.Figure(data=[go.Pie(
            labels=theme_labels,
            values=theme_counts,
            hole=0.55,
            marker=dict(colors=palette[:len(theme_labels)], line=dict(color='#FFFFFF', width=2)),
            textinfo='percent+label',
            textposition='outside',
            textfont=dict(size=12, color='#1A1D26'),
            pull=[0.03] * len(theme_labels)
        )])
        fig.update_layout(
            showlegend=False,
            margin=dict(t=20, b=20, l=20, r=20),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=380,
            font=dict(family='Inter', color='#1A1D26')
        )
        st.plotly_chart(fig, use_container_width=True, key="theme_donut")

        # Theme Percentage Cards
        card_cols = st.columns(len(themes_list))
        for idx, t in enumerate(themes_list):
            label = t.get('label', t.get('theme_id', 'Theme'))
            count = t.get('review_count', 0)
            pct = round((count / total_mentions) * 100)
            color = palette[idx % len(palette)]
            with card_cols[idx]:
                st.markdown(f"""
                <div class="theme-pct-card">
                    <div class="theme-icon" style="background:{color};"></div>
                    <div class="theme-label" title="{label}">{label}</div>
                    <div class="theme-value">{pct}%</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No theme data available yet. Run the analysis to see the distribution.")

# --- RIGHT COLUMN: Controls & Actions ---
with right_col:
    # Inputs Card
    st.markdown('<div class="section-title">Analysis Controls</div>', unsafe_allow_html=True)

    review_window = st.selectbox(
        "Review Window",
        ["Last 4 weeks", "Last 8 weeks", "Last 12 weeks"],
        index=0
    )

    num_reviews = st.slider(
        "Number of Reviews to Analyse",
        min_value=50, max_value=500, value=300, step=50
    )

    recipient_email = st.text_input(
        "Recipient Email",
        placeholder="product-team@groww.in"
    )

    st.markdown("")

    # Action Buttons
    if st.button("🚀  Generate Weekly Pulse Report", use_container_width=True, type="primary"):
        try:
            st.info("Initializing pipeline...")

            st.write("📡 **Phase 1/5:** Collecting Play Store reviews...")
            collector = PlayStoreCollector('com.nextbillion.groww', count=num_reviews)
            collector.collect()

            st.write("🧹 **Phase 2/5:** Filtering reviews...")
            cleaner = ReviewCleaner(RAW_REVIEWS_PATH, REVIEWS_CLEANED_PATH)
            cleaner.clean()

            st.write("🧠 **Phase 3/5:** Analyzing themes (Groq Llama-3)...")
            analyzer = ThemeAnalyzer(REVIEWS_CLEANED_PATH, THEME_MAP_PATH)
            analyzer.analyze()

            st.write("💡 **Phase 4/5:** Generating insights...")
            insight_gen = InsightGenerator(THEME_MAP_PATH, INSIGHTS_PATH)
            insight_gen.generate()

            st.write("📝 **Phase 5/5:** Creating pulse report (Gemini)...")
            pulser = PulseGenerator(THEME_MAP_PATH, INSIGHTS_PATH, PULSE_MD_PATH, PULSE_TXT_PATH)
            pulser.generate()

            st.success("✅ Report generated successfully!")
            st.rerun()
        except Exception as e:
            st.error(f"Pipeline Error: {str(e)}")

    st.markdown("")

    if st.button("📧  Send Email Report", use_container_width=True):
        if not recipient_email:
            st.warning("Please enter a recipient email address.")
        elif not os.path.exists(PULSE_MD_PATH):
            st.error("No report found. Generate one first.")
        else:
            with st.spinner("Sending email..."):
                try:
                    sender = EmailSender(PULSE_MD_PATH, EMAIL_MD_PATH, EMAIL_TXT_PATH)
                    sender.process(send_mode=True, recipient=recipient_email)
                    st.success(f"Email sent to {recipient_email}")
                except Exception as e:
                    st.error(f"Email Error: {str(e)}")

# ============================================================
# COLLAPSIBLE WEEKLY REPORT
# ============================================================
st.markdown("")
st.divider()

if os.path.exists(PULSE_MD_PATH) and pulse_md_content:
    with st.expander("📄 View Weekly Report", expanded=False):
        st.markdown(pulse_md_content)
