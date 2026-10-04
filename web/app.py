import os
import sys
import html as html_mod
import torch
import tempfile
import time
import json

if hasattr(torch, 'classes'):
    torch.classes.__path__ = [os.path.join(torch.__path__[0], torch.classes.__file__)]

import streamlit as st
import streamlit.components.v1 as st_components

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ast_parser import ASTParser
from src.feature_extractor import FeatureExtractor
from src.scanner import Scanner
from src.enrichment import PromptEnricher
from src.inference import InferenceEngine
from web.energy_monitor import measure_energy

st.set_page_config(
    page_title="SecureLearn — AI Code Auditor",
    page_icon="https://api.iconify.design/tabler:shield-lock.svg",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.24.0/dist/tabler-icons.min.css">',
    unsafe_allow_html=True
)

st.markdown("""
<style>
/* ═══════════════════════════════════════════════════
   DESIGN TOKENS — GitHub Light Theme
   ═══════════════════════════════════════════════════ */
:root {
    --bg:          #f6f8fa;
    --surface:     #ffffff;
    --surface-2:   #f6f8fa;
    --surface-3:   #eaeef2;
    --border:      #d0d7de;
    --border-light:#d0d7de;

    --accent:      #0969da;
    --accent-hover:#0860ca;
    --accent-bg:   #ddf4ff;
    --accent-rim:  rgba(9, 105, 218, 0.3);

    --danger:      #cf222e;
    --danger-bg:   #ffebe9;
    --warning:     #9a6700;
    --warning-bg:  #fff8c5;
    --success:     #1a7f37;
    --success-bg:  #dafbe1;
    --success-rim: rgba(26, 127, 55, 0.3);

    --ink:         #1f2328;
    --ink-2:       #24292f;
    --ink-muted:   #656d76;
    --ink-faint:   #8c959f;

    --mono: 'Fira Code', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
    --sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    --radius: 8px;
    --shadow-sm: 0 1px 3px rgba(27,31,36,0.12);
    --shadow-md: 0 3px 12px rgba(27,31,36,0.15);
}

/* BASE */
html, body {
    font-family: var(--sans);
    background-color: var(--bg) !important;
    color: var(--ink) !important;
}
.stApp {
    background-color: var(--bg) !important;
}
.block-container {
    padding-top: 1rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
    padding-bottom: 2.5rem !important;
    max-width: 1280px !important;
    margin: 0 auto !important;
}
#MainMenu, footer, header { visibility: hidden; }

/* TEXT */
.stMarkdown p, .stMarkdown span, .stMarkdown li,
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4, .stMarkdown h5 {
    color: var(--ink) !important;
}
.stTextInput > label > div > p,
.stSelectbox  > label > div > p {
    color: var(--ink) !important;
}

/* INPUTS */
.stTextInput input {
    background: var(--surface-2) !important;
    border: 1px solid var(--border-light) !important;
    border-radius: var(--radius) !important;
    color: var(--ink) !important;
}
.stTextInput input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-rim) !important;
    outline: none !important;
}

/* CODE BLOCKS (st.code) */
.stCodeBlock {
    border-radius: var(--radius) !important;
    border: 1px solid var(--border-light) !important;
}
pre code { font-size: 0.84rem !important; line-height: 1.55 !important; }

/* EXPANDER */
details {
    background: var(--surface) !important;
    border: 1px solid var(--border-light) !important;
    border-radius: var(--radius) !important;
    margin-bottom: 8px !important;
}
details > summary {
    background: var(--surface-2) !important;
    color: var(--ink) !important;
    padding: 8px 12px !important;
}
details > summary p { color: var(--ink) !important; font-weight: 600; margin: 0 !important; }

/* TABS */
[data-testid="stTabs"] { background: transparent !important; margin-bottom: 14px !important; }
[data-testid="stTabs"] [role="tab"] {
    color: var(--ink-muted) !important; font-weight: 600 !important;
    font-size: 0.9rem !important; padding: 6px 18px !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: var(--accent) !important; border-bottom: 2px solid var(--accent) !important;
}
[data-testid="stTabs"] [role="tab"]:hover {
    color: var(--ink) !important; background: var(--surface-2) !important;
}

/* BUTTONS */
[data-testid="stBaseButton-primary"] button {
    background: var(--accent) !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: var(--radius) !important;
    padding: 0.5rem 1.4rem !important;
    transition: background .15s !important;
}
[data-testid="stBaseButton-primary"] button:hover {
    background: var(--accent-hover) !important;
}
[data-testid="stBaseButton-secondary"] button {
    background: var(--surface) !important;
    color: var(--ink) !important;
    border: 1px solid var(--border-light) !important;
    border-radius: var(--radius) !important;
    font-weight: 600 !important;
}
[data-testid="stBaseButton-secondary"] button:hover {
    background: var(--surface-3) !important;
    border-color: var(--accent) !important;
    color: var(--accent) !important;
}
[data-testid="stLinkButton"] a {
    background: var(--surface) !important;
    color: var(--ink) !important;
    border: 1px solid var(--border-light) !important;
    border-radius: var(--radius) !important;
    font-weight: 600 !important;
}
[data-testid="stLinkButton"] a:hover {
    background: var(--surface-3) !important;
    border-color: var(--accent) !important; color: var(--accent) !important;
}

/* METRICS & ALERTS */
[data-testid="stMetricValue"] { color: var(--ink) !important; }
[data-testid="stMetricLabel"] > div > p { color: var(--ink-muted) !important; }
[data-testid="stSpinner"] p { color: var(--ink-muted) !important; }
[data-testid="stAlert"] {
    background: var(--surface) !important;
    border: 1px solid var(--border-light) !important;
    border-radius: var(--radius) !important;
}
[data-testid="stAlert"] p { color: var(--ink) !important; }

/* FILE UPLOADER */
[data-testid="stFileUploadDropzone"] {
    background: var(--surface) !important;
    border: 2px dashed var(--border-light) !important;
    border-radius: var(--radius) !important;
}
[data-testid="stFileUploadDropzone"] * { color: var(--ink-muted) !important; }
[data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"] button {
    background: var(--surface) !important;
    color: var(--ink-2) !important;
    border-color: var(--border-light) !important;
}

/* CODE EDITOR TEXTAREA - fixed 25-line viewport; longer code scrolls inside the box.
   (JS in the editor section adds the line-number gutter next to it.) */
:root { --code-lines: 25; --code-lh: 22.4px; --code-fs: 14px; }

.stTextArea { margin-top: 0 !important; margin-bottom: 0 !important; }
.stTextArea > label { display: none !important; }
.stTextArea [data-baseweb="textarea"] {
    background: #ffffff !important;
    border: 1px solid #d0d7de !important;
    border-top: none !important;
    border-radius: 0 0 8px 8px !important;
    overflow: hidden !important;
    padding: 0 !important;
    box-shadow: 0 2px 8px rgba(27,31,36,0.10) !important;
}
.stTextArea [data-baseweb="base-input"] { background: transparent !important; border: none !important; }
.stTextArea textarea {
    font-family: 'Fira Code', ui-monospace, 'SF Mono', Menlo, Consolas, monospace !important;
    font-size: var(--code-fs) !important;
    line-height: var(--code-lh) !important;
    /* exactly 25 lines + 6px top / 18px bottom padding */
    height: calc(var(--code-lines) * var(--code-lh) + 24px) !important;
    min-height: calc(var(--code-lines) * var(--code-lh) + 24px) !important;
    max-height: calc(var(--code-lines) * var(--code-lh) + 24px) !important;
    background: #ffffff !important;
    color: #24292f !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    /* 68px left padding = room for the 56px line-number gutter */
    padding: 6px 18px 18px 68px !important;
    white-space: pre !important;          /* no soft-wrap: keeps line numbers aligned */
    overflow-wrap: normal !important;
    overflow: auto !important;
    resize: none !important;
    tab-size: 4;
    outline: none !important;
    caret-color: #0969da !important;
}
.stTextArea textarea:focus { outline: none !important; box-shadow: none !important; border: none !important; }

/* Slim scrollbars (editor + read-only viewer) */
.stTextArea textarea, .hl-code-wrap { scrollbar-width: thin; scrollbar-color: #c1c8d0 #f6f8fa; }
.stTextArea textarea::-webkit-scrollbar, .hl-code-wrap::-webkit-scrollbar { width: 10px; height: 10px; }
.stTextArea textarea::-webkit-scrollbar-track, .hl-code-wrap::-webkit-scrollbar-track { background: #f6f8fa; }
.stTextArea textarea::-webkit-scrollbar-thumb, .hl-code-wrap::-webkit-scrollbar-thumb {
    background: #c1c8d0; border-radius: 6px; border: 2px solid #f6f8fa;
}

/* SIDEBAR */
section[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid var(--border-light) !important;
}
.sb-section-title {
    font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 2px; color: var(--accent);
    margin: 18px 0 8px 0; padding-bottom: 6px; border-bottom: 1px solid var(--border);
}
.sb-lang-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 4px; }
.sb-lang {
    background: var(--surface); border: 1px solid var(--border-light); border-radius: 6px;
    padding: 4px 10px; font-size: 0.78rem; color: var(--ink);
    display: flex; align-items: center; gap: 5px;
}
.sb-step-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 0.83rem; color: var(--ink-2); }
.sb-step-num {
    width: 20px; height: 20px; border-radius: 50%;
    background: var(--surface-2); border: 1px solid var(--border-light);
    color: var(--accent); font-size: 0.68rem; font-weight: 700;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.model-pill {
    background: var(--surface); border: 1px solid var(--border-light); border-radius: var(--radius);
    padding: 10px 14px; font-family: var(--mono); font-size: 0.77rem; color: var(--ink-2);
    word-break: break-all; display: flex; align-items: center; gap: 8px; margin: 6px 0 14px 0;
}
.model-pill .ti { color: var(--accent); font-size: 1rem; flex-shrink: 0; }

/* HERO BANNER */
.hero-banner {
    background: var(--surface);
    border: 1px solid var(--border-light);
    border-radius: var(--radius); padding: 20px 28px; margin-bottom: 16px;
    position: relative; overflow: hidden;
}
.hero-banner::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0;
    height: 2px; background: linear-gradient(90deg, var(--accent), #3fb950, var(--accent));
}
.hero-title {
    font-size: 1.7rem; font-weight: 800; letter-spacing: -0.3px;
    color: var(--ink); margin: 0 0 4px 0; display: flex; align-items: center; gap: 10px;
}
.hero-title-icon { color: var(--accent); font-size: 1.7rem; }
.hero-sub { font-size: 0.88rem; color: var(--ink-muted); font-weight: 400; margin: 0; }

/* WORKFLOW INDICATOR */
.workflow-bar {
    display: flex; align-items: stretch;
    background: var(--surface); border: 1px solid var(--border-light);
    border-radius: var(--radius); overflow: hidden;
    margin-bottom: 16px;
}
.wf-step {
    flex: 1; display: flex; align-items: center; justify-content: center;
    gap: 5px; padding: 9px 6px; font-size: 0.74rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.5px; color: var(--ink-faint);
    border-right: 1px solid var(--border-light); white-space: nowrap;
}
.wf-step:last-child { border-right: none; }
.wf-step.wf-done   { color: var(--accent); background: rgba(88,166,255,0.07); }
.wf-step.wf-active { color: var(--ink); background: var(--surface-2); font-weight: 700; border-bottom: 2px solid var(--accent); }
.wf-step.wf-verify-done { color: var(--success); background: rgba(63,185,80,0.07); border-bottom: 2px solid var(--success); }
.wf-step i { font-size: 0.85rem; }

/* METRIC CARDS — compact */
.metric-card {
    background: var(--surface); border: 1px solid var(--border-light);
    border-radius: var(--radius); padding: 12px 14px; text-align: center;
}
.metric-card:hover { border-color: var(--accent); }
.metric-value { font-size: 1.8rem; font-weight: 800; line-height: 1; color: var(--ink); }
.metric-label { font-size: 0.7rem; color: var(--ink-muted); text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }

/* FINDING CARDS */
.finding-card {
    border-radius: var(--radius); padding: 12px 16px; margin-bottom: 8px;
    background: var(--surface); border: 1px solid var(--border-light);
    border-left: 4px solid var(--border-light);
    box-shadow: var(--shadow-sm);
}
.finding-HIGH   { border-left-color: var(--danger);  background: #ffebe9; }
.finding-MEDIUM { border-left-color: var(--warning); background: #fff8c5; }
.finding-LOW    { border-left-color: var(--accent);  background: #ddf4ff; }
.finding-header { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1.2px; font-weight: 700; margin-bottom: 5px; display: flex; align-items: center; gap: 6px; }
.finding-msg  { font-size: 0.9rem; color: var(--ink); line-height: 1.5; }
.finding-line { font-size: 0.76rem; color: var(--ink-muted); margin-top: 5px; font-family: var(--mono); }

/* ─────────────────────────────────────────────────────
   CODE PANEL — GitHub-Light IDE style (read + edit)
   ───────────────────────────────────────────────────── */
.code-panel {
    background: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: var(--radius);
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(27,31,36,0.1);
}
.code-panel-bar {
    display: flex; align-items: center; justify-content: space-between;
    background: #f6f8fa; border-bottom: 1px solid #d0d7de;
    padding: 6px 16px; font-size: 0.8rem; font-family: var(--mono); color: #656d76;
}
.code-panel-lang {
    display: inline-flex; align-items: center; gap: 5px;
    background: #ddf4ff; border: 1px solid rgba(9,105,218,0.3);
    border-radius: 4px; padding: 2px 12px; font-size: 0.72rem; color: #0969da;
    font-weight: 700; letter-spacing: 0.8px; text-transform: uppercase;
}
.hl-code-wrap {
    background: #ffffff; overflow: auto; margin: 0;
    /* exactly 25 rows visible, the rest scrolls */
    max-height: calc(var(--code-lines, 25) * var(--code-lh, 22.4px));
}
.hl-code-table {
    border-collapse: collapse; width: 100%;
    border-spacing: 0;
}
/* Explicitly kill any border on rows and cells */
.hl-code-table tr,
.hl-code-table td { border-top: none !important; border-bottom: none !important; }

.hl-line-num {
    user-select: none; text-align: right; padding: 0 12px 0 8px;
    color: #adb5bd; font-size: 0.8rem; font-family: var(--mono);
    border-right: 1px solid #e4e7eb; white-space: nowrap; vertical-align: top;
    min-width: 48px; background: #f8f9fa;
    font-weight: 400; letter-spacing: 0;
    line-height: var(--code-lh, 22.4px);
    height: var(--code-lh, 22.4px);
}
.hl-line-code {
    padding: 0 20px 0 14px; font-size: var(--code-fs, 14px); font-family: var(--mono);
    line-height: var(--code-lh, 22.4px); white-space: pre; color: #24292f;
    vertical-align: top; width: 100%; font-weight: 400;
    height: var(--code-lh, 22.4px);
}
/* Highlighted rows — no border between cells, just background */
tr.hl-HIGH   .hl-line-num,
tr.hl-HIGH   .hl-line-code { background: #ffebe9; }
tr.hl-HIGH   .hl-line-num  { border-left: 3px solid #cf222e; color: #cf222e; font-weight: 600; border-right-color: #f5c6c6; }

tr.hl-MEDIUM .hl-line-num,
tr.hl-MEDIUM .hl-line-code { background: #fff8c5; }
tr.hl-MEDIUM .hl-line-num  { border-left: 3px solid #9a6700; color: #9a6700; font-weight: 600; border-right-color: #e8d8a0; }

tr.hl-LOW    .hl-line-num,
tr.hl-LOW    .hl-line-code { background: #ddf4ff; }
tr.hl-LOW    .hl-line-num  { border-left: 3px solid #0969da; color: #0969da; font-weight: 600; border-right-color: #b6d4f7; }

/* Legend row inside panel bar */
.hl-legend {
    display: flex; gap: 14px; flex-wrap: wrap; font-size: 0.74rem;
    color: #656d76; align-items: center;
}
.hl-legend-item { display: flex; align-items: center; gap: 5px; font-weight: 600; }
.hl-dot { width: 8px; height: 8px; border-radius: 2px; flex-shrink: 0; }
.hl-dot-HIGH   { background: #cf222e; }
.hl-dot-MEDIUM { background: #9a6700; }
.hl-dot-LOW    { background: #0969da; }

/* TAGS */
.tag-container { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.tag {
    background: var(--surface-2); border: 1px solid var(--border-light); color: var(--ink-2);
    border-radius: 4px; padding: 2px 8px; font-size: 0.74rem; font-family: var(--mono);
}
.tag.sink    { border-color: var(--danger); color: var(--danger); background: var(--danger-bg); }
.tag.none    { color: var(--ink-faint); }
.tag-HIGH   { background: var(--danger-bg);  color: var(--danger); border: 1px solid rgba(207,34,46,0.4); font-weight: 700; border-radius: 4px; padding: 2px 8px; font-size: 0.74rem; }
.tag-MEDIUM { background: var(--warning-bg); color: var(--warning); border: 1px solid rgba(154,103,0,0.4); font-weight: 700; border-radius: 4px; padding: 2px 8px; font-size: 0.74rem; }
.tag-LOW    { background: var(--accent-bg);  color: var(--accent); border: 1px solid rgba(9,105,218,0.4); font-weight: 700; border-radius: 4px; padding: 2px 8px; font-size: 0.74rem; }

/* STAGE HEADERS */
.stage-header {
    font-size: 0.95rem; font-weight: 700; color: var(--ink);
    padding: 9px 14px; margin: 18px 0 12px 0;
    background: var(--surface); border: 1px solid var(--border-light);
    border-left: 3px solid var(--accent);
    border-radius: 0 var(--radius) var(--radius) 0;
    display: flex; align-items: center; gap: 10px;
    box-shadow: var(--shadow-sm);
}
.stage-header i { color: var(--accent); font-size: 1.05rem; }
.stage-header .stage-num {
    background: var(--accent); color: #ffffff; border-radius: 50%;
    width: 20px; height: 20px; font-size: 0.7rem; font-weight: 800;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}

/* SECTION HEADER */
.section-header {
    font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px;
    color: var(--accent); padding: 0 0 6px 0; border-bottom: 1px solid var(--border-light);
    margin-bottom: 12px; display: flex; align-items: center; gap: 8px;
}

/* SUMMARY BOX */
.summary-box {
    background: var(--surface); border: 1px solid var(--border-light); border-radius: var(--radius);
    padding: 16px 20px; font-size: 0.92rem; line-height: 1.65;
    color: var(--ink-2);
}

/* GAUGE */
.gauge-container {
    background: var(--surface); border-radius: var(--radius); border: 1px solid var(--border-light);
    padding: 16px 20px; text-align: center; margin-bottom: 14px;
}
.gauge-label { font-size: 0.7rem; color: var(--ink-muted); text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 6px; }
.gauge-score { font-size: 2.8rem; font-weight: 900; line-height: 1; font-family: var(--mono); }
.gauge-score-denom { font-size: 1.1rem; color: var(--ink-faint); }
.gauge-bar-bg { background: var(--surface-2); border-radius: 99px; height: 8px; margin: 10px 0 4px 0; overflow: hidden; border: 1px solid var(--border-light); }
.gauge-bar-fill { height: 100%; border-radius: 99px; }
.gauge-range { font-size: 0.7rem; color: var(--ink-muted); }

/* BASELINE BANNER */
.baseline-banner {
    background: rgba(88,166,255,0.07); border: 1px solid var(--accent-rim); border-radius: var(--radius);
    padding: 9px 16px; margin-bottom: 14px;
    display: flex; align-items: center; gap: 10px; font-size: 0.84rem; color: var(--ink);
}
.baseline-banner i { color: var(--accent); font-size: 1.1rem; flex-shrink: 0; }
.baseline-banner strong { color: var(--accent); }

/* VERIFY STAGE */
.verif-status-row {
    display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap;
}
.verif-badge {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 3px 10px; border-radius: 4px; font-size: 0.76rem; font-weight: 700;
}
.verif-badge.resolved      { background: var(--success-bg); color: var(--success); border: 1px solid var(--success-rim); }
.verif-badge.still-present { background: var(--warning-bg); color: var(--warning); border: 1px solid rgba(210,153,34,0.3); }
.verif-badge.new-issue     { background: var(--danger-bg);  color: var(--danger); border: 1px solid rgba(248,81,73,0.3); }

/* PIPELINE STEPS */
.pipeline-step {
    display: flex; align-items: center; gap: 10px; padding: 8px 12px;
    background: var(--surface); border-radius: var(--radius); margin-bottom: 6px;
    font-size: 0.84rem; border: 1px solid var(--border-light); color: var(--ink);
}
.step-status { margin-left: auto; font-size: 0.72rem; font-weight: 600; display: flex; align-items: center; gap: 4px; }
.step-done .step-status { color: var(--success); }
.step-run  .step-status { color: var(--accent); }
.step-wait .step-status { color: var(--ink-faint); }

.ti     { vertical-align: -0.125em; }
.ti-lg  { font-size: 1.3rem; vertical-align: -0.2em; }
.ti-hero { font-size: 2rem; vertical-align: -0.25em; margin-right: 8px; }
.ti-step { font-size: 0.95rem; vertical-align: -0.12em; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════
# CACHED MODEL LOAD
# ═══════════════════════════════════════════════════
@st.cache_resource(show_spinner=False)
def load_inference_engine():
    return InferenceEngine()


# ═══════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════
def risk_color(score: float) -> str:
    if score >= 8: return "var(--danger)"
    if score >= 5: return "var(--warning)"
    if score >= 2: return "var(--accent)"
    return "var(--ink-muted)"

def risk_label(score: float) -> str:
    if score >= 8:  return "CRITICAL"
    if score >= 5:  return "HIGH"
    if score >= 2:  return "MEDIUM"
    return "LOW"

def sev_color(sev: str) -> str:
    return {"HIGH": "var(--danger)", "MEDIUM": "var(--warning)", "LOW": "var(--accent)"}.get(sev, "var(--ink-muted)")

def severity_icon_html(sev: str) -> str:
    icons = {
        "HIGH":   '<i class="ti ti-circle-x"></i>',
        "MEDIUM": '<i class="ti ti-alert-triangle"></i>',
        "LOW":    '<i class="ti ti-info-circle"></i>',
    }
    return icons.get(sev.upper(), '<i class="ti ti-circle"></i>')


def render_gauge(score: float, title: str = "Baseline Risk Score"):
    color = risk_color(score)
    label = risk_label(score)
    pct   = int((score / 10.0) * 100)
    st.markdown(f"""
    <div class="gauge-container">
        <div class="gauge-label"><i class="ti ti-shield-half-filled" style="margin-right:5px;"></i>{title}</div>
        <div class="gauge-score" style="color:{color};">{score}<span class="gauge-score-denom">/10</span></div>
        <div style="font-size:0.85rem;font-weight:700;letter-spacing:2px;color:{color};margin-top:4px;">{label}</div>
        <div class="gauge-bar-bg">
            <div class="gauge-bar-fill" style="width:{pct}%;background-color:{color};"></div>
        </div>
        <div class="gauge-range">0 &mdash; Safe &nbsp;&nbsp;&nbsp; 10 &mdash; Critical</div>
    </div>""", unsafe_allow_html=True)


def render_finding(f: dict):
    from src.vuln_classifier import normalize_severity
    sev   = normalize_severity(f.get('severity', 'INFO')).upper()
    msg   = f.get('message', '')
    line  = f.get('line', '?')
    icon  = severity_icon_html(sev)
    hdr_color = sev_color(sev)
    st.markdown(f"""
    <div class="finding-card finding-{sev}">
        <div class="finding-header" style="color:{hdr_color};">{icon} {sev} VULNERABILITY</div>
        <div class="finding-msg">{msg}</div>
        <div class="finding-line"><i class="ti ti-code" style="margin-right:4px;"></i>Line {line}</div>
    </div>""", unsafe_allow_html=True)


def render_tags(items: list, kind: str = "source"):
    if not items:
        st.markdown('<div class="tag-container"><span class="tag none">none detected</span></div>', unsafe_allow_html=True)
        return
    tags_html = "".join(f'<span class="tag {kind}">{x}</span>' for x in set(items))
    st.markdown(f'<div class="tag-container">{tags_html}</div>', unsafe_allow_html=True)


def render_workflow(stage: str):
    """Render the workflow progress bar. stage: analyze|understand|learn|edit|verify|verified"""
    stages = [
        ("ti-upload",       "1. Analyze"),
        ("ti-book",         "2. Understand"),
        ("ti-school",       "3. Learn"),
        ("ti-pencil",       "4. Edit Code"),
        ("ti-pencil-check", "5. Verify Fix"),
    ]
    stage_map = {
        "analyze": 0, "understand": 1, "learn": 2,
        "edit": 3, "verify": 4, "verified": 4,
    }
    active_idx = stage_map.get(stage, 0)
    html = '<div class="workflow-bar">'
    for idx, (icon, name) in enumerate(stages):
        if idx < active_idx:
            cls    = "wf-step wf-done"
            prefix = '<i class="ti ti-circle-check"></i>'
        elif idx == active_idx:
            if stage == "verified":
                cls    = "wf-step wf-verify-done"
                prefix = '<i class="ti ti-circle-check"></i>'
            else:
                cls    = "wf-step wf-active"
                prefix = f'<i class="ti {icon}"></i>'
        else:
            cls    = "wf-step"
            prefix = f'<i class="ti {icon}"></i>'
        html += f'<div class="{cls}">{prefix} {name}</div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_stage_header(num: int, icon: str, title: str, subtitle: str = ""):
    sub_html = f'<div style="font-size:0.82rem;font-weight:400;color:var(--ink-muted);margin-top:2px;">{subtitle}</div>' if subtitle else ""
    st.markdown(f"""
    <div class="stage-header">
        <div class="stage-num">{num}</div>
        <i class="ti {icon}"></i>
        <div>
            <div>{title}</div>
            {sub_html}
        </div>
    </div>""", unsafe_allow_html=True)


def render_highlighted_code(code: str, findings: list, language: str = ""):
    """
    Render source code as an HTML table with per-line severity highlighting.
    HIGH   -> red background row & red left border
    MEDIUM -> yellow/amber background row & yellow left border
    LOW    -> blue background row & blue left border
    Dynamic: only lines that appear in 'findings' are highlighted.
    """
    from src.vuln_classifier import normalize_severity

    line_sev: dict[int, str] = {}
    sev_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    for f in findings:
        try:
            ln = int(f.get('line', 0))
        except (ValueError, TypeError):
            continue
        s = normalize_severity(f.get('severity', 'INFO')).upper()
        if ln not in line_sev or sev_order.get(s, 0) > sev_order.get(line_sev[ln], 0):
            line_sev[ln] = s

    has_high   = any(v == "HIGH"   for v in line_sev.values())
    has_medium = any(v == "MEDIUM" for v in line_sev.values())
    has_low    = any(v == "LOW"    for v in line_sev.values())

    legend_items = []
    if has_high:
        legend_items.append('<div class="hl-legend-item"><div class="hl-dot hl-dot-HIGH"></div><span>High Severity</span></div>')
    if has_medium:
        legend_items.append('<div class="hl-legend-item"><div class="hl-dot hl-dot-MEDIUM"></div><span>Medium Severity</span></div>')
    if has_low:
        legend_items.append('<div class="hl-legend-item"><div class="hl-dot hl-dot-LOW"></div><span>Low Severity</span></div>')
    if legend_items:
        legend_items.append('<div class="hl-legend-item" style="margin-left:auto;font-style:italic;">Highlighted lines contain detected security issues</div>')

    legend_html = f'<div class="hl-legend">{"".join(legend_items)}</div>' if legend_items else ""

    code_lines = code.split('\n')
    rows = []
    for i, line in enumerate(code_lines, 1):
        sev = line_sev.get(i, '')
        row_cls  = f'hl-{sev}' if sev else ''
        sev_icon = ''
        if sev == 'HIGH':
            sev_icon = ' ●'
        elif sev == 'MEDIUM':
            sev_icon = ' ◆'
        elif sev == 'LOW':
            sev_icon = ' ▸'
        escaped = html_mod.escape(line) if line else '&nbsp;'
        rows.append(
            f'<tr class="{row_cls}">'
            f'<td class="hl-line-num">{i}{sev_icon}</td>'
            f'<td class="hl-line-code">{escaped}</td>'
            f'</tr>'
        )

    # Legend chips for the IDE tab-bar
    legend_chips = ""
    if has_high:
        legend_chips += '<span style="display:inline-flex;align-items:center;gap:3px;background:#ffebe9;border:1px solid rgba(207,34,46,0.4);border-radius:3px;padding:1px 7px;font-size:0.71rem;color:#cf222e;font-weight:700;">● HIGH</span>'
    if has_medium:
        legend_chips += '<span style="display:inline-flex;align-items:center;gap:3px;background:#fff8c5;border:1px solid rgba(154,103,0,0.4);border-radius:3px;padding:1px 7px;font-size:0.71rem;color:#9a6700;font-weight:700;">◆ MEDIUM</span>'
    if has_low:
        legend_chips += '<span style="display:inline-flex;align-items:center;gap:3px;background:#ddf4ff;border:1px solid rgba(9,105,218,0.4);border-radius:3px;padding:1px 7px;font-size:0.71rem;color:#0969da;font-weight:700;">▸ LOW</span>'
    lang_display = language.upper() if language else "CODE"
    total_vuln = len(line_sev)
    vuln_chip = (
        f'<span style="font-size:0.7rem;color:var(--ink-faint);">{total_vuln} issue{"s" if total_vuln != 1 else ""} flagged</span>'
        if total_vuln > 0 else '<span style="font-size:0.7rem;color:#1a7f37;">✓ No issues flagged</span>'
    )

    table_html = (
        f'<div class="code-panel">'
        f'<div class="code-panel-bar">'
        f'<div style="display:flex;align-items:center;gap:8px;">'
        f'<span class="code-panel-lang">{lang_display}</span>'
        f'<span style="color:var(--ink-muted);font-size:0.73rem;">{len(code_lines)} lines</span>'
        f'</div>'
        f'<div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap;">{legend_chips}&nbsp;{vuln_chip}</div>'
        f'</div>'
        f'<div class="hl-code-wrap">'
        f'<table class="hl-code-table"><tbody>{"".join(rows)}</tbody></table>'
        f'</div>'
        f'</div>'
    )
    st.markdown(table_html, unsafe_allow_html=True)



# ═══════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style="font-size:1.1rem;font-weight:800;color:var(--ink);display:flex;align-items:center;gap:8px;padding-bottom:12px;border-bottom:1px solid var(--border);">
        <i class="ti ti-shield-code" style="color:var(--accent);font-size:1.3rem;"></i> SecureLearn
    </div>

    <div class="sb-section-title">Supported Languages</div>
    <div class="sb-lang-row">
        <span class="sb-lang"><i class="ti ti-brand-python" style="color:var(--accent);"></i> Python</span>
        <span class="sb-lang"><i class="ti ti-coffee" style="color:var(--accent);"></i> Java</span>
        <span class="sb-lang"><i class="ti ti-brand-javascript" style="color:var(--accent);"></i> JS</span>
        <span class="sb-lang"><i class="ti ti-letter-c" style="color:var(--accent);"></i> C</span>
    </div>

    <div class="sb-section-title">Workflow Stages</div>
    <div class="sb-step-row"><span class="sb-step-num">1</span><i class="ti ti-upload" style="color:var(--accent);"></i> Upload &amp; Analyze</div>
    <div class="sb-step-row"><span class="sb-step-num">2</span><i class="ti ti-book" style="color:var(--accent);"></i> Understand Code &amp; Risks</div>
    <div class="sb-step-row"><span class="sb-step-num">3</span><i class="ti ti-school" style="color:var(--accent);"></i> Learn Security Concepts</div>
    <div class="sb-step-row"><span class="sb-step-num">4</span><i class="ti ti-pencil" style="color:var(--accent);"></i> Edit Code In-Browser</div>
    <div class="sb-step-row"><span class="sb-step-num">5</span><i class="ti ti-pencil-check" style="color:var(--accent);"></i> Re-Audit &amp; Verify Fix</div>

    <div class="sb-section-title">AI &amp; Scanner Engines</div>
    <div class="model-pill">
        <i class="ti ti-brain"></i>Salesforce/codet5-base-multi-sum
    </div>
    <div style="font-size:0.83rem;color:var(--ink-2);display:flex;align-items:center;gap:6px;margin-bottom:8px;">
        <i class="ti ti-shield-check" style="color:var(--accent);"></i> Semgrep + AST/Regex Fallback
    </div>

    <div style="margin-top:28px; margin-bottom: 12px;">
        <div class="sb-section-title">Visualization</div>
    </div>
    """, unsafe_allow_html=True)

    st.link_button("View Advanced Analytics (React Frontend)", "http://localhost:5173", use_container_width=True)

    st.markdown("""
    <div style="margin-top:24px;padding-top:16px;border-top:1px solid var(--border);font-size:0.75rem;color:var(--ink-muted);text-align:center;">
        <i class="ti ti-lock" style="margin-right:4px;"></i> SecureLearn v2.0
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════
# HERO
# ═══════════════════════════════════════════════════
st.markdown("""
<div class="hero-banner">
    <div class="hero-title">
        <i class="ti ti-shield-lock hero-title-icon"></i>
        SecureLearn — AI Code Auditor
    </div>
    <p class="hero-sub">
        Analyze vulnerabilities &nbsp;&middot;&nbsp; Understand program logic &nbsp;&middot;&nbsp;
        Learn secure coding principles &nbsp;&middot;&nbsp; Edit code in-browser &nbsp;&middot;&nbsp; Verify your fixes
    </p>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════
# TABS + INPUTS
# ═══════════════════════════════════════════════════
tab_file, tab_dir, tab_big = st.tabs(["Single File Audit", "Directory Bulk Scan", "Large File Audit"])
uploaded_file = None
dir_path_input = ""
big_file_path  = ""
run_big_btn    = False

with tab_file:
    uploaded_file = st.file_uploader(
        "Drop a source file to begin — the initial audit sets your security baseline",
        type=['py', 'java', 'c', 'js'],
        help="Supported: .py .java .c .js"
    )

with tab_big:
    st.markdown("""<div style='font-size:0.88rem;color:var(--ink-muted);margin-bottom:12px;'>
        <i class='ti ti-info-circle'></i>&nbsp;
        Files over <b style='color:var(--ink);'>200 lines</b> are split into chunks via AST-aware segmentation.
        Each chunk is independently scanned and summarised, then a <b style='color:var(--ink);'>Meta-Transformer</b>
        pass produces a single whole-file narrative.
    </div>""", unsafe_allow_html=True)
    big_uploaded = st.file_uploader(
        "Browse and select a large source file",
        type=['py', 'java', 'c', 'js'],
        help="Supported: .py .java .js .c -- files over 200 lines use chunked analysis",
        key="big_uploader"
    )
    if big_uploaded:
        run_big_btn = st.button("Run Chunked Audit", type="primary", use_container_width=True)

with tab_dir:
    dir_path_input = st.text_input("Enter absolute local folder path to scan:")
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        run_btn = st.button("Run Full Directory Audit", type="primary", use_container_width=True)
    with c_btn2:
        demo_btn = st.button("Load Demo Directory Data (Fast)", use_container_width=True)

if not (uploaded_file or run_btn or demo_btn or run_big_btn or big_uploaded):
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    cards = [
        ("ti-binary-tree",   "AST Analysis",        "Deep structural parsing via Tree-sitter"),
        ("ti-brain",         "AI Summaries",         "CodeT5 generates natural-language explanations"),
        ("ti-shield-search", "Vuln Detection",       "Semgrep + custom AST/Regex hybrid scanner"),
        ("ti-pencil-check",  "Edit &amp; Verify",    "In-browser editing with real-time fix verification"),
    ]
    for col, (icon, title, desc) in zip([c1, c2, c3, c4], cards):
        with col:
            st.markdown(f"""
            <div class="metric-card" style="text-align:center;padding:24px 20px;">
                <i class="ti {icon}" style="font-size:2rem;color:var(--accent);margin-bottom:12px;display:block;"></i>
                <div style="font-weight:700;font-size:1rem;color:var(--ink);margin-bottom:6px;">{title}</div>
                <div style="font-size:0.82rem;color:var(--ink-muted);line-height:1.5;">{desc}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div style="background:var(--surface);border:1px solid var(--border-light);border-radius:var(--radius);
                padding:24px 32px;text-align:center;box-shadow:var(--shadow-sm);">
        <div style="font-size:1.05rem;font-weight:700;color:var(--ink);margin-bottom:10px;">
            <i class="ti ti-route" style="color:var(--accent);margin-right:6px;"></i>Learning &amp; Verification Workflow
        </div>
        <div style="display:flex;align-items:center;justify-content:center;gap:10px;flex-wrap:wrap;
                    font-size:0.85rem;color:var(--ink-muted);">
            <span style="font-weight:700;color:var(--accent);">1. Analyze</span>
            <i class="ti ti-arrow-right"></i>
            <span style="font-weight:700;color:var(--accent);">2. Understand</span>
            <i class="ti ti-arrow-right"></i>
            <span style="font-weight:700;color:var(--accent);">3. Learn</span>
            <i class="ti ti-arrow-right"></i>
            <span style="font-weight:700;color:var(--accent);">4. Edit Code</span>
            <i class="ti ti-arrow-right"></i>
            <span style="font-weight:700;color:var(--success);">5. Verify Fix</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ═══════════════════════════════════════════════════
# DIRECTORY SCAN
# ═══════════════════════════════════════════════════
if run_btn or demo_btn:
    if run_btn and not os.path.isdir(dir_path_input):
        st.error("Directory not found or path empty! Please provide a valid absolute directory path.")
        st.stop()

    st.markdown('''<div class="section-header">
        <i class="ti ti-folder"></i> Directory Scan
    </div>''', unsafe_allow_html=True)

    import json
    from main_folder import bulk_semgrep_scan, analyze_all_files, build_project_map
    inference = load_inference_engine()

    pipeline_ph = st.empty()

    if demo_btn:
        pipeline_ph.markdown("### <i class='ti ti-loader-2'></i> Loading Full Directory Demo Data...", unsafe_allow_html=True)
        time.sleep(0.5)
        demo_res_path = os.path.join(os.path.dirname(__file__), "demo_assets", "demo_results.json")
        demo_energy_path = os.path.join(os.path.dirname(__file__), "demo_assets", "demo_energy.json")
        with open(demo_res_path, 'r') as f:
            results_arr = json.load(f)
        dir_path_input = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        reports_dir = os.path.join(os.path.dirname(__file__), "frontend", "public", "reports")
        os.makedirs(reports_dir, exist_ok=True)
        import shutil
        shutil.copyfile(demo_energy_path, os.path.join(reports_dir, "latest_report.json"))
    else:
        pipeline_ph.markdown("### <i class='ti ti-loader-2'></i> Running Bulk Directory Scan... This may take a while.", unsafe_allow_html=True)
        with measure_energy(sample_interval_s=0.2) as col:
            col.begin_phase("Semgrep Bulk Scan")
            semgrep_map = bulk_semgrep_scan(dir_path_input)
            col.begin_phase("AI Parallel Processing")
            results_arr = analyze_all_files(dir_path_input, semgrep_map, inference)
            col.begin_phase("Map Assembly")
            project_map = build_project_map(results_arr, dir_path_input, inference)
            col.end_phase()
        reports_dir = os.path.join(os.path.dirname(__file__), "frontend", "public", "reports")
        os.makedirs(reports_dir, exist_ok=True)
        with open(os.path.join(reports_dir, "latest_report.json"), "w") as f:
            json.dump(col.report.to_dict(), f)

    pipeline_ph.empty()

    st.markdown('''<div class="section-header"><i class="ti ti-chart-bar"></i> Directory Pipeline Results</div>''', unsafe_allow_html=True)

    total_counts = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
    from src.vuln_classifier import normalize_severity
    for r in results_arr:
        if 'error' in r: continue
        for f in r.get('findings', []):
            sev = normalize_severity(f.get('severity', 'INFO')).upper()
            if sev in total_counts: total_counts[sev] += 1
            else: total_counts['LOW'] += 1

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(f"""<div class="metric-card"><div class="metric-value">{len(results_arr)}</div><div class="metric-label">Files Scanned</div></div>""", unsafe_allow_html=True)
    with c2: st.markdown(f"""<div class="metric-card"><div class="metric-value" style="color:var(--danger);">{total_counts['HIGH']}</div><div class="metric-label">High Severity</div></div>""", unsafe_allow_html=True)
    with c3: st.markdown(f"""<div class="metric-card"><div class="metric-value" style="color:var(--warning);">{total_counts['MEDIUM']}</div><div class="metric-label">Medium Severity</div></div>""", unsafe_allow_html=True)
    with c4: st.markdown(f"""<div class="metric-card"><div class="metric-value" style="color:var(--accent);">{total_counts['LOW']}</div><div class="metric-label">Low Severity</div></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('''<div class="section-header"><i class="ti ti-article"></i> Project AI Overview</div>''', unsafe_allow_html=True)

    from collections import defaultdict
    groups = defaultdict(list)
    for r in sorted(results_arr, key=lambda x: x.get('file', '')):
        if 'error' in r: continue
        rel = os.path.relpath(r['file'], dir_path_input).replace('\\', '/')
        parts = rel.split('/')
        group = parts[0] if len(parts) > 1 else 'root'
        fname = os.path.basename(r.get('file', ''))
        s = r.get('summary', '').strip()
        groups[group].append({'fname': fname, 'summary': s, 'score': r.get('risk_score', 0)})

    for group, entries in sorted(groups.items()):
        with st.expander(f"{group.upper()} ({len(entries)} file{'s' if len(entries)>1 else ''})"):
            for e in entries:
                st.markdown(
                    f"**{e['fname']}** &nbsp;&mdash;&nbsp; "
                    f"<span style='color:var(--ink-muted);'>{e['summary']}</span> "
                    f"<span style='color:var(--ink-muted);font-size:0.85rem;'>*(Score: {e['score']}/10)*</span>",
                    unsafe_allow_html=True
                )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('''<div class="section-header"><i class="ti ti-skull"></i> Top 5 Riskiest Files</div>''', unsafe_allow_html=True)
    ranked_risk = sorted([r for r in results_arr if 'error' not in r], key=lambda x: x.get('risk_score', 0), reverse=True)
    for r in ranked_risk[:5]:
        rel_path = os.path.relpath(r['file'], dir_path_input)
        sev = "HIGH" if r.get('risk_score', 0) >= 8 else "MEDIUM" if r.get('risk_score', 0) >= 5 else "LOW"
        st.markdown(f"""
        <div class="finding-card finding-{sev}">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:600; font-size:0.9rem; color:var(--ink);">{rel_path}</span>
                <span style="font-family:var(--mono); font-weight:800; font-size:1rem; color:var(--ink);">{r.get('risk_score',0)}/10</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.link_button("Open Advanced Analytics (React Frontend)", "http://localhost:5173", use_container_width=True)
    st.stop()


# ═══════════════════════════════════════════════════
# LARGE FILE AUDIT
# ═══════════════════════════════════════════════════
if big_uploaded:
    LANG_MAP_BIG = {'.py': 'python', '.java': 'java', '.js': 'javascript', '.c': 'c'}
    ext_big  = os.path.splitext(big_uploaded.name)[1].lower()
    lang_big = LANG_MAP_BIG.get(ext_big)
    if not lang_big:
        st.error(f"Unsupported file type `{ext_big}`. Supported: .py .java .js .c")
        st.stop()

    big_code  = big_uploaded.getvalue().decode('utf-8', errors='ignore')
    big_lines = big_code.count('\n') + 1

    if not run_big_btn:
        st.markdown("""<div class="section-header"><i class="ti ti-file-code"></i> Source Code</div>""", unsafe_allow_html=True)
        fi1, fi2, fi3 = st.columns(3)
        with fi1: st.markdown(f"""<div class="metric-card"><div class="metric-value" style="font-size:1.1rem;word-break:break-all;">{big_uploaded.name}</div><div class="metric-label"><i class="ti ti-file"></i> File</div></div>""", unsafe_allow_html=True)
        with fi2: st.markdown(f"""<div class="metric-card"><div class="metric-value">{lang_big}</div><div class="metric-label"><i class="ti ti-code"></i> Language</div></div>""", unsafe_allow_html=True)
        with fi3: st.markdown(f"""<div class="metric-card"><div class="metric-value">{big_lines}</div><div class="metric-label"><i class="ti ti-list-numbers"></i> Lines</div></div>""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.code(big_code, language=lang_big or "text", line_numbers=True)
        st.stop()

    import tempfile
    _tmp_big = tempfile.NamedTemporaryFile(delete=False, suffix=ext_big, mode='w', encoding='utf-8')
    _tmp_big.write(big_code)
    _tmp_big.close()
    big_file_path = _tmp_big.name
    _big_tmp_cleanup = True

    st.markdown(f'''<div class="section-header">
        <i class="ti ti-binary-tree-2"></i> Chunked Audit &mdash;
        <span style="font-weight:400;font-size:0.85rem;">{big_uploaded.name}</span>
    </div>''', unsafe_allow_html=True)

    m1, m2, m3 = st.columns(3)
    with m1: st.markdown(f"""<div class="metric-card"><div class="metric-value">{big_lines}</div><div class="metric-label"><i class="ti ti-list-numbers"></i> Total Lines</div></div>""", unsafe_allow_html=True)
    with m2: st.markdown(f"""<div class="metric-card"><div class="metric-value">{lang_big.capitalize()}</div><div class="metric-label"><i class="ti ti-code"></i> Language</div></div>""", unsafe_allow_html=True)
    with m3: st.markdown(f"""<div class="metric-card"><div class="metric-value">Chunked</div><div class="metric-label"><i class="ti ti-cut"></i> Mode</div></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    prog_ph   = st.empty()
    status_ph = st.empty()

    try:
        from main_big import chunk_file, analyze_chunk, meta_summarize
        from src.vuln_classifier import deduplicate_findings
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading

        inference_big = load_inference_engine()
        _completed_count = [0]
        _progress_lock = threading.Lock()

        with measure_energy(sample_interval_s=0.2) as col_big:
            col_big.begin_phase("Chunking")
            with st.spinner("Chunking file and initialising NLP..."):
                chunks = chunk_file(big_file_path)
            col_big.begin_phase("Chunk Analysis (4 threads)")

            status_ph.markdown(
                f"<small style='color:var(--ink-muted);'>Processing <b style='color:var(--ink);'>{len(chunks)} chunks</b> "
                f"across <b style='color:var(--ink);'>4 parallel threads</b>...</small>",
                unsafe_allow_html=True
            )
            chunk_results = [None] * len(chunks)

            def _analyze_and_track(idx, cname, ctext, start_line):
                return idx, analyze_chunk(cname, ctext, lang_big, inference_big, start_line)

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(_analyze_and_track, idx, cname, ctext, start_line): (idx, cname)
                    for idx, (cname, ctext, start_line) in enumerate(chunks)
                }
                for future in as_completed(futures):
                    idx, cname = futures[future]
                    _, cr = future.result()
                    chunk_results[idx] = cr
                    _completed_count[0] += 1
                    prog_ph.progress(
                        _completed_count[0] / len(chunks),
                        text=f"Chunk {_completed_count[0]}/{len(chunks)} done — {cname}"
                    )

            prog_ph.progress(1.0, text="Meta-Transformer pass...")
            col_big.begin_phase("Meta-Transformer")
            with st.spinner("Meta-Transformer assembling global summary..."):
                meta_sum = meta_summarize(chunk_results, inference_big, lang_big)
            col_big.end_phase()

        prog_ph.empty()
        status_ph.empty()

        reports_dir_big = os.path.join(os.path.dirname(__file__), "frontend", "public", "reports")
        os.makedirs(reports_dir_big, exist_ok=True)
        with open(os.path.join(reports_dir_big, "latest_report.json"), "w") as _f:
            json.dump(col_big.report.to_dict(), _f)

        top_score = max(cr['risk_score'] for cr in chunk_results) if chunk_results else 0.0
        render_gauge(top_score)

        st.markdown('''<div class="section-header"><i class="ti ti-message-2"></i> Meta-Transformer Summary</div>''', unsafe_allow_html=True)
        st.markdown(f'<div class="summary-box">{meta_sum}</div>', unsafe_allow_html=True)

        all_findings = []
        for cr in chunk_results:
            all_findings.extend(cr.get('findings', []))
        all_findings = deduplicate_findings(all_findings)
        all_findings.sort(key=lambda f: f.get('line', 0))

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('''<div class="section-header"><i class="ti ti-alert-triangle"></i> Consolidated Vulnerabilities
            <span style="font-weight:400;font-size:0.78rem;color:var(--ink-muted);margin-left:8px;">(original file line numbers, deduplicated)</span>
        </div>''', unsafe_allow_html=True)

        if all_findings:
            sev_counts = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
            from src.vuln_classifier import normalize_severity
            for f in all_findings:
                norm_sev = normalize_severity(f.get('severity', 'INFO')).upper()
                sev_counts[norm_sev] = sev_counts.get(norm_sev, 0) + 1
            vc1, vc2, vc3, vc4 = st.columns(4)
            with vc1: st.markdown(f"""<div class="metric-card"><div class="metric-value">{len(all_findings)}</div><div class="metric-label">Total</div></div>""", unsafe_allow_html=True)
            with vc2: st.markdown(f"""<div class="metric-card"><div class="metric-value" style="color:var(--danger);">{sev_counts.get('HIGH',0)}</div><div class="metric-label">High</div></div>""", unsafe_allow_html=True)
            with vc3: st.markdown(f"""<div class="metric-card"><div class="metric-value" style="color:var(--warning);">{sev_counts.get('MEDIUM',0)}</div><div class="metric-label">Medium</div></div>""", unsafe_allow_html=True)
            with vc4: st.markdown(f"""<div class="metric-card"><div class="metric-value" style="color:var(--accent);">{sev_counts.get('LOW',0)}</div><div class="metric-label">Low</div></div>""", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            for fnd in all_findings:
                chunk_src = fnd.get('original_chunk', '')
                chunk_badge = (f" <span style='font-size:0.68rem;color:var(--ink-muted);font-family:var(--mono);'>chunk: {chunk_src}</span>" if chunk_src else "")
                sev = normalize_severity(fnd.get('severity', 'INFO')).upper()
                icon = severity_icon_html(sev)
                hdr_color = sev_color(sev)
                st.markdown(f"""
                <div class="finding-card finding-{sev}">
                    <div class="finding-header" style="color:{hdr_color};">{icon} {sev} VULNERABILITY{chunk_badge}</div>
                    <div class="finding-msg">{fnd.get('message', '')}</div>
                    <div class="finding-line"><i class="ti ti-code" style="margin-right:4px;"></i>Line {fnd.get('line', '?')}</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""<div class="finding-card finding-LOW">
                <div class="finding-header" style="color:var(--accent);"><i class="ti ti-circle-check"></i> CLEAN</div>
                <div class="finding-msg">No vulnerabilities detected across any chunks.</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('''<div class="section-header"><i class="ti ti-layout-list"></i> Per-Chunk Breakdown</div>''', unsafe_allow_html=True)
        for cr in chunk_results:
            n_findings = len(cr.get('findings', []))
            with st.expander(f"{cr['name']}   |   Score: {cr['risk_score']}/10   |   {n_findings} finding(s)"):
                st.markdown(f"<div class='summary-box' style='margin-bottom:12px;'>{cr['summary']}</div>", unsafe_allow_html=True)
                if cr.get('findings'):
                    for fnd in cr['findings']:
                        render_finding(fnd)
                else:
                    st.markdown("<small style='color:var(--ink-muted);'>No findings in this chunk.</small>", unsafe_allow_html=True)
                feats = cr.get('features', {})
                fa2, fb2 = st.columns(2)
                with fa2:
                    st.markdown("<div style='font-size:0.78rem;font-weight:600;color:var(--ink-muted);margin-bottom:4px;'><i class='ti ti-database-import'></i> Sources</div>", unsafe_allow_html=True)
                    render_tags(feats.get('sources', []), 'source')
                with fb2:
                    st.markdown("<div style='font-size:0.78rem;font-weight:600;color:var(--ink-muted);margin-bottom:4px;'><i class='ti ti-skull'></i> Sinks</div>", unsafe_allow_html=True)
                    render_tags(feats.get('sinks', []), 'sink')

    except Exception as e:
        prog_ph.empty()
        status_ph.empty()
        st.error(f"Large file pipeline error: {e}")
    finally:
        try:
            if _big_tmp_cleanup:
                os.unlink(big_file_path)
        except Exception:
            pass

    st.markdown("<br>", unsafe_allow_html=True)
    st.link_button("Open Advanced Analytics (React Frontend)", "http://localhost:5173", use_container_width=True)
    st.stop()


# ═══════════════════════════════════════════════════
# SINGLE FILE AUDIT — FULL-WIDTH UNIFIED STREAM (NO WASTED SPACE)
# ═══════════════════════════════════════════════════
elif uploaded_file:
    code_content = uploaded_file.getvalue().decode("utf-8", errors="ignore")
    ext      = os.path.splitext(uploaded_file.name)[1].lower()
    lang_map = {'.py': 'python', '.java': 'java', '.js': 'javascript', '.c': 'c'}
    language = lang_map.get(ext)
    lines    = code_content.count('\n') + 1

    if not language:
        st.error(f"Unsupported file type: `{ext}`. Supported languages: Python (.py), Java (.java), JavaScript (.js), C (.c)")
        st.stop()

    # Session reset when a new/different file is uploaded
    audit_file_key = f"audit_{uploaded_file.name}_{lines}"
    if st.session_state.get('current_audit_key') != audit_file_key:
        st.session_state['current_audit_key'] = audit_file_key
        st.session_state.pop('audit_results', None)
        st.session_state.pop('original_audit', None)
        st.session_state.pop('verification_result', None)
        st.session_state.pop('modified_code', None)
        st.session_state.pop('editor_code', None)
        st.session_state.pop('current_findings', None)
        st.session_state.pop('edit_mode', None)
        st.session_state.pop('active_view', None)

    inference = load_inference_engine()

    current_code = st.session_state.get('editor_code', code_content)
    cur_lines    = current_code.count('\n') + 1
    has_audit    = 'audit_results' in st.session_state
    has_verif    = 'verification_result' in st.session_state
    in_edit      = st.session_state.get('edit_mode', False)
    active_view  = st.session_state.get('active_view', 'verification' if has_verif else 'audit')

    # Workflow Progress Banner (Full-Width)
    wf_stage = (
        "edit" if in_edit else
        "verified" if active_view == 'verification' and has_verif else
        "learn" if has_audit else
        "analyze"
    )
    render_workflow(wf_stage)

    # ──────────────────────────────────────────────────────────
    # SECTION 1: SOURCE CODE & IN-BROWSER EDITOR (FULL-WIDTH)
    # ──────────────────────────────────────────────────────────
    is_edited = ('editor_code' in st.session_state and st.session_state['editor_code'] != code_content)
    title_suffix = " — Modified" if is_edited else ""
    render_stage_header(1, "ti-file-code", "Source Code",
                        f"{uploaded_file.name} · {language} · {cur_lines} lines{title_suffix}")

    # Determine findings to highlight on source lines:
    if active_view == 'verification' and 'current_findings' in st.session_state:
        display_findings = st.session_state['current_findings']
    elif 'original_audit' in st.session_state:
        display_findings = st.session_state['original_audit'].get('findings', [])
    elif 'audit_results' in st.session_state:
        display_findings = st.session_state['audit_results'].get('findings', [])
    else:
        display_findings = []

    if in_edit:
        # Build vulnerability line chips for reference in tab-bar
        vuln_lines = sorted({f.get('line', 0) for f in display_findings if f.get('line', 0) > 0})
        sev_map = {}
        for f in display_findings:
            ln = f.get('line', 0)
            sv = f.get('severity', 'LOW').upper()
            if ln > 0:
                if ln not in sev_map or {'HIGH': 2, 'MEDIUM': 1, 'LOW': 0}.get(sv, 0) > {'HIGH': 2, 'MEDIUM': 1, 'LOW': 0}.get(sev_map[ln], 0):
                    sev_map[ln] = sv

        ref_chips = ""
        for ln in vuln_lines[:18]:
            sv = sev_map.get(ln, 'LOW')
            color_map = {'HIGH': '#cf222e', 'MEDIUM': '#9a6700', 'LOW': '#0969da'}
            bg_map    = {'HIGH': '#ffebe9', 'MEDIUM': '#fff8c5', 'LOW': '#ddf4ff'}
            c  = color_map.get(sv, '#0969da')
            bg = bg_map.get(sv, '#ddf4ff')
            ref_chips += (
                f'<span style="background:{bg};border:1px solid {c}66;border-radius:3px;'
                f'padding:1px 7px;font-size:0.71rem;font-family:monospace;color:{c};font-weight:700;'
                f'display:inline-block;margin-right:3px;">L{ln}</span>'
            )
        if len(vuln_lines) > 18:
            ref_chips += f'<span style="font-size:0.71rem;color:#8c959f;">+{len(vuln_lines)-18} more</span>'
        chips_html = ref_chips if ref_chips else '<span style="font-size:0.72rem;color:#1a7f37;font-weight:600;">✓ No flagged lines</span>'

        # ── Code Panel Tab Bar ──
        st.markdown(f"""
        <div class="code-panel" style="border-bottom:0;border-radius:var(--radius) var(--radius) 0 0;margin-bottom:0;">
          <div class="code-panel-bar">
            <div style="display:flex;align-items:center;gap:10px;">
              <span class="code-panel-lang" style="background:#fff8c5;border-color:#9a670066;color:#9a6700;">
                ✏ EDITING
              </span>
              <span style="color:#656d76;font-size:0.8rem;font-weight:500;">{uploaded_file.name}</span>
              <span class="ed-live-count" style="color:#adb5bd;font-size:0.75rem;">· {cur_lines} lines</span>
            </div>
            <div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap;">
              <span style="font-size:0.71rem;color:#8c959f;margin-right:4px;">Flagged:</span>
              {chips_html}
            </div>
          </div>
        </div>""", unsafe_allow_html=True)

        # ── Textarea (value captured by Streamlit) ──
        # Fixed-size editor: always shows 25 lines, longer code scrolls inside the box.
        _VISIBLE_LINES = 25                              # keep in sync with --code-lines in the CSS
        _ta_height = round(_VISIBLE_LINES * 22.4 + 24)   # 22.4px per line + 24px vertical padding
        edited_text = st.text_area(
            label="code_editor",
            value=current_code,
            height=_ta_height,
            key="code_editor_area",
            label_visibility="collapsed"
        )
        st.session_state['editor_code'] = edited_text

        # ── JS: line-number gutter (scrolls with the code, recounts on every keystroke/paste) ──
        from src.vuln_classifier import normalize_severity as _norm_sev
        _sev_json = json.dumps({str(k): _norm_sev(v).upper() for k, v in sev_map.items()})
        _gutter_js = r"""<script>
(function () {
  var SEV = __SEV_JSON__;
  var COLORS = { HIGH: ['#cf222e', '#ffebe9'], MEDIUM: ['#9a6700', '#fff8c5'], LOW: ['#0969da', '#ddf4ff'] };
  var PAD_TOP = 6, GUTTER_W = 56;
  var pdoc;
  try { pdoc = window.parent.document; } catch (err) { return; }
  var pwin = window.parent;
  var current = null;

  function findTA() {
    var ta = pdoc.querySelector('textarea[aria-label="code_editor"]');
    if (ta) return ta;
    var all = pdoc.querySelectorAll('[data-testid="stTextArea"] textarea');
    return all.length ? all[all.length - 1] : null;
  }

  function detach() {
    if (current && current.ta && current.ta.__lnCleanup) {
      try { current.ta.__lnCleanup(); } catch (e) {}
    }
    current = null;
  }

  function attach(ta) {
    var host = ta.parentElement;
    var stale = host.querySelectorAll('.ln-gutter-x');
    for (var i = 0; i < stale.length; i++) stale[i].parentNode.removeChild(stale[i]);
    if (ta.__lnCleanup) { try { ta.__lnCleanup(); } catch (e) {} }

    host.style.position = 'relative';
    var g = pdoc.createElement('div');
    g.className = 'ln-gutter-x';
    g.style.cssText = 'position:absolute;z-index:2;overflow:hidden;box-sizing:border-box;' +
      'width:' + GUTTER_W + 'px;background:#f8f9fa;border-right:1px solid #e4e7eb;' +
      'text-align:right;pointer-events:none;user-select:none;';
    var inner = pdoc.createElement('div');
    inner.style.paddingTop = PAD_TOP + 'px';
    g.appendChild(inner);
    host.appendChild(g);
    ta.setAttribute('wrap', 'off');

    function onScroll() { inner.style.transform = 'translateY(' + (-ta.scrollTop) + 'px)'; }
    ta.addEventListener('scroll', onScroll);
    ta.addEventListener('input', refresh);
    ta.__lnCleanup = function () {
      ta.removeEventListener('scroll', onScroll);
      ta.removeEventListener('input', refresh);
      if (g.parentNode) g.parentNode.removeChild(g);
      ta.__lnCleanup = null;
    };

    current = { ta: ta, g: g, inner: inner, n: -1, lh: 0 };
    refresh();
  }

  function refresh() {
    var s = current;
    if (!s) return;
    var ta = s.ta;
    if (!ta.isConnected) { detach(); return; }

    var cs = pwin.getComputedStyle(ta);
    var lh = parseFloat(cs.lineHeight);
    if (isNaN(lh)) lh = 22.4;
    var n = (ta.value || '').split('\n').length;

    if (n !== s.n || lh !== s.lh) {
      var html = '';
      for (var i = 1; i <= n; i++) {
        var c = '#adb5bd', bg = 'transparent', fw = 400;
        var sv = SEV[String(i)];
        if (sv && COLORS[sv]) { c = COLORS[sv][0]; bg = COLORS[sv][1]; fw = 600; }
        html += '<div style="height:' + lh + 'px;line-height:' + lh + 'px;padding-right:10px;' +
                'color:' + c + ';background:' + bg + ';font-weight:' + fw + ';">' + i + '</div>';
      }
      s.inner.innerHTML = html;
      s.n = n;
      s.lh = lh;
      var labels = pdoc.querySelectorAll('.ed-live-count');
      for (var k = 0; k < labels.length; k++) labels[k].textContent = '\u00B7 ' + n + ' lines';
    }
    s.g.style.fontFamily = cs.fontFamily;
    s.g.style.fontSize = cs.fontSize;
    s.g.style.top = ta.offsetTop + 'px';
    s.g.style.left = ta.offsetLeft + 'px';
    s.g.style.height = ta.clientHeight + 'px';
    s.inner.style.transform = 'translateY(' + (-ta.scrollTop) + 'px)';
  }

  function tick() {
    var ta = findTA();
    if (!ta) return;
    if (!current || current.ta !== ta || !current.g.isConnected) attach(ta);
    else refresh();
  }

  tick();
  var timer = setInterval(tick, 250);
  window.addEventListener('unload', function () { clearInterval(timer); detach(); });
})();
</script>"""
        st_components.html(_gutter_js.replace('__SEV_JSON__', _sev_json), height=0, scrolling=False)

        # ── Action buttons ──
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        btn_c1, btn_c2 = st.columns([3, 1])
        with btn_c1:
            re_audit_clicked = st.button("🔍 Re-Audit & Verify Fix", type="primary", use_container_width=True, key="btn_reaudit")
        with btn_c2:
            cancel_clicked = st.button("✕ Cancel Edit", use_container_width=True, key="btn_cancel_edit")

        if cancel_clicked:
            st.session_state['edit_mode'] = False
            st.rerun()

        if re_audit_clicked:
            scan_code  = st.session_state.get('editor_code', code_content)
            orig_audit = st.session_state.get('original_audit')

            if not orig_audit:
                st.error("Baseline audit missing. Please run the initial audit first.")
                st.stop()

            with st.spinner("Re-auditing edited code against baseline..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext, mode='w', encoding='utf-8') as tmp:
                    tmp.write(scan_code)
                    tmp_path = tmp.name

                try:
                    scanner = Scanner()
                    new_findings, new_risk_score = scanner.scan_file(tmp_path)
                finally:
                    try: os.unlink(tmp_path)
                    except: pass

                from src.agent_tools import match_findings
                verif_result = match_findings(orig_audit['findings'], new_findings)
                verif_result['verification_risk_score'] = new_risk_score

                st.session_state['verification_result'] = verif_result
                st.session_state['current_findings']   = new_findings
                st.session_state['editor_code']        = scan_code
                st.session_state['active_view']        = 'verification'
                st.session_state['edit_mode']          = False
                st.rerun()

    else:
        # Normal Highlighted Code Viewer
        render_highlighted_code(current_code, display_findings, language)

        # Single clean button row beneath the code — NO DUPLICATE BUTTONS!
        st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
        if not has_audit:
            run_initial_btn = st.button("🔍 Run Full Security Audit", type="primary", use_container_width=True, key="btn_initial_audit")
            if run_initial_btn:
                steps = [
                    ("ti-binary-tree",   "AST Parsing & Feature Extraction"),
                    ("ti-shield-search", "Security Scanner (Semgrep + Fallback)"),
                    ("ti-brain",         "Loading CodeT5 Model"),
                    ("ti-pencil",        "Prompt Engineering"),
                    ("ti-message-2",     "Generating AI Summary"),
                ]
                pipeline_ph = st.empty()

                def render_pipeline(done_up_to: int):
                    html = ""
                    for i, (icon, name) in enumerate(steps):
                        if i < done_up_to:
                            cls  = "step-done"
                            stat = '<i class="ti ti-circle-check"></i> Done'
                        elif i == done_up_to:
                            cls  = "step-run"
                            stat = '<i class="ti ti-loader-2"></i> Running...'
                        else:
                            cls  = "step-wait"
                            stat = '<i class="ti ti-minus"></i>'
                        html += (
                            f'<div class="pipeline-step {cls}">'
                            f'<i class="ti {icon} ti-step"></i>{name}'
                            f'<span class="step-status">{stat}</span>'
                            f'</div>'
                        )
                    pipeline_ph.markdown(html, unsafe_allow_html=True)

                fresh = {}
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext, mode='w', encoding='utf-8') as tmp:
                    tmp.write(code_content)
                    tmp_path = tmp.name

                try:
                    with measure_energy(sample_interval_s=0.2) as col:
                        render_pipeline(0)
                        col.begin_phase("AST & Features")
                        ast_parser        = ASTParser()
                        feature_extractor = FeatureExtractor()
                        tree     = ast_parser.parse(code_content, language)
                        features = feature_extractor.extract_features(tree, code_content, language)
                        features['lang']       = language
                        features['line_count'] = code_content.count('\n') + 1
                        fresh['features'] = features
                        col.end_phase()

                        render_pipeline(1)
                        col.begin_phase("Semgrep Scan")
                        scanner = Scanner()
                        findings, risk_score = scanner.scan_file(tmp_path)
                        fresh['findings']   = findings
                        fresh['risk_score'] = risk_score
                        col.end_phase()

                        render_pipeline(2)
                        col.begin_phase("Model Prep")
                        col.end_phase()

                        render_pipeline(3)
                        col.begin_phase("Prompt Engine")
                        enricher = PromptEnricher()
                        prompt   = enricher.construct_prompt(findings, features, code_content)
                        col.end_phase()

                        render_pipeline(4)
                        col.begin_phase("CodeT5 Gen")
                        summary = inference.generate_summary(prompt)
                        summary = PromptEnricher.enrich_summary(summary, features)
                        fresh['summary'] = summary
                        col.end_phase()

                        render_pipeline(5)
                        time.sleep(0.3)
                        pipeline_ph.empty()

                    reports_dir = os.path.join(os.path.dirname(__file__), "frontend", "public", "reports")
                    os.makedirs(reports_dir, exist_ok=True)
                    with open(os.path.join(reports_dir, "latest_report.json"), "w") as f:
                        json.dump(col.report.to_dict(), f)

                except Exception as e:
                    pipeline_ph.empty()
                    st.error(f"Pipeline error: {e}")
                    st.stop()
                finally:
                    try: os.unlink(tmp_path)
                    except: pass

                st.session_state['audit_results'] = fresh
                st.session_state['original_audit'] = {
                    'source':     code_content,
                    'language':   language,
                    'findings':   fresh['findings'],
                    'risk_score': fresh['risk_score'],
                }
                st.session_state['current_findings'] = fresh['findings']
                st.session_state['editor_code']      = code_content
                st.session_state['active_view']      = 'audit'
                st.session_state['edit_mode']        = False
                st.session_state.pop('verification_result', None)
                st.rerun()

        else:
            # Audit has been performed
            act_cols = st.columns([1, 1] if is_edited else [1])
            with act_cols[0]:
                if st.button("✏️ Edit Code In-Browser", type="primary", use_container_width=True, key="btn_trigger_edit"):
                    st.session_state['edit_mode']   = True
                    st.session_state['editor_code'] = current_code
                    st.rerun()
            if is_edited and len(act_cols) > 1:
                with act_cols[1]:
                    if st.button("↺ Reset Code to Original", use_container_width=True, key="btn_reset_to_orig"):
                        st.session_state['editor_code'] = code_content
                        st.session_state.pop('verification_result', None)
                        st.session_state.pop('current_findings', None)
                        st.session_state['active_view'] = 'audit'
                        st.rerun()

    # ──────────────────────────────────────────────────────────
    # SECTION 2: RESULTS AREA (FULL-WIDTH — ZERO WASTED SPACE)
    # ──────────────────────────────────────────────────────────
    if not has_audit:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align:center;padding:50px 20px;color:var(--ink-muted);background:var(--surface);border:1px solid var(--border-light);border-radius:var(--radius);">
            <i class="ti ti-bolt" style="font-size:3rem;display:block;margin-bottom:14px;color:var(--accent);"></i>
            <div style="font-size:1.1rem;font-weight:700;color:var(--ink);">Ready to Audit</div>
            <div style="font-size:0.88rem;margin-top:6px;">Click <b>Run Full Security Audit</b> above to analyze vulnerabilities and begin the learning session.</div>
        </div>""", unsafe_allow_html=True)

    elif active_view == 'verification' and has_verif:
        # ══════════════════════════════════════════════════════════
        # ONLY THE VERIFICATION REPORT IS DISPLAYED WHEN RE-AUDITED
        # ══════════════════════════════════════════════════════════
        verif_result  = st.session_state['verification_result']
        orig_audit    = st.session_state.get('original_audit', {})
        orig_findings = orig_audit.get('findings', [])

        from src.vuln_classifier import classify_vulnerability, normalize_severity as _nsev

        st.markdown("<br>", unsafe_allow_html=True)
        render_stage_header(5, "ti-pencil-check", "Fix Verification Report",
                            f"Comparison against baseline ({len(orig_findings)} original finding{'s' if len(orig_findings) != 1 else ''})")

        overall    = verif_result.get('overall_outcome', '')
        resolved_n = verif_result.get('resolved_count', 0)
        still_n    = verif_result.get('still_present_count', 0)
        new_n      = verif_result.get('new_issue_count', 0)
        verif_risk = verif_result.get('verification_risk_score', 0.0)

        # Overall Outcome Banner
        if overall == 'ALL_RESOLVED' and new_n == 0:
            st.success(
                f"🎉 **All {resolved_n} original vulnerability(ies) resolved!** "
                "Your edited code passed the re-audit with no security issues detected."
            )
        elif overall == 'ALL_RESOLVED' and new_n > 0:
            st.warning(
                f"⚠️ All {resolved_n} original vulnerability(ies) resolved, but your edit introduced "
                f"**{new_n} new issue(s)**. Review the new findings below."
            )
        elif overall in ('STILL_PRESENT', 'STILL_PRESENT_WITH_NEW_ISSUES'):
            extra = f" Additionally, **{new_n} new issue(s)** were introduced." if new_n else ""
            st.error(
                f"⚠️ **{still_n}** original vulnerability(ies) still detected in your edited code.{extra} "
                "Lines that remain vulnerable are highlighted in red/yellow in the code viewer above."
            )

        # 4 Full-Width Metric Cards
        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value" style="color:var(--success);">{resolved_n}</div>
                <div class="metric-label"><i class="ti ti-circle-check"></i> Resolved</div>
            </div>""", unsafe_allow_html=True)
        with sc2:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value" style="color:var(--warning);">{still_n}</div>
                <div class="metric-label"><i class="ti ti-alert-triangle"></i> Still Present</div>
            </div>""", unsafe_allow_html=True)
        with sc3:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value" style="color:var(--danger);">{new_n}</div>
                <div class="metric-label"><i class="ti ti-shield-x"></i> New Issues</div>
            </div>""", unsafe_allow_html=True)
        with sc4:
            vrisk_color = risk_color(verif_risk)
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value" style="color:{vrisk_color};">{verif_risk}/10</div>
                <div class="metric-label"><i class="ti ti-shield-half-filled"></i> New Risk Score</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### Detailed Breakdown by Vulnerability")

        # Per-original finding status cards
        for per in verif_result.get('per_original_status', []):
            status = per['status']
            orig_f = per['original_finding']
            msg    = orig_f.get('message', '')
            cwe, category = classify_vulnerability(msg)
            sev    = _nsev(orig_f.get('severity', 'INFO')).upper()

            if status == 'RESOLVED':
                badge_cls = "resolved"
                badge_txt = "RESOLVED"
                badge_ico = "ti-circle-check"
            else:
                badge_cls = "still-present"
                badge_txt = "STILL PRESENT"
                badge_ico = "ti-alert-triangle"

            with st.container(border=True):
                st.markdown(f"""
                <div class="verif-status-row">
                    <span class="verif-badge {badge_cls}"><i class="ti {badge_ico}"></i> {badge_txt}</span>
                    <span class="tag tag-{sev}">{sev}</span>
                    <span class="tag">{cwe}</span>
                    <span class="tag">{category}</span>
                </div>""", unsafe_allow_html=True)

                st.markdown(f"**Original finding:** {msg}")
                st.caption(per.get('explanation', ''))

                if status == 'RESOLVED':
                    st.success("✅ Fixed! This vulnerability is no longer detected in your edited code.")

                elif status == 'STILL_PRESENT':
                    matched_f = per.get('matched_finding') or {}
                    if matched_f:
                        st.warning(f"Still detected at line **{matched_f.get('line', '?')}** in your edited code.")
                        if matched_f.get('snippet'):
                            st.code(matched_f['snippet'], language=language)

                    try:
                        from src.agent_tools import SecureCodingAgent
                        _agent    = SecureCodingAgent()
                        _analysis = _agent.analyze_finding(
                            matched_f if matched_f else orig_f,
                            current_code,
                            language,
                        )
                        _exp = _analysis['explanation']
                        _tch = _analysis['teaching']
                        with st.expander("📖 Mentor Guidance — why is it still vulnerable?"):
                            st.markdown("**What is still wrong?**")
                            st.markdown(_exp['what_is_wrong'])
                            st.markdown("**Why is it still vulnerable?**")
                            st.markdown(_exp['why_is_it_vulnerable'])
                            st.markdown(f"**Secure Coding Principle:** `{_tch['principle']}`")
                            st.info(f"💡 **Beginner Takeaway:** {_tch['beginner_takeaway']}")
                    except Exception:
                        pass

        # New issues introduced
        if verif_result.get('new_issues'):
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("##### 🚨 New Issues Introduced by Your Edit")
            st.markdown("""<div style="font-size:0.85rem;color:var(--ink-muted);margin-bottom:10px;">
                These issues were not present in the original file. Fix them before your code can be considered secure.
            </div>""", unsafe_allow_html=True)
            for ni in verif_result['new_issues']:
                ni_f   = ni['finding']
                ni_msg = ni_f.get('message', '')
                ni_cwe, ni_cat = classify_vulnerability(ni_msg)
                ni_sev = _nsev(ni_f.get('severity', 'INFO')).upper()
                with st.container(border=True):
                    st.markdown(f"""
                    <div class="verif-status-row">
                        <span class="verif-badge new-issue"><i class="ti ti-shield-x"></i> NEW ISSUE</span>
                        <span class="tag tag-{ni_sev}">{ni_sev}</span>
                        <span class="tag">{ni_cwe}</span>
                        <span class="tag">{ni_cat}</span>
                        <span class="tag"><i class="ti ti-code"></i> Line {ni_f.get('line', '?')}</span>
                    </div>""", unsafe_allow_html=True)
                    st.markdown(f"**{ni_msg}**")
                    if ni_f.get('snippet'):
                        st.code(ni_f['snippet'], language=language)

        # Toggle to view initial lessons if desired
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("👁️ View Initial Baseline Audit & Lessons", use_container_width=True, key="btn_view_initial_audit"):
            st.session_state['active_view'] = 'audit'
            st.rerun()

    else:
        # ══════════════════════════════════════════════════════════
        # INITIAL AUDIT VIEW (FULL-WIDTH STREAM)
        # ══════════════════════════════════════════════════════════
        results = st.session_state['audit_results']

        if has_verif:
            st.markdown("""
            <div style="background:var(--surface);border:1px solid var(--accent);border-radius:var(--radius);padding:14px 20px;margin-bottom:16px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;">
                <div>
                    <i class="ti ti-info-circle" style="color:var(--accent);margin-right:6px;"></i>
                    <strong>Fix Verification Active:</strong> You previously verified edits to this code.
                </div>
            </div>""", unsafe_allow_html=True)
            if st.button("🔍 Return to Fix Verification Report", type="primary", use_container_width=True, key="btn_return_verif"):
                st.session_state['active_view'] = 'verification'
                st.rerun()

        # Baseline Banner
        n_findings = len(results.get('findings', []))
        st.markdown(f"""
        <div class="baseline-banner">
            <i class="ti ti-database-check"></i>
            <span>
                <strong>Baseline Established:</strong> {n_findings} finding(s) detected in
                <strong>{uploaded_file.name}</strong>. Click <b>Edit Code In-Browser</b> above to fix them and re-audit.
            </span>
        </div>""", unsafe_allow_html=True)

        # Risk Gauge + Metrics in a balanced horizontal row
        g_col1, g_col2 = st.columns([1, 2])
        with g_col1:
            render_gauge(results['risk_score'], "Baseline Risk Score")
        with g_col2:
            from src.vuln_classifier import normalize_severity, classify_vulnerability
            sev_counts = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
            for f in results['findings']:
                s = normalize_severity(f.get('severity', 'INFO')).upper()
                sev_counts[s] = sev_counts.get(s, 0) + 1

            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            m1, m2 = st.columns(2)
            with m1:
                st.markdown(f"""<div class="metric-card"><div class="metric-value">{len(results['findings'])}</div><div class="metric-label">Total Findings</div></div>""", unsafe_allow_html=True)
            with m2:
                st.markdown(f"""<div class="metric-card"><div class="metric-value" style="color:var(--danger);">{sev_counts.get('HIGH',0)}</div><div class="metric-label">High Severity</div></div>""", unsafe_allow_html=True)
            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            m3, m4 = st.columns(2)
            with m3:
                st.markdown(f"""<div class="metric-card"><div class="metric-value" style="color:var(--warning);">{sev_counts.get('MEDIUM',0)}</div><div class="metric-label">Medium Severity</div></div>""", unsafe_allow_html=True)
            with m4:
                st.markdown(f"""<div class="metric-card"><div class="metric-value" style="color:var(--accent);">{sev_counts.get('LOW',0)}</div><div class="metric-label">Low Severity</div></div>""", unsafe_allow_html=True)

        # STAGE 2 — UNDERSTAND (three cards side by side)
        st.markdown("<br>", unsafe_allow_html=True)
        render_stage_header(2, "ti-book", "Understand", "AI-generated analysis — program behavior, logic and key components")

        # ── Helper: convert summary body to clean HTML with bullet squares ──
        import re as _re
        import html as _html

        def _render_body(body_text, accent_color):
            """
            Convert raw summary body (may contain - bullets and `backtick` code) to HTML.
            Bullets → colored square marker.
            `code` → inline code badge.
            Plain lines → paragraph text.
            """
            def _inline_code(text):
                # Replace `...` with a styled inline code span
                return _re.sub(
                    r'`([^`]+)`',
                    lambda m: (
                        f'<code style="background:#f0f2f5;border:1px solid #d0d7de;border-radius:3px;'
                        f'padding:1px 5px;font-size:0.82rem;font-family:monospace;color:#24292f;">'
                        f'{_html.escape(m.group(1))}</code>'
                    ),
                    text
                )

            lines = body_text.strip().splitlines()
            html_parts = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith(('-', '*', '•')):
                    item = line.lstrip('-*•').strip()
                    # Handle "— " em-dash separator (func — description)
                    if ' \u2014 ' in item:
                        fn_part, desc_part = item.split(' \u2014 ', 1)
                        item_html = _inline_code(fn_part) + f' <span style="color:#8c959f;">—</span> ' + _inline_code(desc_part)
                    else:
                        item_html = _inline_code(item)
                    html_parts.append(
                        f'<div style="display:flex;align-items:flex-start;gap:10px;'
                        f'margin-bottom:10px;padding:7px 10px;background:#f8f9fa;'
                        f'border-radius:6px;border-left:3px solid {accent_color}20;">'
                        f'<span style="width:7px;height:7px;min-width:7px;border-radius:1px;'
                        f'background:{accent_color};margin-top:5px;flex-shrink:0;'
                        f'display:inline-block;"></span>'
                        f'<span style="font-size:0.875rem;line-height:1.6;color:#24292f;">'
                        f'{item_html}</span>'
                        f'</div>'
                    )
                else:
                    html_parts.append(
                        f'<p style="font-size:0.9rem;line-height:1.65;color:#24292f;'
                        f'margin:0 0 10px 0;">{_inline_code(_html.escape(line))}</p>'
                    )
            return ''.join(html_parts) if html_parts else (
                '<span style="color:#8c959f;font-style:italic;font-size:0.87rem;">Not available</span>'
            )

        # ── Parse the three ### sections ──
        raw_summary = results.get('summary', '')
        section_pattern = _re.compile(r'###\s+(.+?)(?=\n###|\Z)', _re.DOTALL)
        parsed = {}
        for s in section_pattern.findall(raw_summary):
            lines_s = s.strip().splitlines()
            if lines_s:
                title = lines_s[0].strip()
                body  = '\n'.join(lines_s[1:]).strip()
                parsed[title] = body

        # Card config: (section_name, icon, accent_color, bg_color)
        card_cfg = [
            ('Overview',      'ti-layout-dashboard', '#0969da', '#ddf4ff'),
            ('Key Behavior',  'ti-activity',         '#9a6700', '#fff8c5'),
            ('Key Functions', 'ti-code',             '#1a7f37', '#dafbe1'),
        ]

        col_u1, col_u2, col_u3 = st.columns(3, gap="small")
        for col, (section_name, icon_cls, accent, hdr_bg) in zip(
                [col_u1, col_u2, col_u3], card_cfg):
            body_text  = parsed.get(section_name, '')
            body_html  = _render_body(body_text, accent)
            with col:
                st.markdown(f"""
                <div style="background:#ffffff;border:1px solid #d0d7de;
                            border-top:3px solid {accent};
                            border-radius:8px;padding:0;
                            box-shadow:0 2px 6px rgba(27,31,36,0.10);
                            height:100%;">
                  <!-- Card Header -->
                  <div style="display:flex;align-items:center;gap:9px;
                              padding:12px 16px;background:{hdr_bg};
                              border-bottom:1px solid #d0d7de;
                              border-radius:5px 5px 0 0;">
                    <span style="width:28px;height:28px;border-radius:6px;
                                 background:#ffffff;border:1px solid {accent}44;
                                 display:inline-flex;align-items:center;
                                 justify-content:center;flex-shrink:0;">
                      <i class="ti {icon_cls}" style="color:{accent};font-size:0.95rem;"></i>
                    </span>
                    <span style="font-size:0.78rem;font-weight:700;
                                 text-transform:uppercase;letter-spacing:1.2px;
                                 color:{accent};">{section_name}</span>
                  </div>
                  <!-- Card Body -->
                  <div style="padding:14px 14px 12px 14px;">
                    {body_html}
                  </div>
                </div>""", unsafe_allow_html=True)

        # STAGE 3 — LEARN
        st.markdown("<br>", unsafe_allow_html=True)
        render_stage_header(3, "ti-school", "Learn", "Security findings — understand what is wrong and why")

        if results['findings']:
            st.markdown("""
            <div style="font-size:0.88rem;color:var(--ink-muted);margin-bottom:16px;">
                <i class="ti ti-arrow-up" style="color:var(--accent);"></i>
                Highlighted lines in the code viewer above show detected vulnerabilities.
                Review the explanations below, then use <strong>Edit Code In-Browser</strong> above to fix them.
            </div>""", unsafe_allow_html=True)

            for f in results['findings']:
                render_finding(f)

            from src.agent_tools import SecureCodingAgent
            agent    = SecureCodingAgent()
            analyses = agent.analyze_all_findings(results['findings'], code_content, language)

            for i, item in enumerate(analyses):
                ctx = item['context']
                exp = item['explanation']
                tch = item['teaching']
                sc  = sev_color(ctx['severity'])

                with st.container(border=True):
                    st.markdown(f"""
                    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;
                                margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid var(--border-light);">
                        <div style="font-weight:700;font-size:1.05rem;color:var(--ink);">
                            <i class="ti ti-shield-alert" style="color:{sc};margin-right:6px;"></i>
                            <span style="color:var(--accent);">Finding #{i+1}:</span> {ctx['category']}
                        </div>
                        <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
                            <span class="tag tag-{ctx['severity']}">{ctx['severity']}</span>
                            <span class="tag">{ctx['cwe']}</span>
                            <span class="tag"><i class="ti ti-code"></i> Line {ctx['line']}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown(f"**{ctx['message']}**")

                    surrounding  = ctx.get('surrounding_code', {})
                    snippet_text = surrounding.get('snippet', '')
                    if snippet_text:
                        st.code(snippet_text, language=language)
                    elif ctx.get('snippet'):
                        st.code(f"> Line {ctx['line']} | {ctx['snippet']}", language=language)

                    st.markdown("**What is wrong?**")
                    st.markdown(exp['what_is_wrong'])
                    st.markdown("**Why is it vulnerable?**")
                    st.markdown(exp['why_is_it_vulnerable'])

                    st.markdown(f"""
                    <div style="background:var(--accent-bg);border:1px solid var(--accent-rim);border-radius:var(--radius);
                                padding:14px 18px;margin:12px 0;">
                        <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:1px;
                                    color:var(--accent);margin-bottom:6px;">
                            <i class="ti ti-school"></i> Learn This Concept
                        </div>
                        <div style="font-weight:700;color:var(--ink);margin-bottom:4px;">{tch['concept_name']}</div>
                        <div style="font-size:0.9rem;color:var(--ink-2);">{tch['what_to_learn']}</div>
                    </div>""", unsafe_allow_html=True)
                    st.markdown(f"**Secure Coding Principle:** `{tch['principle']}`")
                    st.info(f"💡 **Beginner Takeaway:** {tch['beginner_takeaway']}")
        else:
            st.markdown("""<div class="finding-card finding-LOW">
                <div class="finding-header" style="color:var(--success);">
                    <i class="ti ti-shield-check"></i> ALL CHECKS PASSED
                </div>
                <div class="finding-msg">No vulnerabilities detected. The code passed all security checks.</div>
            </div>""", unsafe_allow_html=True)

        # AST Features (Collapsible)
        with st.expander("Technical Details — AST Feature Extraction", expanded=False):
            feat = results['features']
            fa, fb = st.columns(2)
            with fa:
                st.markdown("<div style='font-size:0.8rem;font-weight:600;color:var(--ink-muted);margin-bottom:4px;'><i class='ti ti-database-import'></i> Data Sources</div>", unsafe_allow_html=True)
                render_tags(feat.get('sources', []), "source")
            with fb:
                st.markdown("<div style='font-size:0.8rem;font-weight:600;color:var(--ink-muted);margin-bottom:4px;'><i class='ti ti-skull'></i> Dangerous Sinks</div>", unsafe_allow_html=True)
                render_tags(feat.get('sinks', []), "sink")
            complexity = feat.get('complexity', 0)
            st.markdown(f"""
            <div class="metric-card" style="margin-top:12px;text-align:left;display:flex;align-items:center;gap:16px;">
                <i class="ti ti-git-branch" style="font-size:1.8rem;color:var(--accent);flex-shrink:0;"></i>
                <div>
                    <div style="font-size:0.7rem;color:var(--ink-muted);text-transform:uppercase;letter-spacing:1px;">Cyclomatic Complexity</div>
                    <div style="font-size:1.8rem;font-weight:800;color:var(--ink);">{complexity}</div>
                </div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.link_button("Open Advanced Analytics (React Frontend)", "http://localhost:5173", use_container_width=True)