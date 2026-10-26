import sys
import os
import re
import json
import html
import datetime
import textwrap

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# Streamlit Cloud: make the project root importable
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from services.config_loader import get_config
from services import orchestrator as orch
from services import usage as usage_svc
from services.usage import fmt_usd
from phase2_review_cleaning.services.cleaner import scrub_pii
from phase6_email_delivery.services.email_sender import EmailSender

st.set_page_config(
    page_title="Weekly Review Pulse",
    page_icon=":material/monitoring:",
    layout="wide",
    initial_sidebar_state="auto",
)

# ---------------------------------------------------------------------------
# Design tokens (shadcn/ui, zinc scale)
# ---------------------------------------------------------------------------
TOKENS = {
    "light": dict(
        background="#FFFFFF", foreground="#09090B", card="#FFFFFF", muted="#F4F4F5", muted_fg="#71717A",
        border="#E4E4E7", primary="#18181B", primary_fg="#FAFAFA", secondary="#F4F4F5",
        sidebar="#FAFAFA", accent="#F4F4F5", success="#15803D", success_bg="#F0FDF4",
        warning="#B45309", warning_bg="#FFFBEB", destructive="#DC2626", destructive_bg="#FEF2F2",
        ring="rgba(24,24,27,.18)", shadow="0 1px 2px rgba(0,0,0,.05)",
        chart=["#2563EB", "#16A34A", "#EA580C", "#DC2626", "#9333EA"],
    ),
    "dark": dict(
        background="#09090B", foreground="#FAFAFA", card="#0F0F12", muted="#18181B", muted_fg="#A1A1AA",
        border="#27272A", primary="#FAFAFA", primary_fg="#18181B", secondary="#27272A",
        sidebar="#0C0C0F", accent="#27272A", success="#4ADE80", success_bg="rgba(74,222,128,.10)",
        warning="#FBBF24", warning_bg="rgba(251,191,36,.10)", destructive="#F87171", destructive_bg="rgba(248,113,113,.10)",
        ring="rgba(250,250,250,.2)", shadow="none",
        chart=["#60A5FA", "#4ADE80", "#FB923C", "#F87171", "#C084FC"],
    ),
}

dark = st.session_state.get("dark_mode", False)
T = TOKENS["dark" if dark else "light"]

ICON_FONT = "'MSR Fill', 'Material Symbols Rounded'"


def inject_css(sb_count_css: str = ""):
    SB_COUNT_CSS = sb_count_css
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');
@font-face {{
  font-family: 'MSR Fill';
  font-style: normal; font-weight: 400; font-display: block;
  src: url(https://fonts.gstatic.com/s/materialsymbolsrounded/v381/syl0-zNym6YjUruM-QrEh7-nyTnjDwKNJ_190FjpZIvDmUSVOK7BDB_Qb9vUSzq3wzLK-P0J-V_Zs-QtQth3-jOcbTCVpeRL2w5rwZu2rIelXxI.ttf) format('truetype');
}}

:root {{
  --background:{T['background']}; --foreground:{T['foreground']}; --card:{T['card']}; --muted:{T['muted']};
  --muted-foreground:{T['muted_fg']}; --border:{T['border']}; --primary:{T['primary']}; --primary-foreground:{T['primary_fg']};
  --secondary:{T['secondary']}; --sidebar:{T['sidebar']}; --accent:{T['accent']}; --success:{T['success']};
  --success-bg:{T['success_bg']}; --warning:{T['warning']}; --warning-bg:{T['warning_bg']};
  --destructive:{T['destructive']}; --destructive-bg:{T['destructive_bg']}; --ring:{T['ring']};
  --shadow:{T['shadow']}; --radius:10px;
}}

/* Manrope on every text element; icon fonts excepted */
html, body, .stApp, .stApp *:not([data-testid="stIconMaterial"]):not([role="img"]):not(.ms):not(svg *) {{
  font-family: 'Manrope', sans-serif !important;
}}
.ms, [data-testid="stIconMaterial"], span[role="img"][translate="no"] {{
  font-family: 'Material Symbols Rounded' !important; font-weight: 400; font-style: normal; line-height: 1; letter-spacing: normal;
  text-transform: none; display: inline-block; white-space: nowrap; direction: ltr;
  -webkit-font-feature-settings: 'liga'; font-feature-settings: 'liga'; -webkit-font-smoothing: antialiased;
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
}}
.ms {{ font-family: {ICON_FONT} !important; }}
.ms.fill {{ font-variation-settings: 'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 24; }}

.stApp {{ background: var(--background) !important; color: var(--foreground); }}
#MainMenu, footer, [data-testid="stToolbarActions"], [data-testid="stMainMenu"], [data-testid="stAppDeployButton"], [data-testid="stDecoration"] {{ display:none !important; }}
header[data-testid="stHeader"] {{ background: transparent !important; }}
h1,h2,h3,h4,p,li,label,span,div {{ color: var(--foreground); }}
.stApp [data-testid="stMarkdownContainer"] p {{ font-size: 14px; line-height: 1.6; }}

/* Layout: 90% on desktop and tablet, 100% with 10px gutters on mobile */
.block-container, [data-testid="stMainBlockContainer"] {{
  width: 90% !important; min-width: 90% !important; max-width: 90% !important;
  margin: 0 auto !important; padding: 2rem 0 4rem !important;
}}
}}

/* Sidebar (shadcn sidebar) */
[data-testid="stSidebar"] {{ background: var(--sidebar) !important; border-right: 1px solid var(--border); }}
@media (min-width: 768px) {{
  [data-testid="stSidebar"], [data-testid="stSidebar"][aria-expanded="false"] {{
    position: sticky !important; top: 0; height: 100vh !important; align-self: flex-start;
    min-width:264px !important; max-width:264px !important; width:264px !important;
    transform: none !important; margin-left: 0 !important; visibility: visible !important;
  }}
  [data-testid="stSidebarCollapseButton"], [data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapsedControl"], [data-testid="stSidebarHeader"] {{ display:none !important; }}
}}
[data-testid="stSidebarContent"] {{ height:100%; overflow-y:auto; padding:0; display:flex; flex-direction:column; }}
[data-testid="stSidebarUserContent"] {{ padding: 0 12px 10px !important; flex:1; min-height:0; display:flex; flex-direction:column; }}
[data-testid="stSidebarUserContent"] > div {{ flex:1; display:flex; flex-direction:column; }}
[data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] {{ flex:1; gap:4px; }}
[data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] > * {{ flex-shrink:0; }}
[data-testid="stLayoutWrapper"]:has(> .st-key-sb_footer) {{ margin-top:auto; }}
.st-key-sb_footer {{ padding-top:12px; border-top:1px solid var(--border); gap:6px; }}
.st-key-sb_footer::after {{ content:"Powered by Google Gemini"; display:block; text-align:center; font-size:11px; color:var(--muted-foreground); padding:2px 0 4px; }}

.sb-brand {{ display:flex; align-items:center; gap:11px; padding:10px 12px; border:1px solid var(--border); border-radius:var(--radius); background:var(--card); box-shadow:var(--shadow); }}
[data-testid="stLayoutWrapper"]:has(> .st-key-sb_brand_c) {{ margin:14px 0 14px; }}
[data-testid="stLayoutWrapper"]:has(> [class*="st-key-sb_group"]) {{ margin-top:30px; }}
.st-key-sb_footer [data-testid="stLayoutWrapper"], .st-key-sb_footer [data-testid="stElementContainer"] {{ margin:0; }}
.sb-card-wrap {{ padding:0; margin-bottom:6px; }}
.sb-mark {{ width:34px; height:34px; border-radius:9px; background:var(--primary); display:flex; align-items:center; justify-content:center; flex-shrink:0; }}
.sb-mark .ms {{ color:var(--primary-foreground); font-size:20px; }}
.sb-title {{ font-size:14px; font-weight:800; letter-spacing:-.015em; line-height:1.25; margin:0; }}
.sb-sub {{ font-size:11.5px; color:var(--muted-foreground); margin:1px 0 0; font-weight:500; }}
.sb-label {{ font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.08em; color:var(--muted-foreground); padding:0 12px; }}

[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {{
  position:relative; border-radius:8px; padding:8px 12px; margin-bottom:2px; gap:11px; transition:background .12s;
}}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] p {{ font-size:13.5px; font-weight:600; color:var(--muted-foreground) !important; }}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] span[data-testid="stIconMaterial"] {{ color:var(--muted-foreground); font-size:20px; }}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover {{ background:var(--accent); }}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover p,
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover span[data-testid="stIconMaterial"] {{ color:var(--foreground) !important; }}
/* group labels drawn on the first link of each group */
[data-testid="stSidebar"] a[href=""]::after, [data-testid="stSidebar"] a[href="pipeline"]::after {{
  position:absolute; left:12px; top:-24px; font-size:11px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:var(--muted-foreground);
}}
[data-testid="stSidebar"] a[href=""]::after {{ content:"Analyze"; }}
[data-testid="stSidebar"] a[href="pipeline"]::after {{ content:"Operate"; }}
/* trailing pills */
[data-testid="stSidebar"] a[href="reviews"]::after {{ content:"LIVE"; margin-left:auto; font-size:10px; font-weight:800; letter-spacing:.06em; color:var(--success); background:var(--success-bg); padding:2px 7px; border-radius:99px; }}
{SB_COUNT_CSS}

.sb-card {{ border:1px solid var(--border); border-radius:var(--radius); padding:10px 12px; background:var(--card); }}
.sb-row {{ display:flex; justify-content:space-between; align-items:center; font-size:12.5px; color:var(--muted-foreground); padding:4px 0; font-weight:500; }}
.sb-row b {{ color:var(--foreground); font-weight:700; font-variant-numeric:tabular-nums; }}
.sb-sep {{ height:1px; background:var(--border); margin:6px 0; }}
.sb-foot {{ font-size:11px; color:var(--muted-foreground); text-align:center; padding:2px 0 0; }}
[data-testid="stSidebar"] [data-testid="stToggle"] label {{ width:100%; flex-direction:row-reverse; justify-content:space-between; padding:6px 4px 0; }}
[data-testid="stSidebar"] [data-testid="stToggle"] label p {{ font-size:13px !important; font-weight:600; color:var(--foreground) !important; }}

/* Page header */
.page-head {{ display:flex; align-items:flex-start; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:20px; }}
.stApp h1.page-title {{ font-size:26px; font-weight:800; letter-spacing:-.025em; margin:0; padding:0; line-height:1.2; }}
.page-desc {{ font-size:14px; color:var(--muted-foreground); margin:4px 0 0; }}

/* Card */
.card {{ background:var(--card); border:1px solid var(--border); border-radius:calc(var(--radius) + 2px); padding:22px 24px; box-shadow:var(--shadow); margin-bottom:16px; }}
.card-title {{ display:flex; align-items:center; gap:8px; font-size:15px; font-weight:700; margin:0; letter-spacing:-.01em; }}
.card-title .ms {{ font-size:18px; color:var(--muted-foreground); }}
.card-desc {{ font-size:13px; color:var(--muted-foreground); margin:4px 0 16px; }}
.card-title + .card-body {{ margin-top:14px; }}

/* KPI grid */
.kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(190px, 1fr)); gap:14px; margin-bottom:16px; }}
.kpi {{ background:var(--card); border:1px solid var(--border); border-radius:calc(var(--radius) + 2px); padding:16px 18px; box-shadow:var(--shadow); }}
.kpi-top {{ display:flex; align-items:center; justify-content:space-between; }}
.kpi-label {{ font-size:12.5px; font-weight:600; color:var(--muted-foreground); }}
.kpi-top .ms {{ font-size:18px; color:var(--muted-foreground); }}
.kpi-value {{ font-size:26px; font-weight:800; letter-spacing:-.03em; margin-top:8px; line-height:1.15; }}
.kpi-hint {{ font-size:12px; color:var(--muted-foreground); margin-top:4px; }}

