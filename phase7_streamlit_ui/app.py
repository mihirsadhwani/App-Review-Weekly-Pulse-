import streamlit as st
import os
import subprocess
import json
import pandas as pd
import plotly.express as px
import datetime

# Configuration
st.set_page_config(page_title="Groww Weekly Review Pulse", layout="wide")

# 6. Dark Mode Support
dark_mode = st.toggle("Dark Mode")

if dark_mode:
    st.markdown("""
        <style>
            .stApp {
                background-color: #121212;
                color: #e0e0e0;
            }
            h1, h2, h3, h4, p, span, label, div.stMarkdown p {
                color: #e0e0e0 !important;
            }
            /* Explicitly forcing standard Streamlit widget colors for dark mode */
            [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
                color: #e0e0e0 !important;
            }
            div[data-testid="stExpander"] {
                background-color: #1e1e1e !important;
                border: 1px solid #333333 !important;
            }
            p, .streamlit-expanderContent {
                color: #e0e0e0 !important;
            }
            .theme-card {
                background-color: #1e1e1e;
                border-left: 4px solid;
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 8px;
                color: #e0e0e0;
            }
            .stButton > button {
                background-color: #333333;
                color: white;
                border: 1px solid #555555;
            }
            .stButton > button:hover {
                background-color: #444444;
                color: white;
                border: 1px solid #777777;
            }
        </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
        <style>
            .theme-card {
                background-color: #f8f9fa;
                border-left: 4px solid;
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 8px;
                color: #111827;
            }
        </style>
    """, unsafe_allow_html=True)


# Paths
THEME_MAP_PATH = "phase3_theme_analysis/theme_map.json"
INSIGHTS_PATH = "phase4_insight_generation/insights.json"
PULSE_MD_PATH = "phase5_weekly_pulse/weekly_pulse.md"
REVIEWS_CLEANED_PATH = "phase2_review_cleaning/filtered_reviews.json"

# Load Data
theme_map_data = None
insights_data = None
pulse_md_data = None
reviews_data = None

if os.path.exists(THEME_MAP_PATH):
    with open(THEME_MAP_PATH, "r", encoding="utf-8") as f:
        theme_map_data = json.load(f)

if os.path.exists(INSIGHTS_PATH):
    with open(INSIGHTS_PATH, "r", encoding="utf-8") as f:
        insights_data = json.load(f)

if os.path.exists(PULSE_MD_PATH):
    with open(PULSE_MD_PATH, "r", encoding="utf-8") as f:
        pulse_md_data = f.read()
    report_time = os.path.getmtime(PULSE_MD_PATH)
    report_timestamp = datetime.datetime.fromtimestamp(report_time).strftime('%Y-%m-%d %H:%M:%S')
else:
    report_timestamp = "N/A"

if os.path.exists(REVIEWS_CLEANED_PATH):
    with open(REVIEWS_CLEANED_PATH, "r", encoding="utf-8") as f:
        reviews_data = json.load(f)


# 1. Header
st.markdown("# **Groww Weekly Review Pulse Dashboard**")
st.markdown("### AI-powered analysis of Groww Play Store reviews")
st.divider()

# 2. Control Panel
with st.container():
    col1, col2, col3 = st.columns(3)
    
    with col1:
        review_window = st.selectbox(
            "Review Window",
            ["Last 4 weeks", "Last 8 weeks", "Last 12 weeks"]
        )
        
    with col2:
        num_reviews = st.slider(
            "Number of Reviews to Analyse",
            min_value=50,
            max_value=500,
            value=300,
            step=50
        )
        
    with col3:
        email_recipient = st.text_input("**Recipient Email**", placeholder="user@example.com")
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        run_analysis_btn = st.button("Run Review Analysis", use_container_width=True)
    with btn_col2:
        send_email_btn = st.button("Send Weekly Report", use_container_width=True)

    if run_analysis_btn:
        phases = ['collect', 'clean', 'analyze', 'insight', 'pulse']
        st.write("#### Running Pipeline")
        progress_bar = st.progress(0, text="Initializing...")
        for i, phase in enumerate(phases):
            progress_bar.progress((i) / len(phases), text=f"Running phase: {phase}...")
            try:
                subprocess.run(["python", "main.py", "--phase", phase], capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as e:
                st.error(f"Error in {phase}")
                break
        progress_bar.progress(1.0, text="Analysis Complete!")
        st.rerun()

    if send_email_btn:
        if email_recipient:
            with st.spinner("Sending email..."):
                try:
                    subprocess.run(
                        ["python", "main.py", "--phase", "email", "--send", "--recipient", email_recipient],
                        capture_output=True, text=True, check=True
                    )
                    st.success("Email sent!")
                except subprocess.CalledProcessError as e:
                    st.error("Error sending email.")
        else:
            st.warning("Please enter an email address.")

st.divider()

# 3. Theme Distribution Section
st.header("Themes Detected")
if theme_map_data and 'themes' in theme_map_data:
    themes = theme_map_data['themes']
    theme_names = [t.get('label', t.get('theme_id')) for t in themes]
    theme_counts = [t.get('review_count', len(t.get('reviews', []))) for t in themes]
    
    df = pd.DataFrame({
        "Theme": theme_names,
        "Review Count": theme_counts
    })
    
    colors = ['#1df0e8', '#73ff4d', '#ccff29', '#f3ff1f', '#dcdde1']
    
    fig = px.pie(
        df, 
        values='Review Count', 
        names='Theme',
        color_discrete_sequence=colors,
        hole=0.0
    )
    
    fig.update_traces(
        textposition='inside', 
        textinfo='percent+label', 
        marker=dict(line=dict(color='#121212' if dark_mode else '#ffffff', width=1)),
        insidetextorientation='radial'
    )
    
    fig.update_layout(
        margin=dict(t=10, b=10, l=10, r=10),
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=400,
        font=dict(color='#ffffff' if dark_mode else '#000000')
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Theme Cards directly below the chart
    cols = st.columns(len(df))
    for i, row in df.iterrows():
        with cols[i]:
            perc = int(round(row["Review Count"] / df["Review Count"].sum() * 100, 0))
            color = colors[i % len(colors)]
            st.markdown(f'''
            <div class="theme-card" style="border-left-color: {color};">
                <div style="font-size: 14px; text-overflow: ellipsis; white-space: nowrap; overflow: hidden;">{row["Theme"]}</div>
                <div style="font-size: 24px; font-weight: 600;">{perc}%</div>
            </div>
            ''', unsafe_allow_html=True)
else:
    st.info("Theme data not available. Please run the analysis first.")

st.divider()

# 4. Process Metrics Section
reviews_analysed = len(reviews_data) if reviews_data else 0
themes_detected = len(theme_map_data.get('themes', [])) if theme_map_data else 0
insights_generated = len(insights_data.get('action_ideas', [])) if insights_data else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("Reviews", reviews_analysed)
m2.metric("Themes", themes_detected)
m3.metric("Insights", insights_generated)
m4.metric("Last Run", report_timestamp)

st.divider()

# 5. Weekly Report Viewer (Collapsible)
with st.expander("View Weekly Report"):
    if pulse_md_data:
        st.markdown(pulse_md_data)
    else:
        st.warning("No weekly report generated yet.")
