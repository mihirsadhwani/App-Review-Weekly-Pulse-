import streamlit as st
import os
import json
import pandas as pd
import plotly.express as px
import datetime

# Direct imports of service classes for Streamlit Cloud compatibility
from phase1_review_collection.services.collector import PlayStoreCollector
from phase2_review_cleaning.services.cleaner import ReviewCleaner
from phase3_theme_analysis.services.analyzer import ThemeAnalyzer
from phase4_insight_generation.services.insight_generator import InsightGenerator
from phase5_weekly_pulse.services.pulse_generator import PulseGenerator
from phase6_email_delivery.services.email_sender import EmailSender

# Paths for data persistence
RAW_REVIEWS_PATH = "phase1_review_collection/raw_reviews.json"
REVIEWS_CLEANED_PATH = "phase2_review_cleaning/filtered_reviews.json"
THEME_MAP_PATH = "phase3_theme_analysis/theme_map.json"
INSIGHTS_PATH = "phase4_insight_generation/insights.json"
PULSE_MD_PATH = "phase5_weekly_pulse/weekly_pulse.md"
PULSE_TXT_PATH = "phase5_weekly_pulse/weekly_pulse.txt"
EMAIL_MD_PATH = "phase6_email_delivery/email_draft.md"
EMAIL_TXT_PATH = "phase6_email_delivery/email_draft.txt"