/* Badge */
.badge {{ display:inline-flex; align-items:center; gap:4px; font-size:12px; font-weight:600; padding:2px 9px; border-radius:6px; border:1px solid transparent; white-space:nowrap; }}
.badge .ms {{ font-size:14px; }}
.badge.default {{ background:var(--primary); color:var(--primary-foreground); }} .badge.default .ms {{ color:var(--primary-foreground); }}
.badge.secondary {{ background:var(--secondary); color:var(--foreground); }}
.badge.outline {{ border-color:var(--border); color:var(--foreground); }}
.badge.success {{ background:var(--success-bg); color:var(--success); }} .badge.success .ms {{ color:var(--success); }}
.badge.warning {{ background:var(--warning-bg); color:var(--warning); }} .badge.warning .ms {{ color:var(--warning); }}
.badge.destructive {{ background:var(--destructive-bg); color:var(--destructive); }} .badge.destructive .ms {{ color:var(--destructive); }}

/* Theme rows + progress */
.theme-row {{ padding:16px 0; border-top:1px solid var(--border); }}
.theme-row:first-child {{ border-top:none; padding-top:2px; }}
.theme-head {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
.theme-dot {{ width:10px; height:10px; border-radius:3px; flex-shrink:0; }}
.theme-name {{ font-size:14.5px; font-weight:700; }}
.theme-meta {{ margin-left:auto; font-size:12.5px; color:var(--muted-foreground); font-weight:600; }}
.theme-desc {{ font-size:13px; color:var(--muted-foreground); margin:6px 0 0; line-height:1.55; }}
.progress {{ height:6px; background:var(--muted); border-radius:99px; margin-top:10px; overflow:hidden; }}
.progress > span {{ display:block; height:100%; border-radius:99px; }}
.quote {{ margin:10px 0 0; padding:10px 14px; border-left:2px solid var(--border); font-size:13px; line-height:1.6; background:var(--muted); border-radius:0 8px 8px 0; }}

/* Theme + action grids */
.tgrid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(250px, 1fr)); gap:14px; }}
.tcard {{ border:1px solid var(--border); border-radius:var(--radius); padding:16px; background:var(--background); }}
.tcard-top {{ display:flex; align-items:center; gap:8px; }}
.tcard-stats {{ display:flex; align-items:flex-end; gap:18px; margin:12px 0 2px; }}
.tcard-stats > div {{ display:flex; flex-direction:column; }}
.tcard-n {{ font-size:22px; font-weight:800; letter-spacing:-.02em; line-height:1.1; }}
.tcard-l {{ font-size:11.5px; color:var(--muted-foreground); font-weight:600; }}
.tcard-stats .badge {{ margin-left:auto; }}
.agrid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:14px; }}
.agrid-item {{ border:1px solid var(--border); border-radius:var(--radius); padding:16px; background:var(--background); }}
.agrid-item .action-n {{ margin-bottom:10px; }}
/* Actions */
.action {{ display:flex; gap:14px; padding:14px 0; border-top:1px solid var(--border); }}
.action:first-child {{ border-top:none; padding-top:0; }}
.action-n {{ width:28px; height:28px; border-radius:8px; background:var(--muted); font-weight:800; font-size:13px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }}
.action-title {{ font-size:14px; font-weight:700; margin:0 0 3px; }}
.action-body {{ font-size:13px; color:var(--muted-foreground); line-height:1.55; margin:0; }}

