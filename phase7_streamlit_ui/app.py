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

# --- Page Config ---
st.set_page_config(
    page_title="Groww Weekly Review Pulse Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Theme Toggle ---
theme_mode = st.toggle("Dark Mode", value=False)

# --- Global CSS ---
if theme_mode:
    bg_primary = "#0E1117"
    bg_card = "#1A1C24"
    border_color = "#2D2F39"
    text_primary = "#FFFFFF"
    text_secondary = "#A0AEC0"
    accent_green = "#00D09C"
else:
    bg_primary = "#F7F8FA"
    bg_card = "#FFFFFF"
    border_color = "#E8EBF0"
    text_primary = "#1A1D26"
    text_secondary = "#6B7280"
    accent_green = "#00B386"

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    .stApp {{
        background-color: {bg_primary} !important;
        color: {text_primary} !important;
        font-family: 'Inter', sans-serif !important;
    }}

    #MainMenu, footer, header {{visibility: hidden;}}

    .metric-mini {{
        background: {bg_card};
        border: 1px solid {border_color};
        border-radius: 10px;
        padding: 12px 16px;
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 0px;
    }}
    .metric-mini .metric-icon {{ font-size: 20px; }}
    .metric-mini .metric-info .metric-label {{
        font-size: 10px;
        color: {text_secondary};
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}
    .metric-mini .metric-info .metric-val {{
        font-size: 16px;
        font-weight: 700;
        color: {text_primary};
    }}

    .theme-pct-card {{
        background: {bg_card};
        border: 1px solid {border_color};
        border-radius: 10px;
        padding: 12px;
        text-align: center;
    }}
    .theme-pct-card .theme-label {{ font-size: 11px; color: {text_secondary}; margin-bottom: 4px; }}
    .theme-pct-card .theme-value {{ font-size: 20px; font-weight: 700; color: {text_primary}; }}

    .stButton > button {{
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s;
    }}
    
    .section-title {{
        font-size: 16px;
        font-weight: 600;
        color: {text_primary};
        margin-bottom: 12px;
    }}

    /* Customizing inputs for dark mode visibility */
    .stSelectbox label, .stSlider label, .stTextInput label {{
        color: {text_primary} !important;
    }}
    
    div[data-testid="stExpander"] {{
        background: {bg_card} !important;
        border: 1px solid {border_color} !important;
    }}
</style>
""", unsafe_allow_html=True)

# --- Load Data ---
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

# --- Top Header & Metrics (Compact) ---
review_count = reviews_data.get('review_count', 0) if (reviews_data and isinstance(reviews_data, dict)) else 0
theme_count = theme_map_data.get('theme_count', 0) if theme_map_data else 0
insight_count = len(insights_data.get('action_ideas', [])) if insights_data else 0
if os.path.exists(PULSE_MD_PATH):
    mtime = os.path.getmtime(PULSE_MD_PATH)
    last_run_str = datetime.datetime.fromtimestamp(mtime).strftime('%d %b, %H:%M')
else:
    last_run_str = "—"

t1, t2 = st.columns([3, 1])
with t1:
    st.markdown(f"<h1 style='margin:0; font-size:28px; color:{text_primary}'>📊 Groww Weekly Review Pulse</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='margin:0; font-size:14px; color:{text_secondary}'>AI-powered product feedback intelligence</p>", unsafe_allow_html=True)

st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(f"<div class='metric-mini'><div class='metric-icon'>📝</div><div class='metric-info'><div class='metric-label'>Reviews</div><div class='metric-val'>{review_count}</div></div></div>", unsafe_allow_html=True)
with m2:
    st.markdown(f"<div class='metric-mini'><div class='metric-icon'>🏷️</div><div class='metric-info'><div class='metric-label'>Themes</div><div class='metric-val'>{theme_count}</div></div></div>", unsafe_allow_html=True)
with m3:
    st.markdown(f"<div class='metric-mini'><div class='metric-icon'>💡</div><div class='metric-info'><div class='metric-label'>Insights</div><div class='metric-val'>{insight_count}</div></div></div>", unsafe_allow_html=True)
with m4:
    st.markdown(f"<div class='metric-mini'><div class='metric-icon'>🕒</div><div class='metric-info'><div class='metric-label'>Last Run</div><div class='metric-val'>{last_run_str}</div></div></div>", unsafe_allow_html=True)

st.markdown("<hr style='margin: 20px 0; border: 0; border-top: 1px solid "+border_color+"'>", unsafe_allow_html=True)

# --- Main Layout (Chart side-by-side with Controls) ---
left_col, right_col = st.columns([2, 1], gap="large")

with left_col:
    st.markdown(f"<div class='section-title'>Theme Distribution</div>", unsafe_allow_html=True)
    if theme_map_data and 'themes' in theme_map_data:
        themes_list = theme_map_data['themes']
        theme_labels = [t.get('label', t.get('theme_id', 'Unknown')) for t in themes_list]
        theme_counts = [t.get('review_count', len(t.get('reviews', []))) for t in themes_list]
        total_mentions = sum(theme_counts) if sum(theme_counts) > 0 else 1
        
        palette = ['#00D09C', '#5B5EA6', '#F0A500', '#E84855', '#3AAFB9']
        
        fig = go.Figure(data=[go.Pie(
            labels=theme_labels,
            values=theme_counts,
            hole=0.6,
            marker=dict(colors=palette, line=dict(color=bg_card, width=2)),
            textinfo='percent+label',
            textposition='outside',
            textfont=dict(size=12, color=text_primary)
        )])
        fig.update_layout(
            showlegend=False,
            margin=dict(t=30, b=30, l=30, r=30),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=350
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Mini cards for percentages
        sub_cols = st.columns(len(themes_list))
        for idx, t in enumerate(themes_list):
            label = t.get('label', 'Theme')
            val = round((t.get('review_count', 0) / total_mentions) * 100)
            with sub_cols[idx]:
                st.markdown(f"<div class='theme-pct-card'><div class='theme-label'>{label}</div><div class='theme-value'>{val}%</div></div>", unsafe_allow_html=True)
    else:
        st.info("No analysis data found. Use the panel to the right to generate a report.")

with right_col:
    st.markdown(f"<div class='section-title'>Analysis Controls</div>", unsafe_allow_html=True)
    
    review_win = st.selectbox("Review Window", ["Last 4 weeks", "Last 8 weeks", "Last 12 weeks"])
    num_to_analyze = st.slider("Number of Reviews", 50, 500, 300, 50)
    email_target = st.text_input("Recipient Email", placeholder="user@example.com")
    
    if st.button("🚀 Generate Weekly Pulse Report", type="primary", use_container_width=True):
        try:
            with st.status("Running analysis...", expanded=True) as status:
                st.write("📡 Scraping reviews...")
                collector = PlayStoreCollector('com.nextbillion.groww', count=num_to_analyze)
                collector.collect()
                
                st.write("🧹 Cleaning data...")
                cleaner = ReviewCleaner(RAW_REVIEWS_PATH, REVIEWS_CLEANED_PATH)
                cleaner.clean()
                
                st.write("🧠 Analyzing themes...")
                analyzer = ThemeAnalyzer(REVIEWS_CLEANED_PATH, THEME_MAP_PATH)
                analyzer.analyze()
                
                st.write("💡 Generating insights...")
                insight_gen = InsightGenerator(THEME_MAP_PATH, INSIGHTS_PATH)
                insight_gen.generate()
                
                st.write("📝 Finalizing report...")
                pulser = PulseGenerator(THEME_MAP_PATH, INSIGHTS_PATH, PULSE_MD_PATH, PULSE_TXT_PATH)
                pulser.generate()
                
                status.update(label="✅ Analysis Complete!", state="complete", expanded=False)
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    if st.button("📧 Send Email Report", use_container_width=True):
        if not email_target:
            st.warning("Recipient email is required.")
        elif not os.path.exists(PULSE_MD_PATH):
            st.error("No report exists to send.")
        else:
            with st.spinner("Sending..."):
                try:
                    sender = EmailSender(PULSE_MD_PATH, EMAIL_MD_PATH, EMAIL_TXT_PATH)
                    sender.process(send_mode=True, recipient=email_target)
                    st.success("Report sent successfully!")
                except Exception as e:
                    st.error(f"Failed to send: {e}")

# --- Collapsible Report ---
st.markdown("<br>", unsafe_allow_html=True)
if pulse_md_content:
    with st.expander("📄 View Weekly Report", expanded=False):
        st.markdown(pulse_md_content)