# --- Page Configuration & Styling ---
st.set_page_config(
    page_title="Groww Weekly Pulse",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dark Mode Setup
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = True

with st.sidebar:
    st.title("Settings")
    st.session_state.dark_mode = st.toggle("Dark Mode UI", value=st.session_state.dark_mode)
    st.divider()
    st.markdown("### System Status")
    if os.path.exists(PULSE_MD_PATH):
        st.success("✅ Weekly Report Ready")
    else:
        st.warning("⚠️ No Report Found")

# Apply Dashboard Styling
if st.session_state.dark_mode:
    st.markdown("""
        <style>
            .stApp { background-color: #0E1117; color: #FFFFFF; }
            .metric-card { background-color: #1A1C24; border-radius: 10px; padding: 20px; border: 1px solid #2D2F39; }
            .stButton > button { width: 100%; border-radius: 8px; font-weight: 600; transition: all 0.3s; }
            .stButton > button:first-child { background-color: #00D09C; color: #121212; border: none; }
            .stButton > button:first-child:hover { background-color: #00F0B5; transform: translateY(-2px); }
            .report-box { background-color: #1A1C24; border-radius: 10px; padding: 25px; border: 1px solid #2D2F39; }
        </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
        <style>
            .metric-card { background-color: #F8F9FB; border-radius: 10px; padding: 20px; border: 1px solid #E6E8F1; }
            .stButton > button { width: 100%; border-radius: 8px; font-weight: 600; }
            .stButton > button:first-child { background-color: #00D09C; color: white; border: none; }
            .report-box { background-color: #FFFFFF; border-radius: 10px; padding: 25px; border: 1px solid #E6E8F1; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
        </style>
    """, unsafe_allow_html=True)

# --- Header ---
st.markdown("# **Groww Weekly Review Pulse Dashboard**")
st.markdown("#### AI-Powered Product Feedback Intelligence")
st.divider()

# --- Inputs Section ---
with st.container():
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        num_reviews = st.number_input("Number of Reviews", min_value=50, max_value=1000, value=300, step=50, help="Total reviews to scrape from Play Store")
    with c2:
        review_window = st.selectbox("Review Window", ["Last 4 weeks", "Last 8 weeks", "Last 12 weeks"], index=0)
    with c3:
        recipient_email = st.text_input("Recipient Email", placeholder="product-team@groww.in")

st.markdown("<br>", unsafe_allow_html=True)

# --- Action Buttons ---
b1, b2 = st.columns(2)

with b1:
    if st.button("Generate Weekly Pulse Report"):
        try:
            st.info("🚀 Initializing backend processing pipeline...")
            
            # Step 1: Collection
            st.write("📡 **Phase 1:** Scraping latest Play Store reviews...")
            collector = PlayStoreCollector('com.nextbillion.groww', count=num_reviews)
            collector.collect()
            
            # Step 2: Cleaning
            st.write("🧹 **Phase 2:** Filtering high-signal feedback...")
            cleaner = ReviewCleaner(RAW_REVIEWS_PATH, REVIEWS_CLEANED_PATH)
            cleaner.clean()
            
            # Step 3: Theme Analysis
            st.write("🧠 **Phase 3:** Identifying recurring themes (Groq Llama-3)...")
            analyzer = ThemeAnalyzer(REVIEWS_CLEANED_PATH, THEME_MAP_PATH)
            analyzer.analyze()
            
            # Step 4: Insight Generation
            st.write("💡 **Phase 4:** Crafting actionable product insights...")
            insight_gen = InsightGenerator(THEME_MAP_PATH, INSIGHTS_PATH)
            insight_gen.generate()
            
            # Step 5: Pulse Generation
            st.write("📝 **Phase 5:** Finalizing weekly report (Gemini 1.5)...")
            pulser = PulseGenerator(THEME_MAP_PATH, INSIGHTS_PATH, PULSE_MD_PATH, PULSE_TXT_PATH)
            pulser.generate()
            
            st.success("✨ Report generated successfully!")
            st.rerun() # Refresh to show new data
        except Exception as e:
            st.error(f"❌ Pipeline Failure: {str(e)}")

with b2:
    if st.button("Send Email Report"):
        if not recipient_email:
            st.warning("⚠️ Please provide a recipient email address.")
        elif not os.path.exists(PULSE_MD_PATH):
            st.error("⚠️ No report found. Please generate one first.")
        else:
            with st.spinner("📤 Communicating with SMTP server..."):
                try:
                    sender = EmailSender(PULSE_MD_PATH, EMAIL_MD_PATH, EMAIL_TXT_PATH)
                    # Note: We use .process() as it handles the actual delivery logic
                    sender.process(send_mode=True, recipient=recipient_email)
                    st.success(f"📧 Weekly Pulse sent to {recipient_email}")
                except Exception as e:
                    st.error(f"❌ Email Failure: {str(e)}")

st.divider()

# --- Metrics Visualization ---
if os.path.exists(THEME_MAP_PATH) and os.path.exists(REVIEWS_CLEANED_PATH):
    with open(THEME_MAP_PATH, 'r') as f:
        t_data = json.load(f)
    with open(REVIEWS_CLEANED_PATH, 'r') as f:
        r_data = json.load(f)
    
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Reviews Processed", r_data.get('review_count', 0))
    with m2:
        st.metric("Themes Identified", t_data.get('theme_count', 0))
    with m3:
        if os.path.exists(PULSE_MD_PATH):
            mtime = os.path.getmtime(PULSE_MD_PATH)
            st.metric("Last Updated", datetime.datetime.fromtimestamp(mtime).strftime('%d %b, %H:%M'))

    # Visual Chart
    themes_list = t_data.get('themes', [])
    if themes_list:
        chart_data = pd.DataFrame([
            {"Theme": t['label'], "Mentions": t['review_count']} 
            for t in themes_list
        ])
        fig = px.bar(
            chart_data, x="Mentions", y="Theme", orientation='h',
            color="Mentions", color_continuous_scale="Viridis",
            title="Theme Distribution"
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font_color="#FFFFFF" if st.session_state.dark_mode else "#000000"
        )
        st.plotly_chart(fig, use_container_width=True)

# --- Weekly Report Display ---
if os.path.exists(PULSE_MD_PATH):
    st.subheader("📁 Latest Weekly Report")
    with open(PULSE_MD_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    
    st.markdown(f'<div class="report-box">{content}</div>', unsafe_allow_html=True)
else:
    st.info("👋 Welcome! Click 'Generate Weekly Pulse Report' above to start the analysis.")