/* Stepper */
.step {{ display:flex; align-items:center; gap:12px; padding:11px 0; border-top:1px solid var(--border); font-size:13.5px; font-weight:600; }}
.step:first-child {{ border-top:none; }}
.step .ms {{ font-size:22px; }}
.step.pending {{ color:var(--muted-foreground); }} .step.pending .ms {{ color:var(--border); }}
.step.running .ms {{ color:var(--primary); animation: spin 1.1s linear infinite; }}
.step.done .ms {{ color:var(--success); }}
.step.failed {{ color:var(--destructive); }} .step.failed .ms {{ color:var(--destructive); }}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}

/* Table (shadcn table) */
.tbl-wrap {{ overflow-x:auto; }}
.tbl {{ width:100%; border-collapse:collapse; font-size:13px; }}
.tbl th {{ text-align:left; font-size:12px; font-weight:600; color:var(--muted-foreground); padding:0 12px 10px; border:none; border-bottom:1px solid var(--border); white-space:nowrap; }}
.tbl td {{ padding:12px; border:none; border-bottom:1px solid var(--border); font-weight:500; white-space:nowrap; }}
.tbl tr:last-child td {{ border-bottom:none; }}
.tbl td.num, .tbl th.num {{ text-align:right; font-variant-numeric:tabular-nums; }}

/* Live feed */
.live-dot {{ width:8px; height:8px; border-radius:50%; background:var(--success); display:inline-block; margin-right:6px; animation:pulse 1.6s ease-in-out infinite; }}
.live-dot.off {{ background:var(--muted-foreground); animation:none; }}
@keyframes pulse {{ 0%,100% {{ opacity:1; box-shadow:0 0 0 0 rgba(34,197,94,.45); }} 50% {{ opacity:.7; box-shadow:0 0 0 6px rgba(34,197,94,0); }} }}
.rv {{ padding:14px 0; border-top:1px solid var(--border); }}
.rv:first-child {{ border-top:none; padding-top:0; }}
.rv-head {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; font-size:12.5px; color:var(--muted-foreground); font-weight:600; }}
.stars {{ display:inline-flex; }} .stars .ms {{ font-size:16px; color:var(--warning); }} .stars .ms.off {{ color:var(--border); }}
.rv-text {{ font-size:13.5px; line-height:1.6; margin:6px 0 0; }}
.rv-meta {{ margin-left:auto; }}

/* Alert (shadcn alert) */
.notice {{ display:flex; align-items:flex-start; gap:12px; padding:12px 16px; border-radius:var(--radius); border:1px solid var(--border); font-size:13.5px; font-weight:500; margin:0 0 14px; background:var(--card); }}
.notice .ms {{ font-size:20px; margin-top:1px; }}
.notice.ok {{ border-color:var(--success); }} .notice.ok .ms {{ color:var(--success); }}
.notice.bad {{ border-color:var(--destructive); }} .notice.bad .ms {{ color:var(--destructive); }}
.notice.warn {{ border-color:var(--warning); }} .notice.warn .ms {{ color:var(--warning); }}
.notice.info .ms {{ color:var(--muted-foreground); }}
.empty {{ text-align:center; padding:44px 20px; color:var(--muted-foreground); }}
.empty .ms {{ font-size:36px; color:var(--border); display:block; margin-bottom:8px; }}
.empty b {{ color:var(--foreground); font-size:15px; display:block; margin-bottom:4px; }}

/* Streamlit widgets in shadcn style */
.stButton > button, .stDownloadButton > button {{
  border-radius:8px; font-weight:600; font-size:13.5px; height:40px; padding:0 16px;
  border:1px solid var(--border); background:var(--card); color:var(--foreground); box-shadow:var(--shadow); transition:background .12s;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{ background:var(--accent); border-color:var(--border); color:var(--foreground); }}
.stButton > button[kind="primary"] {{ background:var(--primary); border-color:var(--primary); color:var(--primary-foreground); }}
.stButton > button[kind="primary"] p, .stButton > button[kind="primary"] span {{ color:var(--primary-foreground) !important; }}
.stButton > button[kind="primary"]:hover {{ opacity:.9; background:var(--primary); }}
.stButton > button:disabled {{ opacity:.5; }}

[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="select"] > div, textarea {{
  background:var(--background) !important; border-color:var(--border) !important; border-radius:8px !important; color:var(--foreground) !important;
}}
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within {{ box-shadow:0 0 0 3px var(--ring) !important; }}
[data-baseweb="input"] input, [data-baseweb="select"] div {{ color:var(--foreground) !important; }}
[data-baseweb="popover"] *, [data-baseweb="menu"] {{ background:var(--card); color:var(--foreground); }}
[data-testid="stWidgetLabel"] p, label p {{ font-size:13px !important; font-weight:600; color:var(--foreground) !important; }}
[data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"], .react-aria-ComboBox [role="group"], [data-testid="stSelectbox"] [role="group"] {{
  background:var(--background) !important; border:1px solid var(--border) !important; border-radius:8px !important;
}}
[data-testid="stTextInputRootElement"] input, .react-aria-ComboBox input, [data-testid="stNumberInputContainer"] input {{ color:var(--foreground) !important; background:transparent !important; }}
.react-aria-ComboBox button svg, [data-testid="stSelectbox"] svg {{ color:var(--muted-foreground); fill:currentColor; }}
.react-aria-Popover, [role="listbox"], [role="listbox"] [role="option"] {{ background:var(--card) !important; color:var(--foreground) !important; }}
[role="listbox"] [role="option"]:hover, [role="listbox"] [role="option"][data-focused="true"] {{ background:var(--accent) !important; }}
[data-testid="stFileUploaderDropzone"] {{ background:var(--muted); border:1.5px dashed var(--border); border-radius:var(--radius); }}
[data-testid="stFileUploaderDropzone"] * {{ color:var(--muted-foreground) !important; }}
[data-testid="stFileUploaderDropzone"] button {{ color:var(--foreground) !important; }}

/* Tabs as shadcn TabsList */
[data-testid="stTabs"] [role="tablist"] {{ display:inline-flex; gap:2px; padding:4px; background:var(--muted); border-radius:var(--radius); border:none; max-width:100%; overflow-x:auto; }}
[data-testid="stTab"] {{ height:34px; padding:0 14px; border-radius:7px; background:transparent; color:var(--muted-foreground); }}
[data-testid="stTab"] p {{ color:inherit !important; font-weight:600; font-size:13.5px; }}
[data-testid="stTab"] span[role="img"] {{ font-size:18px; vertical-align:-4px; margin-right:2px; }}
[data-testid="stTab"][aria-selected="true"] {{ background:var(--background); color:var(--foreground); box-shadow:0 1px 2px rgba(0,0,0,.08); }}
.react-aria-SelectionIndicator {{ display:none !important; }}
[data-testid="stTabs"] [role="tabpanel"] {{ padding-top:16px; }}

