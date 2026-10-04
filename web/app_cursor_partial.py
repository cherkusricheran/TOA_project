import os
import sys
import re
import html as html_mod
import difflib
import torch
import tempfile
import time
import json
import hashlib

if hasattr(torch, 'classes'):
    torch.classes.__path__ = [os.path.join(torch.__path__[0], torch.classes.__file__)]

import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ast_parser import ASTParser
from src.feature_extractor import FeatureExtractor
from src.scanner import Scanner
from src.enrichment import PromptEnricher
from src.inference import InferenceEngine
from web.energy_monitor import measure_energy

st.set_page_config(
    page_title="SecureLearn — Secure Coding Learning",
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
:root {
    --bg:          #F8FAFC;
    --surface:     #FFFFFF;
    --border:      #E2E8F0;
    --border-soft: #F1F5F9;
    --accent:      #3B82F6;
    --accent-bg:   #EFF6FF;
    --accent-rim:  #BFDBFE;
    --danger:      #EF4444;
    --danger-bg:   #FEF2F2;
    --warning:     #F59E0B;
    --warning-bg:  #FFFBEB;
    --success:     #22C55E;
    --success-bg:  #F0FDF4;
    --success-rim: #BBF7D0;
    --ink:         #0F172A;
    --ink-2:       #334155;
    --ink-muted:   #64748B;
    --ink-faint:   #94A3B8;
    --mono: ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
    --sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    --radius: 8px;
    --shadow-sm: 0 1px 3px rgba(15,23,42,.06), 0 1px 2px rgba(15,23,42,.04);
}

html, body { font-family: var(--sans); }
.stApp { background-color: var(--bg); }
.block-container { padding-top: 1.25rem; padding-bottom: 3rem; max-width: min(1600px, 96vw); }
#MainMenu, footer, header { visibility: hidden; }

.stMarkdown p, .stMarkdown span, .stMarkdown li,
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 { color: var(--ink); }
.stTextInput > label > div > p,
.stSelectbox  > label > div > p { color: var(--ink); }

.stTextInput input {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); color: var(--ink);
}
.stCodeBlock {
    border-radius: var(--radius); border: 1px solid var(--border);
    max-height: 420px; overflow: auto;
}

details > summary p { color: var(--ink); font-weight: 600; }

[data-testid="stTabs"] [role="tab"] { color: var(--ink-muted); font-weight: 600; font-size: 0.88rem; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] { color: var(--ink); border-bottom: 2px solid var(--accent); }

[data-testid="stBaseButton-primary"] button {
    background: var(--accent); color: #fff; font-weight: 600;
    border: none; border-radius: var(--radius); padding: 0.5rem 1.4rem;
}
[data-testid="stBaseButton-secondary"] button {
    background: var(--surface); color: var(--ink); border: 1px solid var(--border);
    border-radius: var(--radius); font-weight: 600;
}
[data-testid="stLinkButton"] a {
    background: var(--surface); color: var(--ink); border: 1px solid var(--border);
    border-radius: var(--radius); font-weight: 600; font-size: 0.82rem;
}

[data-testid="stMetricValue"] { color: var(--ink); }
[data-testid="stFileUploadDropzone"] {
    background: #1E2130; border: 2px dashed #3D4560; border-radius: var(--radius);
}
[data-testid="stFileUploadDropzone"] * { color: #CBD5E1; }

section[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--border); }
.sb-section-title {
    font-size: 0.65rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1.6px; color: var(--ink-muted);
    margin: 14px 0 6px 0; padding-bottom: 4px; border-bottom: 1px solid var(--border);
}
.sb-lang-row { display: flex; flex-wrap: wrap; gap: 6px; }
.sb-lang {
    background: var(--bg); border: 1px solid var(--border); border-radius: 6px;
    padding: 3px 8px; font-size: 0.75rem; color: var(--ink);
}
.model-pill {
    background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 8px 10px; font-family: var(--mono); font-size: 0.72rem; color: var(--ink);
    word-break: break-all;
}

.app-header {
    display: flex; align-items: baseline; justify-content: space-between;
    gap: 16px; flex-wrap: wrap;
    padding: 8px 0 18px 0; margin-bottom: 16px;
    border-bottom: 1px solid var(--border);
}
.app-title { font-size: 3rem; font-weight: 800; color: var(--ink); letter-spacing: -1.2px; margin: 0; }
.app-title i { color: var(--accent); margin-right: 8px; }
.app-sub { font-size: 0.82rem; color: var(--ink-muted); margin: 0; }

.stepper {
    display: flex; align-items: center; gap: 0; margin: 0 0 20px 0;
    border: 1px solid var(--border); border-radius: var(--radius);
    background: var(--surface); overflow: hidden;
}
.stepper-item {
    flex: 1; text-align: center; padding: 7px 4px;
    font-size: 0.68rem; font-weight: 700; letter-spacing: 0.4px;
    text-transform: uppercase; color: var(--ink-faint);
    border-right: 1px solid var(--border);
}
.stepper-item:last-child { border-right: none; }
.stepper-item.is-done { color: var(--accent); background: var(--accent-bg); }
.stepper-item.is-active { color: var(--ink); background: var(--bg); box-shadow: inset 0 -2px 0 var(--accent); }
.stepper-item.is-verify { color: #166534; background: var(--success-bg); }

.stage {
    margin: 22px 0 10px 0; padding-bottom: 6px;
    border-bottom: 1px solid var(--border);
    display: flex; align-items: baseline; gap: 10px;
}
.stage-num {
    font-size: 0.68rem; font-weight: 800; color: var(--accent);
    background: var(--accent-bg); border: 1px solid var(--accent-rim);
    border-radius: 99px; padding: 2px 8px; letter-spacing: 0.4px;
}
.stage-title { font-size: 0.95rem; font-weight: 750; color: var(--ink); }
.stage-sub { font-size: 0.78rem; color: var(--ink-muted); margin-left: auto; }

.meta-row {
    display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
    margin: 0 0 12px 0; font-size: 0.8rem; color: var(--ink-2);
}
.meta-chip {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 6px; padding: 3px 9px; font-family: var(--mono); font-size: 0.75rem;
}

.overview-bar {
    display: flex; flex-wrap: wrap; gap: 10px; align-items: stretch;
    margin: 8px 0 6px 0;
}
.overview-risk {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 12px 16px; min-width: 180px;
}
.overview-risk .score { font-size: 1.7rem; font-weight: 800; font-family: var(--mono); line-height: 1; }
.overview-risk .lbl { font-size: 0.68rem; color: var(--ink-muted); text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }
.overview-counts { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }

.sev-badge {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: 0.68rem; font-weight: 800; letter-spacing: 0.5px;
    padding: 2px 8px; border-radius: 99px; border: 1px solid transparent;
}
.sev-HIGH { background: var(--danger-bg); color: var(--danger); border-color: #FECACA; }
.sev-MEDIUM { background: var(--warning-bg); color: #92400E; border-color: #FDE68A; }
.sev-LOW { background: var(--success-bg); color: #166534; border-color: var(--success-rim); }
.count-pill {
    background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
    padding: 6px 10px; font-size: 0.78rem; color: var(--ink-2);
}
.count-pill b { font-family: var(--mono); }

.find-row {
    display: flex; align-items: flex-start; gap: 10px;
    padding: 8px 0; border-bottom: 1px solid var(--border-soft);
    font-size: 0.88rem;
}
.find-row .msg { color: var(--ink); }
.find-row .meta { font-family: var(--mono); font-size: 0.72rem; color: var(--ink-muted); }

.lesson-head {
    display: flex; justify-content: space-between; align-items: center;
    gap: 8px; flex-wrap: wrap; margin-bottom: 8px; padding-bottom: 10px;
    border-bottom: 1px solid var(--border);
}
.lesson-title { font-weight: 750; font-size: 0.98rem; color: var(--ink); }
.lesson-q { font-size: 0.78rem; font-weight: 750; color: var(--ink-muted); text-transform: uppercase; letter-spacing: 0.6px; margin: 14px 0 4px 0; }
.learn-note {
    background: var(--accent-bg); border-left: 3px solid var(--accent);
    padding: 10px 12px; margin: 8px 0; font-size: 0.9rem; color: var(--ink-2);
}
.ref-note { font-size: 0.78rem; color: var(--ink-muted); margin: 4px 0 10px 0; }
.code-kicker {
    font-size: 0.7rem; font-weight: 750; text-transform: uppercase; letter-spacing: 0.6px;
    margin: 8px 0 4px 0;
}
.code-kicker.orig { color: var(--danger); }
.code-kicker.suggested { color: #166534; }
.code-kicker.user { color: #166534; }

.diff-wrap {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 10px 12px;
    font-family: var(--mono); font-size: 0.78rem; line-height: 1.55;
    max-height: 260px; overflow: auto; color: var(--ink-2);
}
.diff-add { background: #ECFDF5; color: #166534; display: block; padding: 0 4px; }
.diff-rem { background: #FEF2F2; color: #991B1B; text-decoration: line-through; display: block; padding: 0 4px; }
.diff-ctx { color: var(--ink-faint); display: block; padding: 0 4px; }

.verif-stage {
    margin-top: 28px; padding-top: 8px; border-top: 2px solid var(--border);
}
.legend-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 14px 0; font-size: 0.78rem; color: var(--ink-muted); }
.verif-badge {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 3px 9px; border-radius: 99px; font-size: 0.72rem; font-weight: 750;
}
.verif-badge.resolved { background: var(--success-bg); color: #166534; border: 1px solid var(--success-rim); }
.verif-badge.still-present { background: var(--warning-bg); color: #78350F; border: 1px solid #FCD34D; }
.verif-badge.new-issue { background: var(--danger-bg); color: var(--danger); border: 1px solid #FECACA; }

.metric-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 14px 16px; text-align: center;
}
.metric-value { font-size: 1.6rem; font-weight: 800; line-height: 1; color: var(--ink); }
.metric-label { font-size: 0.7rem; color: var(--ink-muted); text-transform: uppercase; letter-spacing: 1px; margin-top: 5px; }

.finding-card {
    border-radius: var(--radius); padding: 12px 14px; margin-bottom: 8px;
    background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--border);
}
.finding-HIGH { border-left-color: var(--danger); }
.finding-MEDIUM { border-left-color: var(--warning); }
.finding-LOW { border-left-color: var(--success); }
.finding-header { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 1px; font-weight: 700; margin-bottom: 4px; }
.finding-msg { font-size: 0.88rem; color: var(--ink); }
.finding-line { font-size: 0.74rem; color: var(--ink-muted); margin-top: 4px; font-family: var(--mono); }

.tag-container { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.tag {
    background: var(--surface); border: 1px solid var(--border); color: var(--ink);
    border-radius: 6px; padding: 3px 10px; font-size: 0.78rem; font-family: var(--mono);
}
.tag.sink { border-color: var(--danger); color: var(--danger); }
.tag.none { color: var(--ink-faint); }
.tag-HIGH { background: var(--danger-bg); color: var(--danger); border: none; font-weight: 700; }
.tag-MEDIUM { background: var(--warning-bg); color: #92400e; border: none; font-weight: 700; }
.tag-LOW { background: var(--success-bg); color: #166534; border: none; font-weight: 700; }

.section-header {
    font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1.2px;
    color: var(--ink); padding: 0 0 6px 0; border-bottom: 1px solid var(--border);
    margin: 16px 0 12px 0;
}
.summary-box {
    background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 14px 16px; font-size: 0.92rem; line-height: 1.6; color: var(--ink);
}
.gauge-container {
    background: var(--surface); border-radius: var(--radius); border: 1px solid var(--border);
    padding: 16px; text-align: center; margin-bottom: 12px;
}
.gauge-label { font-size: 0.7rem; color: var(--ink-muted); text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 6px; }
.gauge-score { font-size: 2.4rem; font-weight: 800; line-height: 1; font-family: var(--mono); }
.gauge-score-denom { font-size: 1.1rem; color: var(--ink-faint); }
.gauge-bar-bg { background: var(--bg); border-radius: 99px; height: 8px; margin: 10px 0 4px 0; overflow: hidden; border: 1px solid var(--border); }
.gauge-bar-fill { height: 100%; border-radius: 99px; }
.gauge-range { font-size: 0.7rem; color: var(--ink-muted); }

.ti { vertical-align: -0.125em; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def load_inference_engine():
    return InferenceEngine()


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
    return {"HIGH": "var(--danger)", "MEDIUM": "var(--warning)", "LOW": "var(--success)"}.get(sev, "var(--ink-muted)")


def severity_icon_html(sev: str) -> str:
    icons = {
        "HIGH":   '<i class="ti ti-circle-x"></i>',
        "MEDIUM": '<i class="ti ti-alert-triangle"></i>',
        "LOW":    '<i class="ti ti-info-circle"></i>',
    }
    return icons.get(sev.upper(), '<i class="ti ti-circle"></i>')


def sev_badge_html(sev: str) -> str:
    s = (sev or "LOW").upper()
    if s not in ("HIGH", "MEDIUM", "LOW"):
        s = "LOW"
    return f'<span class="sev-badge sev-{s}">{s}</span>'


def render_gauge(score: float):
    color = risk_color(score)
    label = risk_label(score)
    pct   = int((score / 10.0) * 100)
    st.markdown(f"""
    <div class="gauge-container">
        <div class="gauge-label">Baseline Risk Score</div>
        <div class="gauge-score" style="color:{color};">{score}<span class="gauge-score-denom">/10</span></div>
        <div style="font-size:0.75rem;font-weight:700;letter-spacing:1.5px;color:{color};margin-top:4px;">{label}</div>
        <div class="gauge-bar-bg">
            <div class="gauge-bar-fill" style="width:{pct}%;background-color:{color};"></div>
        </div>
        <div class="gauge-range">0 — Safe &nbsp;&nbsp; 10 — Critical</div>
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
        <div class="finding-header" style="color:{hdr_color};">{icon} {sev}</div>
        <div class="finding-msg">{msg}</div>
        <div class="finding-line">Line {line}</div>
    </div>""", unsafe_allow_html=True)


def render_tags(items: list, kind: str = "source"):
    if not items:
        st.markdown('<div class="tag-container"><span class="tag none">none detected</span></div>', unsafe_allow_html=True)
        return
    tags_html = "".join(f'<span class="tag {kind}">{x}</span>' for x in set(items))
    st.markdown(f'<div class="tag-container">{tags_html}</div>', unsafe_allow_html=True)


def render_stepper(stage: str):
    stages = [
        ("analyze", "Analyze"),
        ("understand", "Understand"),
        ("learn", "Learn"),
        ("generate", "Generate"),
        ("write", "Write"),
        ("verify", "Verify"),
    ]
    order = {name: i for i, (name, _) in enumerate(stages)}
    active_idx = order.get(stage, 0)
    html = '<div class="stepper">'
    for idx, (key, name) in enumerate(stages):
        if idx < active_idx:
            cls = "stepper-item is-done"
        elif idx == active_idx:
            cls = "stepper-item is-verify" if key == "verify" else "stepper-item is-active"
        else:
            cls = "stepper-item"
        html += f'<div class="{cls}">{name}</div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_stage(num: int, title: str, subtitle: str = ""):
    sub = f'<span class="stage-sub">{subtitle}</span>' if subtitle else ""
    st.markdown(f"""
    <div class="stage">
        <span class="stage-num">{num}</span>
        <span class="stage-title">{title}</span>
        {sub}
    </div>""", unsafe_allow_html=True)


def split_summary_sections(summary: str) -> dict:
    sections = {"Overview": "", "Key Behavior": "", "Key Functions": ""}
    current = None
    for line in (summary or "").splitlines():
        m = re.match(r'^###\s+(Overview|Key Behavior|Key Functions)\s*$', line.strip())
        if m:
            current = m.group(1)
            continue
        if current:
            sections[current] += line + "\n"
    for key in sections:
        sections[key] = sections[key].strip()
    if not any(sections.values()) and (summary or "").strip():
        sections["Overview"] = summary.strip()
    return sections


def compute_diff_html(orig: str, new: str, lang: str) -> str:
    orig_lines = orig.splitlines()
    new_lines  = new.splitlines()
    diff = list(difflib.unified_diff(orig_lines, new_lines, lineterm='', n=2))
    if not diff:
        return "<em style='color:var(--ink-muted);font-size:0.82rem;'>No textual differences detected.</em>"

    rows = []
    for line in diff:
        if line.startswith('---') or line.startswith('+++') or line.startswith('@@'):
            continue
        if line.startswith('+'):
            rows.append(f'<span class="diff-add">+ {html_mod.escape(line[1:])}</span>')
        elif line.startswith('-'):
            rows.append(f'<span class="diff-rem">- {html_mod.escape(line[1:])}</span>')
        else:
            body = html_mod.escape(line[1:] if len(line) > 0 else "")
            rows.append(f'<span class="diff-ctx">  {body}</span>')
    if not rows:
        return "<em style='color:var(--ink-muted);font-size:0.82rem;'>No textual differences detected.</em>"
    return f'<div class="diff-wrap">{"".join(rows)}</div>'


# ═══════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style="font-size:1rem;font-weight:800;color:var(--ink);padding-bottom:10px;border-bottom:1px solid var(--border);">
        SecureLearn
    </div>
    <div class="sb-section-title">Languages</div>
    <div class="sb-lang-row">
        <span class="sb-lang">Python</span>
        <span class="sb-lang">Java</span>
        <span class="sb-lang">JS</span>
        <span class="sb-lang">C</span>
    </div>
    <div class="sb-section-title">Model</div>
    <div class="model-pill">Salesforce/codet5-base-multi-sum</div>
    <div class="sb-section-title">Scanner</div>
    <div style="font-size:0.8rem;color:var(--ink-2);">Semgrep + AST/Regex fallback</div>
    <div class="sb-section-title">Analytics</div>
    """, unsafe_allow_html=True)
    st.link_button("React visualisation", "http://localhost:5173", use_container_width=True)
    st.markdown("""
    <div style="margin-top:20px;padding-top:12px;border-top:1px solid var(--border);font-size:0.7rem;color:var(--ink-muted);">
        SecureLearn v2.0
    </div>
    """, unsafe_allow_html=True)


st.markdown("""
<div class="app-header">
    <div>
        <p class="app-title"><i class="ti ti-shield-lock"></i>SecureLearn</p>
    </div>
    <p class="app-sub">AI-Assisted Secure Coding Learning &amp; Verification System</p>
</div>
""", unsafe_allow_html=True)


tab_file, tab_dir, tab_big = st.tabs(["Single File Audit", "Directory Bulk Scan", "Large File Audit"])
uploaded_file = None
dir_path_input = ""
big_file_path  = ""
run_big_btn    = False

with tab_file:
    uploaded_file = st.file_uploader(
        "Upload source code to start the learning baseline",
        type=['py', 'java', 'c', 'js'],
        help="Supported: .py .java .c .js"
    )

with tab_big:
    st.caption("Files over 200 lines are chunked, scanned in parallel, then summarised.")
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
    st.markdown(
        '<p style="color:var(--ink-muted);font-size:0.9rem;margin-top:8px;">'
        'Upload a file to analyze vulnerabilities, understand the code, learn the security principle, '
        'generate a secure reference, then write and verify your own fix.'
        '</p>',
        unsafe_allow_html=True,
    )
    render_stepper("analyze")
    st.stop()


# ═══════════════════════════════════════════════════
# DIRECTORY SCAN
# ═══════════════════════════════════════════════════
if run_btn or demo_btn:
    if run_btn and not os.path.isdir(dir_path_input):
        st.error("Directory not found or path empty! Please provide a valid absolute directory path.")
        st.stop()

    st.markdown('''<div class="section-header">Directory Scan</div>''', unsafe_allow_html=True)

    from main_folder import bulk_semgrep_scan, analyze_all_files, build_project_map
    inference = load_inference_engine()

    pipeline_ph = st.empty()

    if demo_btn:
        pipeline_ph.markdown("Loading directory demo data…")
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
        pipeline_ph.markdown("Running bulk directory scan…")
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

    st.markdown('''<div class="section-header">Directory Pipeline Results</div>''', unsafe_allow_html=True)

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
    with c4: st.markdown(f"""<div class="metric-card"><div class="metric-value" style="color:var(--success);">{total_counts['LOW']}</div><div class="metric-label">Low Severity</div></div>""", unsafe_allow_html=True)

    st.markdown('''<div class="section-header">Project AI Overview</div>''', unsafe_allow_html=True)

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

    st.markdown('''<div class="section-header">Top 5 Riskiest Files</div>''', unsafe_allow_html=True)
    ranked_risk = sorted([r for r in results_arr if 'error' not in r], key=lambda x: x.get('risk_score', 0), reverse=True)
    for r in ranked_risk[:5]:
        rel_path = os.path.relpath(r['file'], dir_path_input)
        sev = "HIGH" if r.get('risk_score',0) >= 8 else "MEDIUM" if r.get('risk_score',0) >= 5 else "LOW"
        st.markdown(f"""
        <div class="finding-card finding-{sev}">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:600; font-size:0.9rem; color:var(--ink);">{rel_path}</span>
                <span style="font-family:var(--mono); font-weight:800; font-size:1rem; color:var(--ink);">{r.get('risk_score',0)}/10</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

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
        st.markdown("""<div class="section-header">Source Code</div>""", unsafe_allow_html=True)
        fi1, fi2, fi3 = st.columns(3)
        with fi1: st.markdown(f"""<div class="metric-card"><div class="metric-value" style="font-size:1.1rem;word-break:break-all;">{big_uploaded.name}</div><div class="metric-label">File</div></div>""", unsafe_allow_html=True)
        with fi2: st.markdown(f"""<div class="metric-card"><div class="metric-value">{lang_big}</div><div class="metric-label">Language</div></div>""", unsafe_allow_html=True)
        with fi3: st.markdown(f"""<div class="metric-card"><div class="metric-value">{big_lines}</div><div class="metric-label">Lines</div></div>""", unsafe_allow_html=True)
        st.code(big_code, language=lang_big or "text", line_numbers=True)
        st.info("Click **Run Chunked Audit** in the Large File tab above.")
        st.stop()

    _tmp_big = tempfile.NamedTemporaryFile(delete=False, suffix=ext_big, mode='w', encoding='utf-8')
    _tmp_big.write(big_code)
    _tmp_big.close()
    big_file_path = _tmp_big.name
    _big_tmp_cleanup = True

    st.markdown(f'''<div class="section-header">Chunked Audit — {big_uploaded.name}</div>''', unsafe_allow_html=True)

    m1, m2, m3 = st.columns(3)
    with m1: st.markdown(f"""<div class="metric-card"><div class="metric-value">{big_lines}</div><div class="metric-label">Total Lines</div></div>""", unsafe_allow_html=True)
    with m2: st.markdown(f"""<div class="metric-card"><div class="metric-value">{lang_big.capitalize()}</div><div class="metric-label">Language</div></div>""", unsafe_allow_html=True)
    with m3: st.markdown(f"""<div class="metric-card"><div class="metric-value">Chunked</div><div class="metric-label">Mode</div></div>""", unsafe_allow_html=True)

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
                f"<small style='color:var(--ink-muted);'>Processing <b>{len(chunks)} chunks</b> across 4 threads…</small>",
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

        st.markdown('''<div class="section-header">Meta-Transformer Summary</div>''', unsafe_allow_html=True)
        st.markdown(f'<div class="summary-box">{meta_sum}</div>', unsafe_allow_html=True)

        all_findings = []
        for cr in chunk_results:
            all_findings.extend(cr.get('findings', []))
        all_findings = deduplicate_findings(all_findings)
        all_findings.sort(key=lambda f: f.get('line', 0))

        st.markdown('''<div class="section-header">Consolidated Vulnerabilities</div>''', unsafe_allow_html=True)

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
            with vc4: st.markdown(f"""<div class="metric-card"><div class="metric-value" style="color:var(--success);">{sev_counts.get('LOW',0)}</div><div class="metric-label">Low</div></div>""", unsafe_allow_html=True)
            for fnd in all_findings:
                chunk_src = fnd.get('original_chunk', '')
                chunk_badge = (f" <span style='font-size:0.68rem;color:var(--ink-muted);font-family:var(--mono);'>chunk: {chunk_src}</span>" if chunk_src else "")
                sev = normalize_severity(fnd.get('severity', 'INFO')).upper()
                icon = severity_icon_html(sev)
                hdr_color = sev_color(sev)
                st.markdown(f"""
                <div class="finding-card finding-{sev}">
                    <div class="finding-header" style="color:{hdr_color};">{icon} {sev}{chunk_badge}</div>
                    <div class="finding-msg">{fnd.get('message', '')}</div>
                    <div class="finding-line">Line {fnd.get('line', '?')}</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""<div class="finding-card finding-LOW">
                <div class="finding-header" style="color:var(--success);">CLEAN</div>
                <div class="finding-msg">No vulnerabilities detected across any chunks.</div>
            </div>""", unsafe_allow_html=True)

        st.markdown('''<div class="section-header">Per-Chunk Breakdown</div>''', unsafe_allow_html=True)
        for cr in chunk_results:
            n_findings = len(cr.get('findings', []))
            with st.expander(f"{cr['name']}   |   Score: {cr['risk_score']}/10   |   {n_findings} finding(s)"):
                st.markdown(f"<div class='summary-box' style='margin-bottom:12px;'>{cr['summary']}</div>", unsafe_allow_html=True)
                if cr.get('findings'):
                    for fnd in cr['findings']:
                        render_finding(fnd)
                else:
                    st.caption("No findings in this chunk.")
                feats = cr.get('features', {})
                fa2, fb2 = st.columns(2)
                with fa2:
                    st.markdown("<div style='font-size:0.78rem;font-weight:600;color:var(--ink-muted);margin-bottom:4px;'>Sources</div>", unsafe_allow_html=True)
                    render_tags(feats.get('sources', []), 'source')
                with fb2:
                    st.markdown("<div style='font-size:0.78rem;font-weight:600;color:var(--ink-muted);margin-bottom:4px;'>Sinks</div>", unsafe_allow_html=True)
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

    st.link_button("Open Advanced Analytics (React Frontend)", "http://localhost:5173", use_container_width=True)
    st.stop()


# ═══════════════════════════════════════════════════
# SINGLE FILE AUDIT
# ═══════════════════════════════════════════════════
elif uploaded_file:
    code_content = uploaded_file.getvalue().decode("utf-8", errors="ignore")
    ext      = os.path.splitext(uploaded_file.name)[1].lower()
    lang_map = {'.py': 'python', '.java': 'java', '.js': 'javascript', '.c': 'c'}
    language = lang_map.get(ext)
    lines    = code_content.count('\n') + 1

    file_digest = hashlib.sha1(code_content.encode("utf-8", errors="ignore")).hexdigest()[:12]
    audit_file_key = f"audit_{uploaded_file.name}_{file_digest}"
    if st.session_state.get('current_audit_key') != audit_file_key:
        st.session_state['current_audit_key'] = audit_file_key
        st.session_state.pop('audit_results', None)
        st.session_state.pop('original_audit', None)
        st.session_state.pop('verification_result', None)
        st.session_state.pop('modified_code', None)
        for k in list(st.session_state.keys()):
            if k.startswith('secure_fix_'):
                del st.session_state[k]

    inference = load_inference_engine()

    if not language:
        st.error(f"Unsupported file type: `{ext}`")
        st.stop()

    has_audit = 'audit_results' in st.session_state
    has_verif = 'verification_result' in st.session_state
    has_fix = any(str(k).startswith('secure_fix_') for k in st.session_state)
    has_modified = bool(st.session_state.get('modified_code'))
    if has_verif:
        wf_stage = "verify"
    elif has_modified:
        wf_stage = "write"
    elif has_fix:
        wf_stage = "generate"
    elif has_audit:
        wf_stage = "learn"
    else:
        wf_stage = "analyze"
    render_stepper(wf_stage)

    render_stage(1, "Analyze", f"{uploaded_file.name} · {language} · {lines} lines")
    st.markdown(f"""
    <div class="meta-row">
        <span class="meta-chip">{html_mod.escape(uploaded_file.name)}</span>
        <span class="meta-chip">{html_mod.escape(language)}</span>
        <span class="meta-chip">{lines} lines</span>
    </div>""", unsafe_allow_html=True)
    st.code(code_content, language=language or "text", line_numbers=True)

    run_btn_label = "Re-run Security Audit" if has_audit else "Run Full Security Audit"
    run_audit_btn = st.button(run_btn_label, type="primary", use_container_width=True)

    if has_audit:
        n_findings = len(st.session_state['audit_results'].get('findings', []))
        st.caption(f"Baseline established — {n_findings} finding(s). Re-run replaces the baseline.")

    if run_audit_btn:
        fresh = {}
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        try:
            with measure_energy(sample_interval_s=0.2) as col:
                with st.spinner("Running security audit…"):
                    col.begin_phase("AST & Features")
                    ast_parser        = ASTParser()
                    feature_extractor = FeatureExtractor()
                    tree     = ast_parser.parse(code_content, language)
                    features = feature_extractor.extract_features(tree, code_content, language)
                    features['lang']       = language
                    features['line_count'] = lines
                    fresh['features'] = features

                    col.end_phase()
                    col.begin_phase("Semgrep Scan")
                    scanner = Scanner()
                    findings, risk_score = scanner.scan_file(tmp_path)
                    fresh['findings']   = findings
                    fresh['risk_score'] = risk_score
                    col.end_phase()

                    col.begin_phase("Model Prep")
                    col.end_phase()

                    col.begin_phase("Prompt Engine")
                    enricher = PromptEnricher()
                    prompt   = enricher.construct_prompt(findings, features, code_content)
                    col.end_phase()

                    col.begin_phase("CodeT5 Gen")
                    summary = inference.generate_summary(prompt)
                    summary = PromptEnricher.enrich_summary(summary, features)
                    fresh['summary'] = summary
                    col.end_phase()

            reports_dir = os.path.join(os.path.dirname(__file__), "frontend", "public", "reports")
            os.makedirs(reports_dir, exist_ok=True)
            with open(os.path.join(reports_dir, "latest_report.json"), "w") as f:
                json.dump(col.report.to_dict(), f)

        except Exception as e:
            st.error(f"Pipeline error: {e}")
            st.stop()
        finally:
            try: os.unlink(tmp_path)
            except: pass

        st.session_state['audit_results'] = fresh
        st.session_state['original_audit'] = {
            'source':    code_content,
            'language':  language,
            'findings':  fresh['findings'],
            'risk_score': fresh['risk_score'],
        }
        for k in list(st.session_state.keys()):
            if k.startswith('secure_fix_'):
                del st.session_state[k]
        st.session_state.pop('verification_result', None)
        st.rerun()

    if 'audit_results' not in st.session_state:
        st.caption("Run the security audit to continue the learning path.")
        st.stop()

    results = st.session_state['audit_results']
    from src.vuln_classifier import normalize_severity, classify_vulnerability

    sev_counts = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
    for f in results['findings']:
        s = normalize_severity(f.get('severity', 'INFO')).upper()
        sev_counts[s] = sev_counts.get(s, 0) + 1
    score = results['risk_score']
    st.markdown(f"""
    <div class="overview-bar">
        <div class="overview-risk">
            <div class="score" style="color:{risk_color(score)};">{score}<span style="font-size:0.9rem;color:var(--ink-faint);">/10</span></div>
            <div class="lbl">{risk_label(score)} risk</div>
        </div>
        <div class="overview-counts">
            <span class="count-pill"><b>{len(results['findings'])}</b> findings</span>
            {sev_badge_html('HIGH')} <span class="count-pill">{sev_counts.get('HIGH', 0)}</span>
            {sev_badge_html('MEDIUM')} <span class="count-pill">{sev_counts.get('MEDIUM', 0)}</span>
            {sev_badge_html('LOW')} <span class="count-pill">{sev_counts.get('LOW', 0)}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    render_stage(2, "Understand", "What this program does")
    sections = split_summary_sections(results.get('summary', ''))
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown("**Overview**")
        st.markdown(sections["Overview"] or "_No overview available._")
    with col_b:
        st.markdown("**Key Behavior**")
        st.markdown(sections["Key Behavior"] or "_No key behavior available._")
    with col_c:
        st.markdown("**Key Functions**")
        st.markdown(sections["Key Functions"] or "_No key functions available._")

    render_stage(3, "Learn", "Each finding, then a secure reference when you are ready")

    if not results['findings']:
        st.success("No vulnerabilities detected. The Secure Coding Assistant activates when findings are present.")
    else:
        st.markdown("**Findings**")
        for f in results['findings']:
            sev = normalize_severity(f.get('severity', 'INFO')).upper()
            cwe, category = classify_vulnerability(f.get('message', ''))
            st.markdown(f"""
            <div class="find-row">
                {sev_badge_html(sev)}
                <div>
                    <div class="msg">{html_mod.escape(f.get('message', ''))}</div>
                    <div class="meta">{html_mod.escape(category)} · {html_mod.escape(cwe)} · Line {f.get('line', '?')}</div>
                </div>
            </div>""", unsafe_allow_html=True)

        from src.agent_tools import SecureCodingAgent
        agent    = SecureCodingAgent()
        analyses = agent.analyze_all_findings(results['findings'], code_content, language)

        for i, item in enumerate(analyses):
            ctx = item['context']
            exp = item['explanation']
            tch = item['teaching']
            btn_key = f"btn_gen_secure_{i}_{ctx['line']}"
            fix_key = f"secure_fix_{i}_{ctx['line']}"
            surrounding = ctx.get('surrounding_code', {})
            snippet_text = surrounding.get('snippet', '')

            with st.container(border=True):
                st.markdown(f"""
                <div class="lesson-head">
                    <div class="lesson-title">Finding {i+1}: {html_mod.escape(ctx['category'])}</div>
                    <div>{sev_badge_html(ctx['severity'])}
                        <span class="meta-chip">{html_mod.escape(str(ctx['cwe']))}</span>
                        <span class="meta-chip">Line {ctx['line']}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if snippet_text:
                    st.code(snippet_text, language=language)
                elif ctx.get('snippet'):
                    st.code(f"> Line {ctx['line']} | {ctx['snippet']}", language=language)

                st.markdown('<div class="lesson-q">What is wrong?</div>', unsafe_allow_html=True)
                st.markdown(exp['what_is_wrong'])

                st.markdown('<div class="lesson-q">Why is it vulnerable?</div>', unsafe_allow_html=True)
                st.markdown(exp['why_is_it_vulnerable'])

                st.markdown('<div class="lesson-q">What should I learn?</div>', unsafe_allow_html=True)
                st.markdown(f"""
                <div class="learn-note">
                    <strong>{html_mod.escape(tch['concept_name'])}</strong><br>
                    {html_mod.escape(tch['what_to_learn'])}
                </div>""", unsafe_allow_html=True)
                st.markdown(f"**Principle:** `{tch['principle']}`")
                st.markdown(f"**Beginner takeaway:** {tch['beginner_takeaway']}")

                st.markdown('<div class="lesson-q">Generate secure code</div>', unsafe_allow_html=True)
                st.markdown(
                    '<p class="ref-note">One reference implementation for this finding. It does not replace your original code and is not used for verification.</p>',
                    unsafe_allow_html=True,
                )

                if fix_key not in st.session_state:
                    if st.button("Generate Secure Code", key=btn_key, type="primary"):
                        with st.spinner("Generating secure reference…"):
                            fix_result = agent.generate_secure_fix(
                                item, code_content, language, inference_engine=inference
                            )
                            st.session_state[fix_key] = fix_result
                            st.rerun()

                if fix_key in st.session_state:
                    fix = st.session_state[fix_key]
                    orig_snip = snippet_text or ctx.get('snippet', '') or ""
                    gen_code  = fix.get('secure_code', '')

                    st.markdown("**AI Suggested Secure Code — reference only**")
                    st.markdown(
                        '<p class="ref-note">Original Vulnerable Code remains the baseline. User Modified Code is uploaded in Write &amp; Verify.</p>',
                        unsafe_allow_html=True,
                    )

                    orig_n = len(orig_snip.splitlines()) if orig_snip else 0
                    gen_n  = len(gen_code.splitlines()) if gen_code else 0
                    use_side_by_side = orig_snip and orig_n <= 18 and gen_n <= 18

                    if use_side_by_side:
                        col_orig, col_gen = st.columns(2, gap="medium")
                        with col_orig:
                            st.markdown('<div class="code-kicker orig">Original Vulnerable Code</div>', unsafe_allow_html=True)
                            st.code(orig_snip, language=language)
                        with col_gen:
                            st.markdown('<div class="code-kicker suggested">AI Suggested Secure Code</div>', unsafe_allow_html=True)
                            st.code(gen_code, language=language)
                    else:
                        if orig_snip:
                            st.markdown('<div class="code-kicker orig">Original Vulnerable Code</div>', unsafe_allow_html=True)
                            st.code(orig_snip, language=language)
                        st.markdown('<div class="code-kicker suggested">AI Suggested Secure Code</div>', unsafe_allow_html=True)
                        st.code(gen_code, language=language)

                    exp_col1, exp_col2 = st.columns(2, gap="medium")
                    with exp_col1:
                        st.markdown("**What changed**")
                        for change in fix.get('changes_made', []):
                            st.markdown(f"- {change}")
                    with exp_col2:
                        st.markdown("**Why this is safer**")
                        for reason in fix.get('why_secure', []):
                            st.markdown(f"- {reason}")

                    st.markdown('<div class="lesson-q">Diff</div>', unsafe_allow_html=True)
                    if orig_snip:
                        st.markdown(compute_diff_html(orig_snip, gen_code, language), unsafe_allow_html=True)
                    if fix.get('target_scope'):
                        st.caption(f"Scope: {fix['target_scope']}")
                    st.caption("Write your own fix in the Verify stage below. This reference is not submitted.")

    with st.expander("Technical details — AST feature extraction", expanded=False):
        f  = results['features']
        fa, fb = st.columns(2)
        with fa:
            st.caption("Data sources")
            render_tags(f.get('sources', []), "source")
        with fb:
            st.caption("Dangerous sinks")
            render_tags(f.get('sinks', []), "sink")
        st.caption(f"Cyclomatic complexity: {f.get('complexity', 0)}")

    original_audit = st.session_state.get('original_audit')
    if original_audit and original_audit.get('findings'):
        orig_lang     = original_audit['language']
        orig_findings = original_audit['findings']

        st.markdown('<div class="verif-stage"></div>', unsafe_allow_html=True)
        render_stage(5, "Write", "Your modified code — not the AI reference")
        st.markdown(
            f"Verification compares **your uploaded file** to the original baseline of "
            f"`{uploaded_file.name}` ({len(orig_findings)} finding(s)). "
            "AI Suggested Secure Code is not submitted."
        )
        st.markdown("""
        <div class="legend-row">
            <span><strong>1. Original Vulnerable Code</strong> — baseline</span>
            <span>·</span>
            <span><strong>2. AI Suggested Secure Code</strong> — reference only</span>
            <span>·</span>
            <span><strong>3. User Modified Code</strong> — verification input</span>
        </div>
        """, unsafe_allow_html=True)

        modified_file = st.file_uploader(
            "Upload your modified source file for verification",
            type=['py', 'java', 'c', 'js'],
            key="modified_uploader",
            help="This should be YOUR version of the fixed code, not the AI suggestion."
        )

        if modified_file is not None:
            modified_code = modified_file.getvalue().decode("utf-8", errors="ignore")
            st.session_state['modified_code'] = modified_code
            st.markdown('<div class="code-kicker user">User Modified Code</div>', unsafe_allow_html=True)
            st.code(modified_code, language=orig_lang, line_numbers=True)

            ext_map  = {'.py': 'python', '.js': 'javascript', '.java': 'java', '.c': 'c'}
            mod_ext  = os.path.splitext(modified_file.name)[1].lower()
            mod_lang = ext_map.get(mod_ext, orig_lang)
            if mod_lang != orig_lang:
                st.warning(
                    f"Original file was **{orig_lang}** but modified file appears to be **{mod_lang}**. "
                    f"Verification will use **{orig_lang}** for consistency."
                )
                mod_lang = orig_lang

            verify_btn = st.button("Verify My Fix", type="primary")

            if verify_btn:
                with st.spinner("Rescanning your modified code against the original baseline…"):
                    from src.agent_tools import verify_fix_pipeline
                    verif_result = verify_fix_pipeline(orig_findings, modified_code, orig_lang)
                    st.session_state['verification_result'] = verif_result

        verif_result = st.session_state.get('verification_result')
        if verif_result:
            render_stage(6, "Verify", "Results for your uploaded modified code")

            overall    = verif_result.get('overall_outcome', '')
            resolved_n = verif_result.get('resolved_count', 0)
            still_n    = verif_result.get('still_present_count', 0)
            new_n      = verif_result.get('new_issue_count', 0)
            verif_risk = verif_result.get('verification_risk_score', 0.0)

            sc1, sc2, sc3, sc4 = st.columns(4)
            with sc1:
                st.markdown(f"""<div class="metric-card">
                    <div class="metric-value" style="color:var(--success);">{resolved_n}</div>
                    <div class="metric-label">Resolved</div>
                </div>""", unsafe_allow_html=True)
            with sc2:
                st.markdown(f"""<div class="metric-card">
                    <div class="metric-value" style="color:var(--warning);">{still_n}</div>
                    <div class="metric-label">Still Present</div>
                </div>""", unsafe_allow_html=True)
            with sc3:
                st.markdown(f"""<div class="metric-card">
                    <div class="metric-value" style="color:var(--danger);">{new_n}</div>
                    <div class="metric-label">New Issues</div>
                </div>""", unsafe_allow_html=True)
            with sc4:
                st.markdown(f"""<div class="metric-card">
                    <div class="metric-value" style="color:{risk_color(verif_risk)};">{verif_risk}/10</div>
                    <div class="metric-label">Verification Risk</div>
                </div>""", unsafe_allow_html=True)

            for per in verif_result.get('per_original_status', []):
                status = per['status']
                orig_f = per['original_finding']
                msg    = orig_f.get('message', '')
                cwe, category = classify_vulnerability(msg)
                sev    = normalize_severity(orig_f.get('severity', 'INFO')).upper()

                if status == 'RESOLVED':
                    badge_cls, badge_txt = "resolved", "RESOLVED"
                else:
                    badge_cls, badge_txt = "still-present", "STILL PRESENT"

                with st.container(border=True):
                    st.markdown(f"""
                    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px;">
                        <span class="verif-badge {badge_cls}">{badge_txt}</span>
                        {sev_badge_html(sev)}
                        <span class="meta-chip">{html_mod.escape(cwe)}</span>
                        <span class="meta-chip">{html_mod.escape(category)}</span>
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown(f"**{msg}**")
                    st.caption(per['explanation'])

                    if status == 'RESOLVED':
                        st.success("Original vulnerability resolved. No matching security finding detected in your modified code.")
                    elif status == 'STILL_PRESENT':
                        matched_f = per.get('matched_finding') or {}
                        if matched_f:
                            st.warning(f"Still detected at line {matched_f.get('line', '?')} in your modified code.")
                            if matched_f.get('snippet'):
                                st.code(matched_f['snippet'], language=orig_lang)
                        try:
                            from src.agent_tools import SecureCodingAgent
                            _agent    = SecureCodingAgent()
                            _analysis = _agent.analyze_finding(
                                matched_f if matched_f else orig_f,
                                st.session_state.get('modified_code', ''),
                                orig_lang,
                            )
                            _exp = _analysis['explanation']
                            _tch = _analysis['teaching']
                            with st.expander("Guidance — why the fix did not work"):
                                st.markdown("**What is still wrong?**")
                                st.markdown(_exp['what_is_wrong'])
                                st.markdown("**Why is it still vulnerable?**")
                                st.markdown(_exp['why_is_it_vulnerable'])
                                st.markdown(f"**Principle:** `{_tch['principle']}`")
                                st.info(_tch['beginner_takeaway'])
                        except Exception:
                            pass

            if verif_result.get('new_issues'):
                st.markdown("**New issues introduced by your fix**")
                st.caption("These were not in the original baseline. They appear in your modified file.")
                for ni in verif_result['new_issues']:
                    ni_f   = ni['finding']
                    ni_msg = ni_f.get('message', '')
                    ni_cwe, ni_cat = classify_vulnerability(ni_msg)
                    ni_sev = normalize_severity(ni_f.get('severity', 'INFO')).upper()
                    with st.container(border=True):
                        st.markdown(f"""
                        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:4px 0 8px 0;">
                            <span class="verif-badge new-issue">NEW ISSUE</span>
                            {sev_badge_html(ni_sev)}
                            <span class="meta-chip">{html_mod.escape(ni_cwe)}</span>
                            <span class="meta-chip">{html_mod.escape(ni_cat)}</span>
                            <span class="meta-chip">Line {ni_f.get('line', '?')}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        st.markdown(f"**{ni_msg}**")
                        if ni_f.get('snippet'):
                            st.code(ni_f['snippet'], language=orig_lang)

            if overall == 'ALL_RESOLVED' and new_n == 0:
                st.success(
                    f"All {resolved_n} original vulnerability(ies) resolved. "
                    "Your modified code passed the verification scan with no new issues detected."
                )
            elif overall == 'ALL_RESOLVED' and new_n > 0:
                st.warning(
                    f"All {resolved_n} original vulnerability(ies) resolved, but your fix introduced "
                    f"**{new_n} new issue(s)**. Review the new findings above and try again."
                )
            elif overall in ('STILL_PRESENT', 'STILL_PRESENT_WITH_NEW_ISSUES'):
                extra = f" Your fix also introduced **{new_n} new issue(s)**." if new_n else ""
                st.error(
                    f"**{still_n}** original vulnerability(ies) still detected in your modified code.{extra} "
                    "Review the guidance above and try again."
                )