div[data-testid="stVerticalBlockBorderWrapper"] {{ border-color:var(--border); border-radius:calc(var(--radius) + 2px); background:var(--card); }}
[data-testid="stExpander"] {{ background:var(--card); border:1px solid var(--border) !important; border-radius:var(--radius); }}
[data-testid="stExpander"] summary p {{ font-weight:700; }}
[data-testid="stSegmentedControl"] button {{ font-weight:600; }}
[data-testid="stMarkdownContainer"] code {{ background:var(--muted); color:var(--foreground); }}
.st-key-pulse_doc h1, .st-key-archived_doc h1 {{ font-size:20px; font-weight:800; letter-spacing:-.02em; }}
.st-key-pulse_doc h2, .st-key-archived_doc h2 {{ font-size:12.5px; font-weight:700; margin-top:1.4rem; text-transform:uppercase; letter-spacing:.07em; color:var(--muted-foreground); }}
.st-key-pulse_doc blockquote, .st-key-archived_doc blockquote {{ border-left:2px solid var(--border); background:var(--muted); padding:8px 14px; border-radius:0 8px 8px 0; }}
@font-face {{ font-family:'MSR Solid'; font-style:normal; font-weight:400; font-display:block;
  src:url(https://fonts.gstatic.com/s/materialsymbolsrounded/v381/syl0-zNym6YjUruM-QrEh7-nyTnjDwKNJ_190FjpZIvDmUSVOK7BDJ_vb9vUSzq3wzLK-P0J-V_Zs-QtQth3-jOcbTCVpeRL2w5rwZu2rIelXxI.ttf) format('truetype'); }}
.ms.fill {{ font-family:'MSR Solid', 'Material Symbols Rounded' !important; }}
@media (max-width: 767px) {{
  .block-container, [data-testid="stMainBlockContainer"] {{
    width: 100% !important; min-width: 100% !important; max-width: 100% !important;
    margin: 0 !important; padding: 1rem 10px 3rem !important;
  }}
  .card {{ padding: 16px; }}
  [data-testid="stHorizontalBlock"] {{ gap: 0.75rem !important; }}
  .page-head {{ flex-direction: column; gap: 8px; margin-bottom: 14px; }}
  .stApp h1.page-title {{ font-size: 22px; }}
  .kpi-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
  .kpi {{ padding: 12px; }}
  .kpi-label {{ font-size: 12px; }}
  .kpi-value {{ font-size: 22px; margin-top: 6px; }}
  .kpi-hint {{ font-size: 11px; }}
  .tbl th, .tbl td {{ padding: 10px 8px; font-size: 12.5px; }}
  .tbl .hm {{ display: none; }}
  .tgrid, .agrid {{ grid-template-columns: 1fr; }}
  .tcard-stats {{ gap: 14px; }}
  .rv-meta, .theme-meta {{ margin-left: 0; width: 100%; }}
  [data-testid="stTabs"] [role="tablist"] {{ width: 100%; }}
  [data-testid="stTab"] {{ padding: 0 10px; flex: 1 0 auto; }}
  .stButton > button, .stDownloadButton > button {{ width: 100%; }}
}}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍]+",
    flags=re.UNICODE,
)


def clean_text(s: str) -> str:
    return EMOJI_RE.sub("", s or "").strip()


def esc(s) -> str:
    return html.escape(clean_text(str(s)))


def icon(name: str, fill: bool = False) -> str:
    return f'<span class="ms{" fill" if fill else ""}">{name}</span>'


def render(markup: str):
    # Collapse whitespace between tags so Markdown never treats indentation as a code block
    st.markdown(re.sub(r">\s*\n\s*<", "><", markup.strip()), unsafe_allow_html=True)


def card(title: str, icon_name: str, body: str, desc: str = "") -> str:
    d = f'<p class="card-desc">{desc}</p>' if desc else ""
    return f'<div class="card"><p class="card-title">{icon(icon_name)}{title}</p>{d}<div class="card-body">{body}</div></div>'


def badge(text: str, kind: str = "secondary", icon_name: str = "") -> str:
    return f'<span class="badge {kind}">{icon(icon_name) if icon_name else ""}{esc(text)}</span>'


def notice(kind: str, text: str):
    glyph = {"ok": "check_circle", "bad": "error", "warn": "warning", "info": "info"}[kind]
    render(f'<div class="notice {kind}">{icon(glyph, fill=True)}<span>{esc(text)}</span></div>')


def soft_breaks(md: str) -> str:
    """Render single newlines as line breaks so label lines stay on separate rows."""
    return re.sub(r"(?<!\n)\n(?!\n)", "  \n", md)


def page_header(title: str, desc: str, right: str = ""):
    render(f'<div class="page-head"><div><h1 class="page-title">{title}</h1><p class="page-desc">{desc}</p></div><div>{right}</div></div>')
    if st.session_state.get("flash"):
        notice("ok", st.session_state.pop("flash"))


def kpi_grid(items):
    cells = "".join(
        f'<div class="kpi"><div class="kpi-top"><span class="kpi-label">{label}</span>{icon(ic)}</div>'
        f'<div class="kpi-value">{esc(value)}</div><div class="kpi-hint">{esc(hint)}</div></div>'
        for ic, label, value, hint in items
    )
    render(f'<div class="kpi-grid">{cells}</div>')


def table(headers, rows, num_cols=(), hide_mobile=()):
    """headers: list[str]; rows: list[list[str-html]]; num_cols: right-aligned indexes; hide_mobile: indexes hidden on phones."""
    def cls(i):
        return ("num " if i in num_cols else "") + ("hm" if i in hide_mobile else "")
    th = "".join(f'<th class="{cls(i)}">{h}</th>' for i, h in enumerate(headers))
    tr = "".join("<tr>" + "".join(f'<td class="{cls(i)}">{c}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f'<div class="tbl-wrap"><table class="tbl"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def read_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    return None


def read_text(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None


def fmt_dt(iso) -> str:
    try:
        return datetime.datetime.fromisoformat(iso).strftime("%d %b, %H:%M")
    except (TypeError, ValueError):
        return "-"


def sentiment(avg: float):
    if avg < 2.5:
        return "Negative", "destructive", "trending_down"
    if avg < 3.5:
        return "Mixed", "warning", "trending_flat"
    return "Positive", "success", "trending_up"


def chart_layout(fig, height=300):
    fig.update_layout(
        height=height, margin=dict(t=10, b=10, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Manrope, sans-serif", size=12, color=T["foreground"]),
        hoverlabel=dict(font_family="Manrope, sans-serif", bgcolor=T["card"], font_color=T["foreground"], bordercolor=T["border"]),
    )
    return fig


def load_state() -> dict:
    cleaned = read_json(orch.REVIEWS_CLEANED_PATH)
    theme_map = read_json(orch.THEME_MAP_PATH)
    insights = read_json(orch.INSIGHTS_PATH)
    runs = orch.list_runs()
    reviews = (cleaned or {}).get("reviews", [])
    ratings = [r["rating"] for r in reviews if isinstance(r.get("rating"), (int, float))]
    return dict(
        themes=(theme_map or {}).get("themes", []),
        quotes={t["theme_id"]: t.get("quotes", []) for t in (insights or {}).get("themes", [])},
        actions=(insights or {}).get("action_ideas", []),
        reviews=reviews,
        ratings=ratings,
        avg_rating=sum(ratings) / len(ratings) if ratings else 0.0,
        pulse_md=read_text(orch.PULSE_MD_PATH),
        pulse_txt=read_text(orch.PULSE_TXT_PATH),
        runs=runs,
        last_run=next((r for r in runs if r.get("status") == "completed"), None),
        calls=usage_svc.load_calls(),
        gemini_ready=bool(get_config("GEMINI_API_KEY")),
    )


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
def page_overview():
    S = STATE
    last = S["last_run"]
    page_header("Overview", "Customer feedback themes from Google Play reviews of the Groww Mutual Fund app.",
                badge(f"Last run {fmt_dt(last['finished_at'])}", "outline", "schedule") if last else badge("No runs yet", "outline"))
    kpi_grid([
        ("rate_review", "Reviews analysed", f"{len(S['reviews']):,}", "After cleaning and PII scrubbing"),
        ("category", "Themes", str(len(S["themes"])), "Discovered by Gemini"),
        ("star", "Average rating", f"{S['avg_rating']:.2f}" if S["ratings"] else "-", "Out of 5"),
        ("warning", "Negative reviews",
         f"{sum(1 for r in S['ratings'] if r <= 2) / len(S['ratings']) * 100:.0f}%" if S["ratings"] else "-", "Rated 1 or 2 stars"),
    ])

    themes = S["themes"]
    if not themes:
        render(card("Overview", "insights", f'<div class="empty">{icon("inbox")}<b>No analysis yet</b>Open Pipeline in the sidebar and run your first analysis.</div>'))
        return

    total = sum(t.get("review_count", 0) for t in themes) or 1
    labels = [t.get("label") for t in themes]
    colors = [T["chart"][i % len(T["chart"])] for i in range(len(themes))]

    def wrap(label, width=24):
        return "<br>".join(textwrap.wrap(str(label), width)) or str(label)

    wlabels = [wrap(l) for l in labels]

    def theme_ratings(t):
        return [r["rating"] for r in t.get("reviews", []) if isinstance(r.get("rating"), (int, float))]

    def chart_card(title, icon_name, fig, height, sub=""):
        with st.container(border=True):
            render(f'<p class="card-title">{icon(icon_name)}{title}</p>' + (f'<p class="card-desc">{sub}</p>' if sub else ""))
            chart_layout(fig, height)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    axis = dict(showgrid=True, gridcolor=T["border"], zeroline=False, tickfont=dict(color=T["muted_fg"]))
    noaxis = dict(showgrid=False, zeroline=False, tickfont=dict(color=T["muted_fg"]))

    # Row 1: theme share and sentiment mix
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        fig = go.Figure(go.Pie(labels=labels, values=[t.get("review_count", 0) for t in themes], hole=0.66, sort=False,
                               marker=dict(colors=colors, line=dict(color=T["card"], width=3)), textinfo="percent",
                               textfont=dict(color="#FFFFFF", size=11, family="Manrope, sans-serif"),
                               hovertemplate="%{label}<br>%{value} reviews (%{percent})<extra></extra>"))
        fig.add_annotation(text=f"<b>{total}</b><br><span style='font-size:11px'>reviews</span>", showarrow=False,
                           font=dict(size=24, color=T["foreground"], family="Manrope, sans-serif"))
        fig.update_layout(showlegend=True, legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.05, font=dict(size=11, color=T["foreground"])))
        chart_card("Theme distribution", "donut_large", fig, 380, "Share of classified reviews by theme.")
    with c2:
        neg, neu, pos = [], [], []
        for t in themes:
            r = theme_ratings(t) or [0]
            n = len(r)
            neg.append(sum(1 for x in r if x <= 2) / n * 100)
            neu.append(sum(1 for x in r if x == 3) / n * 100)
            pos.append(sum(1 for x in r if x >= 4) / n * 100)
        fig = go.Figure()
        for name, vals, col in (("Negative (1-2)", neg, T["destructive"]), ("Neutral (3)", neu, T["warning"]), ("Positive (4-5)", pos, T["success"])):
            fig.add_trace(go.Bar(y=wlabels, x=vals, name=name, orientation="h", marker=dict(color=col),
                                 hovertemplate="%{y}<br>" + name + ": %{x:.0f}%<extra></extra>"))
        fig.update_layout(barmode="stack", legend=dict(orientation="h", y=-0.15, font=dict(size=11, color=T["foreground"])))
        fig.update_xaxes(range=[0, 100], ticksuffix="%", **axis)
        fig.update_yaxes(autorange="reversed", **noaxis)
        chart_card("Sentiment mix by theme", "sentiment_satisfied", fig, 380, "Share of negative, neutral and positive ratings inside each theme.")

    # Row 2: average rating by theme and volume over time
    c3, c4 = st.columns(2, gap="medium")
    with c3:
        avgs = [sum(theme_ratings(t)) / len(theme_ratings(t)) if theme_ratings(t) else 0 for t in themes]
        bar_cols = [T["destructive"] if a < 2.5 else T["warning"] if a < 3.5 else T["success"] for a in avgs]
        fig = go.Figure(go.Bar(y=wlabels, x=avgs, orientation="h", marker=dict(color=bar_cols, cornerradius=5),
                               text=[f"{a:.2f}" for a in avgs], textposition="outside", textfont=dict(color=T["foreground"], size=12),
                               hovertemplate="%{y}: %{x:.2f}<extra></extra>"))
        fig.update_xaxes(range=[0, 5.5], **axis)
        fig.update_yaxes(autorange="reversed", **noaxis)
        chart_card("Average rating by theme", "star", fig, 340, "Lower is worse. Red is below 2.5, amber below 3.5.")
    with c4:
        df = pd.DataFrame([{"d": r.get("review_date"), "rating": r.get("rating")} for r in S["reviews"] if r.get("review_date")])
        if not df.empty:
            df["d"] = pd.to_datetime(df["d"], errors="coerce")
            df = df.dropna(subset=["d"])
        if df.empty:
            chart_card("Review volume over time", "show_chart", go.Figure(), 260)
        else:
            freq = "D" if df["d"].dt.date.nunique() > 1 else "h"
            g = df.set_index("d").resample(freq)["rating"].agg(["count", "mean"]).reset_index()
            g = g[g["count"] > 0]
            fig = go.Figure()
            fig.add_trace(go.Bar(x=g["d"], y=g["count"], name="Reviews", marker=dict(color=T["chart"][0], cornerradius=4),
                                 hovertemplate="%{x|%d %b %H:%M}<br>%{y} reviews<extra></extra>"))
            fig.add_trace(go.Scatter(x=g["d"], y=g["mean"], name="Avg rating", yaxis="y2", mode="lines+markers",
                                     line=dict(color=T["warning"], width=2.5), marker=dict(size=6),
                                     hovertemplate="%{x|%d %b %H:%M}<br>%{y:.2f} avg<extra></extra>"))
            fig.update_layout(yaxis2=dict(overlaying="y", side="right", range=[0, 5], dtick=1, showgrid=False, tickfont=dict(color=T["muted_fg"])),
                              legend=dict(orientation="h", y=-0.2, font=dict(size=11, color=T["foreground"])))
            fig.update_yaxes(**axis)
            fig.update_xaxes(tickformat="%d %b" if freq == "D" else "%H:%M", dtick=86400000 if freq == "D" else None, **noaxis)
            chart_card("Review volume over time", "show_chart", fig, 260, "Reviews per " + ("day" if freq == "D" else "hour") + " with average rating.")

    # Row 3: rating distribution and negative share
    c5, c6 = st.columns([2, 1], gap="medium")
    with c5:
        if S["ratings"]:
            dist = pd.Series(S["ratings"]).value_counts().reindex([1, 2, 3, 4, 5], fill_value=0)
            fig = go.Figure(go.Bar(x=[f"{i} star" for i in dist.index], y=dist.values,
                                   marker=dict(color=[T["destructive"], T["destructive"], T["warning"], T["success"], T["success"]], cornerradius=6),
                                   hovertemplate="%{x}: %{y} reviews<extra></extra>"))
            fig.update_yaxes(**axis)
            fig.update_xaxes(**noaxis)
            chart_card("Rating distribution", "bar_chart", fig, 230)
    with c6:
        neg_share = sum(1 for r in S["ratings"] if r <= 2) / len(S["ratings"]) * 100 if S["ratings"] else 0
        fig = go.Figure(go.Indicator(mode="gauge+number", value=neg_share,
                                     number=dict(suffix="%", font=dict(size=34, family="Manrope, sans-serif", color=T["foreground"])),
                                     gauge=dict(axis=dict(range=[0, 100], tickvals=[0, 50, 100], ticksuffix="%", tickfont=dict(color=T["muted_fg"], size=10)),
                                                bar=dict(color=T["destructive"], thickness=0.3), bgcolor=T["muted"], borderwidth=0)))
        chart_card("Negative review share", "warning", fig, 230, "Ratings of 1 or 2 stars.")

    # Theme breakdown grid
    cards = []
    for i, t in enumerate(themes):
        cnt = t.get("review_count", 0)
        pct = cnt / total * 100
        r = theme_ratings(t)
        s_label, s_kind, s_icon = sentiment(sum(r) / len(r)) if r else ("No ratings", "secondary", "remove")
        q = (S["quotes"].get(t["theme_id"], [""]) or [""])[0]
        q = (q[:150].rstrip() + "...") if len(q) > 150 else q
        cards.append(
            f'<div class="tcard"><div class="tcard-top"><span class="theme-dot" style="background:{colors[i]}"></span>'
            f'<span class="theme-name">{esc(t.get("label"))}</span></div>'
            f'<div class="tcard-stats"><div><span class="tcard-n">{cnt}</span><span class="tcard-l">mentions</span></div>'
            f'<div><span class="tcard-n">{pct:.0f}%</span><span class="tcard-l">of reviews</span></div>{badge(s_label, s_kind, s_icon)}</div>'
            f'<div class="progress"><span style="width:{pct:.1f}%;background:{colors[i]}"></span></div>'
            f'<p class="theme-desc">{esc(t.get("description", ""))}</p>'
            + (f'<div class="quote">&ldquo;{esc(q)}&rdquo;</div>' if q else "") + '</div>')
    render(card("Theme breakdown", "category", f'<div class="tgrid">{"".join(cards)}</div>', "Each theme with its volume, sentiment and a representative quote."))

    if S["actions"]:
        items = "".join(
            f'<div class="agrid-item"><div class="action-n">{i}</div><p class="action-title">{esc(a.get("title"))}</p>'
            f'<p class="action-body">{esc(a.get("rationale"))}</p></div>' for i, a in enumerate(S["actions"], 1))
        render(card("Product action ideas", "lightbulb", f'<div class="agrid">{items}</div>', "Three prioritised recommendations derived from the themes above."))


def stepper_html(states: dict) -> str:
    glyph = {"pending": "radio_button_unchecked", "running": "progress_activity", "done": "check_circle", "failed": "error"}
    return "".join(
        f'<div class="step {states.get(key, "pending")}">{icon(glyph[states.get(key, "pending")], fill=states.get(key) == "done")}<span>{label}</span></div>'
        for key, label in orch.STEPS)


def page_pipeline():
    S = STATE
    page_header("Pipeline", "Collect reviews, analyse them with Gemini and generate the weekly pulse.")
    left, right = st.columns([3, 2], gap="medium")

    with left:
        with st.container(border=True):
            render(f'<p class="card-title">{icon("cloud_download")}Review ingestion</p>'
                   '<p class="card-desc">Fetch public Google Play reviews automatically, or upload a CSV as a fallback.</p>')
            source = st.segmented_control("Source", ["Play Store", "CSV upload"], default="Play Store",
                                          selection_mode="single", key="source", label_visibility="collapsed") or "Play Store"
            csv_file, count = None, 300
            if source == "Play Store":
                c1, c2 = st.columns(2)
                with c1:
                    window = st.selectbox("Review window", ["Last 4 weeks", "Last 8 weeks", "Last 12 weeks"], index=1)
                with c2:
                    count = st.slider("Reviews to fetch", 100, 1000, 500, 50)
            else:
                window = st.selectbox("Review window", ["Last 4 weeks", "Last 8 weeks", "Last 12 weeks", "No date filter"], index=3)
                csv_file = st.file_uploader("Reviews CSV", type=["csv"], help="Columns: rating, review_text (required); reviewId, review_date (optional).")
            weeks = None if window == "No date filter" else int(re.search(r"\d+", window).group())
            can_run = S["gemini_ready"] and (source == "Play Store" or csv_file is not None)
            run_clicked = st.button("Run analysis", type="primary", icon=":material/play_arrow:", disabled=not can_run, width="stretch")
            if not S["gemini_ready"]:
                st.caption("Set GEMINI_API_KEY in .env or Streamlit secrets to enable analysis.")

    with right:
        step_slot = st.empty()
        states = st.session_state.get("last_states", {})
        step_slot.markdown(card("Pipeline status", "account_tree", stepper_html(states),
                                "Phases 1 to 5. Email delivery is in the Report page."), unsafe_allow_html=True)

    if run_clicked:
        states = {}

        def on_progress(i, key, state):
            states[key] = state
            st.session_state["last_states"] = dict(states)
            step_slot.markdown(card("Pipeline status", "account_tree", stepper_html(states),
                                    "Running. This usually takes under a minute."), unsafe_allow_html=True)

        try:
            rec = orch.run_pipeline(source="csv" if source == "CSV upload" else "scrape", count=count, weeks=weeks,
                                    csv_bytes=csv_file.getvalue() if csv_file else None, progress=on_progress)
            st.session_state["flash"] = (f"Analysis complete: {rec['review_count']} reviews and {rec['theme_count']} themes. See Run history for usage and cost.")
            st.rerun()
        except Exception as e:  # noqa: BLE001
            notice("bad", f"Run failed: {e}")


@st.cache_data(ttl=20, show_spinner=False)
def fetch_live(count: int):
    from phase1_review_collection.services.collector import fetch_latest
    return fetch_latest(orch.PACKAGE_ID, count)


def time_ago(iso: str) -> str:
    try:
        secs = (datetime.datetime.now() - datetime.datetime.fromisoformat(iso[:19])).total_seconds()
    except (TypeError, ValueError):
        return ""
    if secs < 60:
        return "just now"
    for unit, n in (("day", 86400), ("hour", 3600), ("min", 60)):
        if secs >= n:
            v = int(secs // n)
            return f"{v} {unit}{'s' if v > 1 and unit != 'min' else ''} ago"
    return ""


def live_feed():
    c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1], vertical_alignment="bottom")
    auto = c1.toggle("Auto-refresh every 30 seconds", value=False, key="live_auto")
    count = c2.selectbox("Reviews", [25, 50, 100], index=1, key="live_count")
    min_rating = c3.selectbox("Rating", ["All", 1, 2, 3, 4, 5], key="live_rating")
    if c4.button("Refresh now", icon=":material/refresh:", width="stretch"):
        fetch_live.clear()

    @st.fragment(run_every="30s" if auto else None)
    def feed():
        try:
            data = fetch_live(count)
        except Exception as e:  # noqa: BLE001
            notice("bad", f"Could not reach Google Play: {e}")
            return
        seen = st.session_state.get("live_seen")
        ids = [r["reviewId"] for r in data]
        fresh = set() if seen is None else set(ids) - seen
        st.session_state["live_new"] = (st.session_state.get("live_new", set()) | fresh) if seen is not None else set()
        st.session_state["live_seen"] = set(ids) | (seen or set())
        new = st.session_state["live_new"]

        view = [r for r in data if min_rating == "All" or r["rating"] == min_rating]
        avg = sum(r["rating"] for r in data) / len(data) if data else 0
        low = sum(1 for r in data if r["rating"] <= 2)
        now = datetime.datetime.now().strftime("%H:%M:%S")
        status = f'<span class="live-dot{"" if auto else " off"}"></span>{"Live" if auto else "Paused"}'
        rows = "".join(
            f'<div class="rv"><div class="rv-head"><span class="stars">'
            + "".join(icon("star", fill=True).replace('class="ms fill"', f'class="ms fill{"" if i < r["rating"] else " off"}"') for i in range(5))
            + f'</span>{badge("New", "success") if r["reviewId"] in new else ""}'
            f'<span class="rv-meta">{time_ago(r["review_date"])} &middot; {esc(r["review_date"][:16])}</span></div>'
            f'<p class="rv-text">{esc(scrub_pii(r["review_text"] or ""))}</p></div>'
            for r in view
        ) or f'<div class="empty">{icon("search_off")}<b>No reviews match</b>Try a different rating filter.</div>'
        render(card(f"Latest Google Play reviews {badge(f'{len(new)} new this session', 'secondary') if new else ''}", "sensors", rows,
                    f'{status} &middot; updated {now} &middot; newest {len(data)} reviews, average {avg:.2f}, {low} rated 2 stars or below. Fetched directly from Google Play and not stored.'))

    feed()


def reviews_dataset():
    S = STATE
    raw = read_json(orch.RAW_REVIEWS_PATH) or []
    if not raw:
        render(card("Collected reviews", "rate_review", f'<div class="empty">{icon("inbox")}<b>No reviews collected</b>Run the pipeline from the Pipeline page to fetch reviews.</div>'))
        return

    theme_of = {r["reviewId"]: t.get("label") for t in S["themes"] for r in t.get("reviews", [])}
    kept = {r["reviewId"] for r in S["reviews"]}
    df = pd.DataFrame([{
        "Date": (r.get("review_date") or "")[:10],
        "Rating": r.get("rating"),
        "Review": scrub_pii(clean_text(r.get("review_text") or "")),
        "Theme": theme_of.get(r.get("reviewId"), "-"),
        "Status": "Included" if r.get("reviewId") in kept else "Filtered out",
    } for r in raw])

    kpi_grid([
        ("inbox", "Collected", f"{len(df):,}", "Raw reviews from the last fetch"),
        ("check_circle", "Included", f"{(df['Status'] == 'Included').sum():,}", "Used for theme analysis"),
        ("filter_alt", "Filtered out", f"{(df['Status'] == 'Filtered out').sum():,}", "Low-signal, duplicate or outside window"),
    ])

    f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
    query = f1.text_input("Search", placeholder="Search review text")
    status = f2.selectbox("Status", ["All", "Included", "Filtered out"])
    rating = f3.selectbox("Rating", ["All", 1, 2, 3, 4, 5])
    theme = f4.selectbox("Theme", ["All"] + sorted({t for t in df["Theme"] if t != "-"}))

    view = df
    if query:
        view = view[view["Review"].str.contains(query, case=False, na=False, regex=False)]
    if status != "All":
        view = view[view["Status"] == status]
    if rating != "All":
        view = view[view["Rating"] == rating]
    if theme != "All":
        view = view[view["Theme"] == theme]

    st.caption(f"Showing {len(view):,} of {len(df):,} reviews. Personal details are masked.")
    st.dataframe(view, width="stretch", hide_index=True, height=560, column_config={
        "Review": st.column_config.TextColumn(width="large"),
        "Rating": st.column_config.NumberColumn(width="small", format="%d"),
    })
    st.download_button("Download CSV", view.to_csv(index=False), "reviews.csv", mime="text/csv", icon=":material/download:")


def page_reviews():
    page_header("Reviews", "Live Google Play reviews, and the dataset used in the latest analysis.")
    t_live, t_data = st.tabs([":material/sensors: Live feed", ":material/database: Analysis dataset"])
    with t_live:
        live_feed()
    with t_data:
        reviews_dataset()


def page_report():
    S = STATE
    page_header("Report", "The weekly pulse, its email draft and the classified reviews behind it.")
    if not S["pulse_md"]:
        render(card("Weekly pulse", "description", f'<div class="empty">{icon("description")}<b>No report generated</b>Run the pipeline to produce this week\'s pulse.</div>'))
        return

    t_pulse, t_email, t_data = st.tabs([":material/article: Weekly pulse", ":material/mail: Email", ":material/table_chart: Classified reviews"])

    with t_pulse:
        words = len(S["pulse_md"].split())
        with st.container(border=True, key="pulse_doc"):
            render(f'<p class="card-title">{icon("article")}Weekly pulse {badge(f"{words} words", "secondary")}</p>')
            st.markdown(soft_breaks(clean_text(S["pulse_md"])))
            d1, d2, _ = st.columns([1, 1, 3])
            d1.download_button("Markdown", S["pulse_md"], "weekly_pulse.md", icon=":material/download:", width="stretch")
            d2.download_button("Plain text", S["pulse_txt"] or S["pulse_md"], "weekly_pulse.txt", icon=":material/download:", width="stretch")

    with t_email:
        recipient = st.text_input("Recipient", value=get_config("EMAIL_TO") or "", placeholder="name@company.com")
        b1, b2, _ = st.columns([1, 1, 3])
        gen = b1.button("Generate draft", icon=":material/edit_note:", width="stretch")
        send = b2.button("Send email", type="primary", icon=":material/send:", width="stretch")
        if gen or send:
            if send and not recipient:
                notice("warn", "Enter a recipient to send.")
            else:
                try:
                    with st.spinner("Drafting with Gemini..."):
                        EmailSender(orch.PULSE_MD_PATH, orch.EMAIL_MD_PATH, orch.EMAIL_TXT_PATH).process(send_mode=send, recipient=recipient or None)
                    if S["last_run"]:
                        orch.archive_email(S["last_run"]["run_id"])
                    notice("ok", f"Email sent to {recipient}.") if send else notice("info", "Draft saved. Nothing was sent.")
                except Exception as e:  # noqa: BLE001
                    notice("bad", f"Email failed: {e}")
        draft = read_text(orch.EMAIL_TXT_PATH)
        if draft:
            with st.container(border=True):
                render(f'<p class="card-title">{icon("mail")}Draft preview</p>')
                st.code(clean_text(draft), language=None, wrap_lines=True)
        else:
            st.caption("No draft yet. Generate one to preview it here.")

    with t_data:
        if S["themes"]:
            label_by_id = {t["theme_id"]: t.get("label") for t in S["themes"]}
            df = pd.DataFrame([
                {"Theme": label_by_id[t["theme_id"]], "Rating": r.get("rating"), "Review": clean_text(r.get("review_text", "")),
                 "Date": (r.get("review_date") or "")[:10]} for t in S["themes"] for r in t.get("reviews", [])])
            pick = st.multiselect("Filter by theme", sorted(df["Theme"].unique()))
            st.dataframe(df[df["Theme"].isin(pick)] if pick else df, width="stretch", hide_index=True, height=420)


def page_history():
    S = STATE
    runs = S["runs"]
    page_header("Run history", "Every pipeline run with its status and volume, plus Gemini usage and API cost.")
    t_runs, t_usage = st.tabs([":material/history: Runs", ":material/payments: Usage and cost"])
    with t_runs:
        runs_section(S, runs)
    with t_usage:
        usage_section()


def runs_section(S, runs):
    if not runs:
        render(card("Runs", "history", f'<div class="empty">{icon("history")}<b>No runs recorded</b>Completed and failed runs appear here.</div>'))
        return
    status = {"completed": badge("Completed", "success", "check_circle"), "failed": badge("Failed", "destructive", "error"),
              "running": badge("Running", "warning", "progress_activity")}
    rows = [[esc(r["run_id"]), fmt_dt(r.get("started_at")), "CSV upload" if r.get("source") == "csv" else "Play Store",
             str(r.get("review_count", 0)), str(r.get("theme_count", 0)), f'{r.get("tokens", 0):,}',
             fmt_usd(r.get("cost_usd")), status.get(r.get("status"), "")] for r in runs[:25]]
    render(card("Runs", "history", table(["Run", "Started", "Source", "Reviews", "Themes", "Tokens", "Cost", "Status"], rows, num_cols=(3, 4, 5, 6), hide_mobile=(2, 4, 5))))

    done = [r["run_id"] for r in runs if r.get("status") == "completed"]
    if done:
        chosen = st.selectbox("Open archived run", done)
        archived = orch.read_run_file(chosen, "output", "weekly_pulse.md")
        if archived:
            with st.expander("Archived weekly pulse", expanded=True):
                with st.container(key="archived_doc"):
                    st.markdown(soft_breaks(clean_text(archived)))
                st.download_button("Download", archived, f"{chosen}_weekly_pulse.md", icon=":material/download:")
    err = [r for r in runs if r.get("status") == "failed" and r.get("error")][:1]
    if err:
        st.caption(f"Most recent failure ({err[0]['run_id']}): {err[0]['error']}")


def usage_section():
    S = STATE
    calls = S["calls"]

    done = [r for r in S["runs"] if r.get("status") == "completed" and r.get("cost_usd")]
    avg_run = sum(r["cost_usd"] for r in done) / len(done) if done else None
    total = float(calls["cost_usd"].sum()) if not calls.empty else 0.0
    tokens = int(calls["prompt_tokens"].sum() + calls["output_tokens"].sum()) if not calls.empty else 0
    kpi_grid([
        ("payments", "Total spend", fmt_usd(total), f"{len(calls):,} API calls, all time"),
        ("receipt_long", "Average cost per run", fmt_usd(avg_run), f"Across {len(done)} priced runs" if done else "No priced runs yet"),
        ("calendar_month", "Projected monthly", fmt_usd(avg_run * 52 / 12) if avg_run else "-", "One weekly run, about 4.3 per month"),
        ("token", "Total tokens", f"{tokens:,}", "Input plus output, including thinking"),
    ])

    pt = usage_svc.pricing_table()
    render(card("Model pricing", "sell", table(
        ["Model", "Used for", "Input per 1M", "Output per 1M"],
        [[esc(r["Model"]), esc(r["Used for"]), f'${r["Input $/1M"]:.2f}', f'${r["Output $/1M"]:.2f}'] for _, r in pt.iterrows()], num_cols=(2, 3), hide_mobile=(1,)),
        "Paid-tier standard text pricing from Google. The synthesis model rises to $1.50 input and $7.50 output on 1 Jan 2027."))

    if calls.empty:
        render(card("Spend breakdown", "bar_chart", f'<div class="empty">{icon("payments")}<b>No API calls logged</b>Run the pipeline to start tracking cost.</div>'))
        return

    c1, c2 = st.columns(2, gap="medium")
    by_step = calls.groupby("step").agg(calls=("step", "size"), prompt=("prompt_tokens", "sum"), output=("output_tokens", "sum"),
                                        cost=("cost_usd", "sum")).sort_values("cost", ascending=False).reset_index()
    with c1:
        with st.container(border=True):
            render(f'<p class="card-title">{icon("bar_chart")}Spend by step</p>')
            fig = go.Figure(go.Bar(y=by_step["step"], x=by_step["cost"], orientation="h", marker=dict(color=T["chart"][0], cornerradius=5),
                                   hovertemplate="%{y}: $%{x:.4f}<extra></extra>"))
            chart_layout(fig, 260)
            fig.update_yaxes(autorange="reversed", tickfont=dict(color=T["muted_fg"]))
            fig.update_xaxes(showgrid=True, gridcolor=T["border"], tickprefix="$", tickfont=dict(color=T["muted_fg"]))
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with c2:
        by_day = calls.assign(day=calls["ts"].dt.strftime("%d %b")).groupby("day", sort=False)["cost_usd"].sum().reset_index()
        with st.container(border=True):
            render(f'<p class="card-title">{icon("show_chart")}Daily spend</p>')
            fig = go.Figure(go.Bar(x=by_day["day"], y=by_day["cost_usd"], marker=dict(color=T["chart"][1], cornerradius=5),
                                   hovertemplate="%{x}: $%{y:.4f}<extra></extra>"))
            chart_layout(fig, 260)
            fig.update_yaxes(showgrid=True, gridcolor=T["border"], tickprefix="$", tickfont=dict(color=T["muted_fg"]))
            fig.update_xaxes(showgrid=False, type="category", tickfont=dict(color=T["muted_fg"]))
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    render(card("Cost by step", "functions", table(
        ["Step", "Calls", "Input tokens", "Output tokens", "Cost"],
        [[esc(r.step), str(r.calls), f"{int(r.prompt):,}", f"{int(r.output):,}", fmt_usd(r.cost)] for r in by_step.itertuples()], num_cols=(1, 2, 3, 4), hide_mobile=(1, 2))))

    with st.expander("Recent API calls"):
        recent = calls.sort_values("ts", ascending=False).head(50).rename(columns={
            "ts": "Time", "step": "Step", "model": "Model", "prompt_tokens": "Input", "output_tokens": "Output", "cost_usd": "Cost (USD)", "latency_s": "Latency (s)"})
        st.dataframe(recent, width="stretch", hide_index=True)
    st.caption("Estimates use Google's published prices and may differ from your invoice. Check Google AI Studio billing for the authoritative figure.")


# ---------------------------------------------------------------------------
# App shell: sidebar navigation
# ---------------------------------------------------------------------------
STATE = load_state()

P = dict(
    overview=st.Page(page_overview, title="Overview", icon=":material/dashboard:", url_path="overview", default=True),
    reviews=st.Page(page_reviews, title="Reviews", icon=":material/rate_review:", url_path="reviews"),
    report=st.Page(page_report, title="Report", icon=":material/description:", url_path="report"),
    pipeline=st.Page(page_pipeline, title="Pipeline", icon=":material/play_circle:", url_path="pipeline"),
    history=st.Page(page_history, title="Run history", icon=":material/history:", url_path="history"),
)
NAV_GROUPS = [("Analyze", ["overview", "reviews", "report"]), ("Operate", ["pipeline", "history"])]
nav = st.navigation(list(P.values()), position="hidden")


active = "" if nav.url_path in ("", "overview") else nav.url_path
extra = (
    f'[data-testid="stSidebar"] a[href="{active}"] {{ background:var(--accent); }}'
    f'[data-testid="stSidebar"] a[href="{active}"] p, [data-testid="stSidebar"] a[href="{active}"] span[data-testid="stIconMaterial"] {{ color:var(--foreground) !important; font-weight:700; }}'
    f'[data-testid="stSidebar"] a[href="{active}"]::before {{ content:""; position:absolute; left:-12px; top:8px; bottom:8px; width:3px; border-radius:0 3px 3px 0; background:var(--primary); }}'
)
if STATE["runs"]:
    extra += (f'[data-testid="stSidebar"] a[href="history"]::after {{ content:"{len(STATE["runs"])}"; margin-left:auto; font-size:11px; font-weight:700; '
              'color:var(--muted-foreground); background:var(--muted); padding:1px 8px; border-radius:99px; }')
inject_css(extra)

with st.sidebar:
    with st.container(key="sb_brand_c"):
        render(f'<div class="sb-brand"><div class="sb-mark">{icon("monitoring")}</div>'
               '<div><p class="sb-title">Weekly Review Pulse</p><p class="sb-sub">Groww Mutual Fund</p></div></div>')
    for gi, (group, keys) in enumerate(NAV_GROUPS):
        with st.container(key=f"sb_group_{gi}"):
            for k in keys:
                st.page_link(P[k], label=P[k].title, icon=P[k].icon)

    last = STATE["last_run"]
    with st.container(key="sb_footer"):
        st.toggle(":material/dark_mode: Dark mode", key="dark_mode")

nav.run()
