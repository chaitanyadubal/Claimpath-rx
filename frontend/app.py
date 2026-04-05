"""
ClaimPath Rx — Medical Benefit Drug Policy Intelligence
Uses st.query_params for navigation — NO button row, NO gap.
"""
import os, httpx, streamlit as st, pandas as pd
import plotly.express as px, plotly.graph_objects as go
from datetime import datetime, timedelta

API = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="ClaimPath Rx",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
/* ── Kill every Streamlit chrome element ── */
#MainMenu, header, footer,
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stSidebar"],
[data-testid="collapsedControl"],
[data-testid="stStatusWidget"],
.stDeployButton,
[data-testid="manage-app-button"] { display:none!important; }

/* ── Zero out all container padding/margin ── */
html,body { margin:0!important; padding:0!important; background:#09090f!important; }
[data-testid="stApp"],
[data-testid="stAppViewContainer"],
section[data-testid="stMain"],
section[data-testid="stMain"]>div,
.main .block-container,
.block-container {
    padding:0!important;
    margin:0!important;
    max-width:100%!important;
    background:#09090f!important;
}

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
*{font-family:'Inter',-apple-system,sans-serif;box-sizing:border-box;}
body,p,li,span,div{color:#8b8aaa;}

/* ── NAV ── */
.cp-nav{
    background:#0d0d1a;
    border-bottom:1px solid #1a1730;
    padding:0 2.5rem;
    display:flex;
    align-items:center;
    gap:2px;
    width:100%;
    position:sticky;
    top:0;
    z-index:999;
}
.cp-brand{
    font-size:1rem;font-weight:800;color:#fff;
    padding:.85rem 1.2rem .85rem 0;
    border-right:1px solid #1a1730;
    margin-right:8px;white-space:nowrap;flex-shrink:0;
}
.cp-brand em{color:#8b5cf6;font-style:normal;}
.cp-link{
    padding:.85rem .9rem;
    font-size:.76rem;font-weight:500;
    color:#524f6e;
    white-space:nowrap;
    border-bottom:2px solid transparent;
    text-decoration:none!important;
    cursor:pointer;
    transition:color .15s,border-color .15s;
}
.cp-link:hover{color:#a78bfa;}
.cp-link.active{color:#a78bfa;border-bottom-color:#7c3aed;font-weight:600;}

/* ── LAYOUT ── */
.cp-page{padding:2rem 2.5rem;max-width:1100px;margin:0 auto;}

/* ── HERO ── */
.cp-hero{
    background:linear-gradient(135deg,#0d0b1e 0%,#130e2d 55%,#1a1244 100%);
    border:1px solid #1e1a35;border-radius:16px;
    padding:2.8rem;margin-bottom:2rem;
    position:relative;overflow:hidden;
}
.cp-hero::after{
    content:'';position:absolute;right:-80px;top:-80px;
    width:320px;height:320px;
    background:radial-gradient(circle,rgba(139,92,246,.13) 0%,transparent 65%);
    border-radius:50%;pointer-events:none;
}
.hero-eyebrow{font-size:.7rem;font-weight:700;color:#7c3aed;text-transform:uppercase;letter-spacing:.12em;margin-bottom:.7rem;}
.hero-title{font-size:2.1rem;font-weight:800;color:#fff;letter-spacing:-.5px;line-height:1.15;margin-bottom:.7rem;}
.hero-title em{color:#8b5cf6;font-style:normal;}
.hero-sub{font-size:.88rem;color:#524f6e;line-height:1.7;max-width:520px;margin-bottom:2.2rem;}
.hero-stats{display:flex;gap:2.5rem;flex-wrap:wrap;}
.hs-val{font-size:1.9rem;font-weight:800;color:#8b5cf6;display:block;line-height:1;}
.hs-lbl{font-size:.65rem;color:#3b3857;text-transform:uppercase;letter-spacing:.08em;margin-top:3px;}

/* ── SECTION HEAD ── */
.sec-title{font-size:1.35rem;font-weight:800;color:#f1f0f9;letter-spacing:-.3px;margin-bottom:.3rem;}
.sec-sub{font-size:.83rem;color:#524f6e;line-height:1.6;margin-bottom:1.2rem;}
.why-box{
    background:#0d0b1e;border-left:3px solid #7c3aed;
    border-radius:0 8px 8px 0;padding:.8rem 1.1rem;
    margin-bottom:1.4rem;font-size:.81rem;color:#524f6e;line-height:1.65;
}
.why-box strong{color:#a78bfa;}

/* ── FEATURE GRID ── */
.feat-grid{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:#1a1730;border:1px solid #1a1730;border-radius:14px;overflow:hidden;margin-bottom:1.5rem;}
.feat-cell{background:#0d0d1a;padding:1.4rem;transition:background .15s;}
.feat-cell:hover{background:#110e20;}
.fc-icon{font-size:1.2rem;margin-bottom:.5rem;}
.fc-title{font-size:.9rem;font-weight:700;color:#e2e0f0;margin-bottom:2px;}
.fc-ques{font-size:.74rem;color:#7c3aed;font-weight:600;margin-bottom:5px;}
.fc-desc{font-size:.78rem;color:#3b3857;line-height:1.6;}
.fc-btn{
    margin-top:.8rem;display:inline-block;
    font-size:.75rem;font-weight:600;color:#8b5cf6;
    border:1px solid #3d2a7e;border-radius:6px;
    padding:4px 12px;background:#1e1035;
    cursor:pointer;text-decoration:none!important;
    transition:background .15s;
}
.fc-btn:hover{background:#2d1b69;color:#c4b5fd;}

/* ── METRICS ── */
.metrics{display:grid;gap:10px;margin-bottom:1.4rem;}
.metric{background:#0d0d1a;border:1px solid #1a1730;border-radius:10px;padding:.9rem 1rem;text-align:center;}
.mv{font-size:1.55rem;font-weight:800;color:#8b5cf6;display:block;line-height:1;}
.ml{font-size:.64rem;color:#3b3857;text-transform:uppercase;letter-spacing:.07em;margin-top:3px;}
.m-blu .mv{color:#60a5fa;} .m-grn .mv{color:#34d399;}
.m-amb .mv{color:#fbbf24;} .m-red .mv{color:#f87171;}

/* ── COV TABLE ── */
.cov-tbl{border:1px solid #1a1730;border-radius:12px;overflow:hidden;margin-bottom:1rem;}
.cov-hd{background:#1a1730;display:grid;padding:7px 15px;font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#3b3857;}
.cov-row{background:#0d0d1a;border-top:1px solid #1a1730;display:grid;padding:11px 15px;align-items:center;transition:background .12s;}
.cov-row:hover{background:#100e1f;}
.cp-name{font-weight:700;color:#e2e0f0;font-size:.86rem;}
.cp-plan{color:#3b3857;font-size:.73rem;margin-top:1px;}
.jc{font-family:monospace;font-size:.74rem;color:#8b5cf6;background:#130e2d;padding:2px 6px;border-radius:4px;}

/* ── BADGE ── */
.bdg{display:inline-block;padding:2px 8px;border-radius:20px;font-size:.69rem;font-weight:700;}
.b-cov{background:#052e16;color:#34d399;} .b-pa{background:#1c1400;color:#fbbf24;}
.b-stp{background:#1c0a00;color:#fb923c;} .b-no{background:#1f0606;color:#f87171;}
.b-ql{background:#0c1e3a;color:#60a5fa;} .b-si{background:#071e2b;color:#38bdf8;}
.b-iv{background:#170a2b;color:#c084fc;}

/* ── PA CARD ── */
.pa-card{border:1px solid #1a1730;border-radius:12px;overflow:hidden;margin-bottom:1rem;}
.pa-hd{background:#130e2d;padding:.9rem 1.2rem;display:flex;justify-content:space-between;align-items:flex-start;border-bottom:1px solid #1e1a35;}
.pa-hd-t{font-weight:700;font-size:.91rem;color:#e2e0f0;}
.pa-hd-s{font-size:.72rem;color:#3b3857;margin-top:2px;}
.pa-body{padding:1.1rem 1.2rem;background:#0d0d1a;}
.pa-row{display:flex;gap:9px;align-items:flex-start;padding:7px 0;border-bottom:1px solid #1a1730;font-size:.82rem;color:#8b8aaa;}
.pa-row:last-child{border-bottom:none;}
.pa-ic{width:19px;height:19px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:9px;flex-shrink:0;margin-top:1px;}
.iw{background:#1c1400;color:#fbbf24;} .ir{background:#1f0606;color:#f87171;} .ig{background:#052e16;color:#34d399;}

/* ── STEP ── */
.st-item{display:flex;gap:10px;align-items:flex-start;margin-bottom:8px;}
.st-n{width:24px;height:24px;background:#1e1035;color:#8b5cf6;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:11px;flex-shrink:0;}
.st-drug{font-weight:600;color:#c4b5fd;font-size:.85rem;}
.st-det{color:#3b3857;font-size:.75rem;margin-top:2px;}

/* ── DIFF ── */
.di{border-radius:8px;padding:8px 12px;margin:4px 0;display:flex;gap:8px;align-items:flex-start;font-size:.81rem;}
.di-c{background:#1f0606;border-left:3px solid #dc2626;}
.di-g{background:#052e16;border-left:3px solid #16a34a;}
.di-a{background:#0d0d1a;border-left:3px solid #374151;}
.di-txt{color:#8b8aaa;line-height:1.55;}
.dsig{display:inline-block;font-size:9px;font-weight:700;padding:1px 5px;border-radius:3px;margin-left:4px;vertical-align:middle;}
.ds-c{background:#1f0606;color:#f87171;} .ds-g{background:#052e16;color:#34d399;} .ds-a{background:#1a1730;color:#524f6e;}

/* ── VERDICT ── */
.verd{border-radius:8px;padding:9px 13px;margin:8px 0;font-size:.86rem;font-weight:600;display:flex;align-items:center;gap:10px;}
.v-c{background:#1f0606;color:#fca5a5;border:1px solid #7f1d1d;}
.v-g{background:#052e16;color:#86efac;border:1px solid #14532d;}
.v-a{background:#0d0d1a;color:#524f6e;border:1px solid #1a1730;}

/* ── REBATE ── */
.rebate{background:linear-gradient(135deg,#0d0b1e,#1a1244);border:1px solid #2d1b69;border-radius:12px;padding:1.1rem 1.3rem;margin:1rem 0;}
.rebate-lbl{font-size:.65rem;text-transform:uppercase;letter-spacing:.09em;color:#3b3857;margin-bottom:4px;}
.rebate-txt{font-size:.84rem;color:#7c6fa8;line-height:1.6;}

/* ── INFO ── */
.info{background:#0d0b1e;border:1px solid #1e1a35;border-radius:8px;padding:8px 12px;font-size:.8rem;color:#524f6e;margin:7px 0;line-height:1.6;}
.info strong{color:#8b5cf6;}

/* ── PAYER GRID ── */
.pg{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:.8rem 0;}
.pt{background:#0d0d1a;border:1px solid #1a1730;border-radius:9px;padding:9px 12px;display:flex;align-items:center;gap:8px;}
.ptd{width:7px;height:7px;background:#34d399;border-radius:50%;flex-shrink:0;}
.ptn{font-weight:600;color:#c4b5fd;font-size:.8rem;}
.ptt{color:#3b3857;font-size:.7rem;}

/* ── CMP ── */
.cmp-wrap{border:1px solid #1a1730;border-radius:12px;overflow:hidden;}
.cmp-hdr{background:#130e2d;padding:7px 13px;display:grid;font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#3b3857;}
.cmp-row{background:#0d0d1a;border-top:1px solid #1a1730;padding:8px 13px;display:grid;font-size:.81rem;color:#8b8aaa;align-items:center;}
.cmp-row:nth-child(even){background:#0b0b17;}
.cmp-lbl{color:#3b3857;font-size:.72rem;font-weight:600;}

/* ── STREAMLIT FORM OVERRIDES ── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea{
    background:#0d0d1a!important;border:1px solid #1e1a35!important;
    color:#c4b5fd!important;border-radius:8px!important;font-size:.84rem!important;
}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder{color:#2e2b4a!important;}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus{border-color:#7c3aed!important;outline:none!important;}
[data-testid="stSelectbox"]>div>div,
[data-testid="stMultiSelect"]>div>div{
    background:#0d0d1a!important;border:1px solid #1e1a35!important;
    color:#c4b5fd!important;border-radius:8px!important;
}
[data-baseweb="popover"],[data-baseweb="menu"]{background:#0d0d1a!important;border:1px solid #1e1a35!important;}
[role="option"]{background:#0d0d1a!important;color:#c4b5fd!important;}
[role="option"]:hover{background:#1e1a35!important;}
[data-testid="stButton"]>button{
    background:#1e1035!important;color:#a78bfa!important;
    border:1px solid #3d2a7e!important;border-radius:8px!important;
    font-weight:600!important;font-size:.81rem!important;
    padding:.42rem 1.1rem!important;transition:all .15s!important;
}
[data-testid="stButton"]>button:hover{background:#2d1b69!important;border-color:#7c3aed!important;color:#c4b5fd!important;}
[data-testid="stExpander"]{background:#0d0d1a!important;border:1px solid #1a1730!important;border-radius:10px!important;}
[data-testid="stExpander"] summary{color:#8b8aaa!important;}
[data-testid="stExpander"]>div{background:#0d0d1a!important;}
[data-testid="stAlert"]{background:#0d0b1e!important;border-color:#3d2a7e!important;color:#a78bfa!important;}
[data-testid="stSuccess"]{background:#052e16!important;color:#34d399!important;border-color:#14532d!important;}
[data-testid="stFileUploader"]>div{background:#0d0b1e!important;border:1px dashed #1e1a35!important;border-radius:10px!important;color:#524f6e!important;}
[data-testid="stDataFrame"] table{background:#0d0d1a!important;}
[data-testid="stDataFrame"] th{background:#130e2d!important;color:#524f6e!important;font-size:.7rem!important;}
[data-testid="stDataFrame"] td{color:#8b8aaa!important;font-size:.8rem!important;border-color:#1a1730!important;}
[data-testid="stRadio"] label{color:#524f6e!important;font-size:.81rem!important;}
[data-testid="stRadio"] label:has(input:checked){color:#a78bfa!important;}
.stCaption{color:#3b3857!important;font-size:.72rem!important;}
p,li{color:#8b8aaa!important;font-size:.84rem!important;}
h1,h2,h3,h4{color:#e2e0f0!important;}
code{background:#130e2d!important;color:#a78bfa!important;border-radius:4px!important;}
</style>
""", unsafe_allow_html=True)


# ─── Helpers ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def api_get(path, params=None):
    try:
        r = httpx.get(f"{API}{path}", params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def api_post(path, data, timeout=120):
    try:
        r = httpx.post(f"{API}{path}", json=data, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None

def bdg(status):
    m = {
        "covered":("b-cov","✓ Covered"),
        "not_covered":("b-no","✗ Not Covered"),
        "covered_with_pa":("b-pa","⚠ Prior Auth"),
        "covered_with_step_therapy":("b-stp","↻ Step Therapy"),
        "covered_with_quantity_limit":("b-ql","⊠ Qty Limited"),
        "covered_site_restricted":("b-si","⊕ Site Restricted"),
        "non_covered_investigational":("b-iv","⊘ Investigational"),
    }
    c,l = m.get(status,("b-no",status.replace("_"," ").title()))
    return f'<span class="bdg {c}">{l}</span>'

def sigb(s):
    return {"clinical":'<span class="dsig ds-c">🔴 CLINICAL</span>',
            "cosmetic":'<span class="dsig ds-g">🟢 COSMETIC</span>',
            "administrative":'<span class="dsig ds-a">⚪ ADMIN</span>'}.get(s,'<span class="dsig ds-a">⚪</span>')

def ch(fig,h=250):
    fig.update_layout(height=h,margin=dict(t=20,b=0,l=0,r=0),
        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter",color="#524f6e"),showlegend=False)
    return fig

# ─── Load data ────────────────────────────────────────────────────────────────
stats       = api_get("/stats") or {}
g           = stats.get("graph",{})
v           = stats.get("vector",{})
payer_list  = (api_get("/payers") or {}).get("payers",[])
drug_list   = (api_get("/drugs")  or {}).get("drugs",[])
sup_payers  = (api_get("/supported-payers") or {}).get("payers",[])
class_list  = (api_get("/drug-classes") or {}).get("classes",[])

# ─── Navigation via query params — ZERO button row ────────────────────────────
PAGES = ["Home","Drug Coverage","PA Criteria","Compare Plans",
         "Changelog","Market Position","Auto-Crawl","Search","Ingest"]
ICONS = {"Home":"🏠","Drug Coverage":"🔍","PA Criteria":"📋",
         "Compare Plans":"⚖️","Changelog":"📅","Market Position":"🏆",
         "Auto-Crawl":"🤖","Search":"🔎","Ingest":"📥"}

params = st.query_params
pg = params.get("pg","Home")
if pg not in PAGES:
    pg = "Home"

def nav_link(name):
    icon = ICONS.get(name,"•")
    active = "active" if pg==name else ""
    return f'<a class="cp-link {active}" href="?pg={name}">{icon} {name}</a>'

# ─── Navbar ───────────────────────────────────────────────────────────────────
links = "".join(nav_link(p) for p in PAGES)
st.markdown(
    f'<div class="cp-nav"><div class="cp-brand">ClaimPath <em>Rx</em></div>{links}</div>',
    unsafe_allow_html=True
)

# ─── Page ─────────────────────────────────────────────────────────────────────
st.markdown('<div class="cp-page">', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# HOME
# ══════════════════════════════════════════════════════════════════════════════
if pg == "Home":
    st.markdown(f"""
    <div class="cp-hero">
        <div class="hero-eyebrow">Medical Benefit Drug Policy Intelligence</div>
        <div class="hero-title">ClaimPath <em>Rx</em></div>
        <div class="hero-sub">AI-powered ingestion, normalization, and real-time tracking of medical benefit drug policies across all major health plans — purpose-built for market access analysts.</div>
        <div class="hero-stats">
            <div><span class="hs-val">{g.get("drugs",0)}</span><span class="hs-lbl">Drugs</span></div>
            <div><span class="hs-val">{g.get("payers",0)}</span><span class="hs-lbl">Payers</span></div>
            <div><span class="hs-val">{g.get("policies",0)}</span><span class="hs-lbl">Policies</span></div>
            <div><span class="hs-val">{g.get("change_edges",0)}</span><span class="hs-lbl">Change Records</span></div>
            <div><span class="hs-val">{v.get("total_vectors",0)}</span><span class="hs-lbl">Indexed Vectors</span></div>
        </div>
    </div>

    <div class="feat-grid">
        <div class="feat-cell">
            <div class="fc-icon">🔍</div>
            <div class="fc-title">Drug Coverage</div>
            <div class="fc-ques">Which plans cover Drug X?</div>
            <div class="fc-desc">Every payer's coverage status — PA requirements, step therapy, site restrictions — normalized into one view. "Humira", "adalimumab", "J0135" all return the same result.</div>
            <a class="fc-btn" href="?pg=Drug Coverage">Open →</a>
        </div>
        <div class="feat-cell">
            <div class="fc-icon">📋</div>
            <div class="fc-title">PA Criteria</div>
            <div class="fc-ques">What does Plan Y require for Drug Z?</div>
            <div class="fc-desc">Full prior authorization breakdown — diagnoses, step drugs, clinical scores, prescriber requirements, renewal terms. Structured data, not raw PDF text.</div>
            <a class="fc-btn" href="?pg=PA Criteria">Open →</a>
        </div>
        <div class="feat-cell">
            <div class="fc-icon">⚖️</div>
            <div class="fc-title">Compare Plans</div>
            <div class="fc-ques">Side-by-side payer comparison</div>
            <div class="fc-desc">Put 2–5 payers side by side for the same drug. Differences highlighted in red instantly. Core deliverable for client advisory work.</div>
            <a class="fc-btn" href="?pg=Compare Plans">Open →</a>
        </div>
        <div class="feat-cell">
            <div class="fc-icon">📅</div>
            <div class="fc-title">Policy Changelog</div>
            <div class="fc-ques">What changed this quarter?</div>
            <div class="fc-desc">Clause-level diffs. Every change classified as 🔴 Clinical (affects patient access) or 🟢 Cosmetic (formatting only) — so you never waste time on noise.</div>
            <a class="fc-btn" href="?pg=Changelog">Open →</a>
        </div>
        <div class="feat-cell">
            <div class="fc-icon">🏆</div>
            <div class="fc-title">Market Position</div>
            <div class="fc-ques">Competitive landscape & rebate economics</div>
            <div class="fc-desc">Class size, competitors, biosimilar count. "Preferred 1-of-2" vs "1-of-5 with 7 biosimilars" drives every rebate contract.</div>
            <a class="fc-btn" href="?pg=Market Position">Open →</a>
        </div>
        <div class="feat-cell">
            <div class="fc-icon">🤖</div>
            <div class="fc-title">Auto-Crawl</div>
            <div class="fc-ques">Automated policy retrieval</div>
            <div class="fc-desc">Type a drug name — ClaimPath Rx visits Aetna, UHC, Cigna, BCBS, Humana automatically, finds, downloads, and ingests the right policies.</div>
            <a class="fc-btn" href="?pg=Auto-Crawl">Open →</a>
        </div>
        <div class="feat-cell">
            <div class="fc-icon">🔎</div>
            <div class="fc-title">Semantic Search</div>
            <div class="fc-ques">Free-text Q&A across all policies</div>
            <div class="fc-desc">Ask "Which payers require biosimilar trial first?" — AI embeddings search across all indexed policy documents and answer in seconds.</div>
            <a class="fc-btn" href="?pg=Search">Open →</a>
        </div>
        <div class="feat-cell">
            <div class="fc-icon">📥</div>
            <div class="fc-title">Ingest Policy</div>
            <div class="fc-ques">Add a policy manually</div>
            <div class="fc-desc">Upload a PDF or paste a URL. AI extracts all criteria, normalizes them, computes diffs against the previous version, and adds to the knowledge graph.</div>
            <a class="fc-btn" href="?pg=Ingest">Open →</a>
        </div>
    </div>

    <div class="info">💡 <strong>Start here:</strong> Use <strong><a href="?pg=Auto-Crawl" style="color:#8b5cf6;">Auto-Crawl</a></strong> to pull real payer policies automatically, or <strong><a href="?pg=Ingest" style="color:#8b5cf6;">Ingest</a></strong> to upload a PDF. Then search by drug name in <strong><a href="?pg=Drug Coverage" style="color:#8b5cf6;">Drug Coverage</a></strong>.</div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# DRUG COVERAGE
# ══════════════════════════════════════════════════════════════════════════════
elif pg == "Drug Coverage":
    st.markdown('<div class="sec-title">🔍 Drug Coverage Lookup</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">Search by drug name, brand name, or J-code billing code.</div>', unsafe_allow_html=True)
    st.markdown('<div class="why-box"><strong>Why this matters:</strong> Without this, an analyst opens 10 different PDFs to answer one question. Here it takes seconds. "Humira", "adalimumab", and "J0135" all return the same results.</div>', unsafe_allow_html=True)

    c1,c2,c3 = st.columns([3,2,1])
    with c1: drug_q = st.text_input("Drug","",placeholder="e.g. adalimumab · Humira · J0135",label_visibility="collapsed")
    with c2: pf = st.multiselect("Payer",payer_list,placeholder="All payers",label_visibility="collapsed")
    with c3: go_s = st.button("Search →",use_container_width=True)

    if go_s and drug_q:
        with st.spinner("Querying..."):
            resp = api_get(f"/coverage/{drug_q}",{"payers":",".join(pf) if pf else None})
        if resp and resp.get("coverage"):
            cov = resp["coverage"]
            npa = sum(1 for r in cov if r.get("pa_required"))
            nst = sum(1 for r in cov if r.get("step_required"))
            nbb = sum(1 for r in cov if r.get("buy_and_bill"))
            hc  = list(set(c for r in cov for c in (r.get("hcpcs_codes") or [])))

            st.markdown(f"""<div class="metrics" style="grid-template-columns:repeat(5,1fr);">
                <div class="metric"><span class="mv">{resp["total_plans"]}</span><span class="ml">Plans Found</span></div>
                <div class="metric m-amb"><span class="mv">{npa}</span><span class="ml">PA Required</span></div>
                <div class="metric m-red"><span class="mv">{nst}</span><span class="ml">Step Therapy</span></div>
                <div class="metric m-grn"><span class="mv">{nbb}</span><span class="ml">Buy & Bill</span></div>
                <div class="metric m-blu"><span class="mv">{", ".join(hc) or "—"}</span><span class="ml">J-Code(s)</span></div>
            </div>""", unsafe_allow_html=True)

            gtpl = "1.5fr 1fr .8fr .8fr 1fr .7fr"
            st.markdown(f'<div class="cov-tbl"><div class="cov-hd" style="grid-template-columns:{gtpl};"><span>Payer / Plan</span><span>Status</span><span>Prior Auth</span><span>Step Therapy</span><span>Site of Care</span><span>Version</span></div>', unsafe_allow_html=True)
            for r in cov:
                pac = "#fbbf24" if r.get("pa_required") else "#34d399"
                stc = "#fb923c" if r.get("step_required") else "#34d399"
                pts = "⚠ Yes" if r.get("pa_required") else "✓ No"
                sts = "↻ Yes" if r.get("step_required") else "✓ No"
                soc = ", ".join(s.replace("_"," ").title() for s in (r.get("site_of_care") or []))[:30] or "—"
                st.markdown(f"""<div class="cov-row" style="grid-template-columns:{gtpl};">
                    <div><div class="cp-name">{r.get("payer_name","")}</div><div class="cp-plan">{r.get("plan_name","")}</div></div>
                    <div>{bdg(r.get("coverage_status",""))}</div>
                    <div style="color:{pac};font-weight:600;font-size:.81rem;">{pts}</div>
                    <div style="color:{stc};font-weight:600;font-size:.81rem;">{sts}</div>
                    <div style="font-size:.74rem;color:#3b3857;">{soc}</div>
                    <div><span class="jc">{r.get("policy_version","")}</span></div>
                </div>""", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            ca,cb = st.columns(2)
            with ca:
                sc={r.get("coverage_status","?").replace("_"," ").title():0 for r in cov}
                for r in cov: sc[r.get("coverage_status","?").replace("_"," ").title()]+=1
                fig=px.pie(values=list(sc.values()),names=list(sc.keys()),hole=.55,
                    color_discrete_sequence=["#7c3aed","#a78bfa","#c4b5fd","#4c1d95","#60a5fa"])
                fig.update_traces(textfont_color="#e2e0f0",textfont_size=11)
                st.plotly_chart(ch(fig),use_container_width=True)
            with cb:
                fig2=go.Figure(go.Bar(x=["PA Req.","No PA","Step","Buy&Bill"],
                    y=[npa,len(cov)-npa,nst,nbb],
                    marker_color=["#fbbf24","#34d399","#fb923c","#8b5cf6"],
                    text=[npa,len(cov)-npa,nst,nbb],textposition="outside",textfont=dict(color="#8b8aaa")))
                fig2.update_xaxes(showgrid=False,color="#3b3857",tickfont_size=11)
                fig2.update_yaxes(visible=False)
                st.plotly_chart(ch(fig2),use_container_width=True)

            pap=[r for r in cov if r.get("pa_required") and r.get("pa_criteria")]
            if pap:
                st.markdown('<div style="font-size:.87rem;font-weight:700;color:#c4b5fd;margin:1.2rem 0 .6rem;">Prior Auth Details</div>',unsafe_allow_html=True)
                for r in pap:
                    with st.expander(f"📋 {r['payer_name']} — {r['plan_name']}"):
                        if r.get("pa_severity"): st.markdown(f'<div class="info"><strong>Severity:</strong> {r["pa_severity"]}</div>',unsafe_allow_html=True)
                        if r.get("step_drugs"):
                            wk=f" ({r['step_weeks']} wks min)" if r.get("step_weeks") else ""
                            st.markdown(f'<div class="info"><strong>🔄 Step therapy — must try first:</strong> {", ".join(r["step_drugs"])}{wk}</div>',unsafe_allow_html=True)
                        for c in (r.get("pa_criteria") or []): st.markdown(f'<div class="pa-row"><div class="pa-ic iw">⚠</div><div>{c}</div></div>',unsafe_allow_html=True)
                        for e in (r.get("pa_exclusions") or []): st.markdown(f'<div class="pa-row"><div class="pa-ic ir">✗</div><div style="color:#f87171;">{e}</div></div>',unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="text-align:center;padding:3rem 2rem;background:#0d0d1a;border:1px solid #1a1730;border-radius:12px;"><div style="font-size:1.8rem;margin-bottom:.6rem;">🔍</div><div style="font-size:.95rem;font-weight:700;color:#e2e0f0;margin-bottom:5px;">No data for "{drug_q}"</div><div style="color:#3b3857;font-size:.82rem;">Use <a href="?pg=Auto-Crawl" style="color:#8b5cf6;">Auto-Crawl</a> or <a href="?pg=Ingest" style="color:#8b5cf6;">Manual Ingest</a> to add policies.</div></div>',unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PA CRITERIA
# ══════════════════════════════════════════════════════════════════════════════
elif pg == "PA Criteria":
    st.markdown('<div class="sec-title">📋 Prior Authorization Criteria</div>',unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">Full, structured PA requirements for any drug at any payer.</div>',unsafe_allow_html=True)
    st.markdown('<div class="why-box"><strong>Why this matters:</strong> PA criteria are the #1 barrier to drug access. Knowing exactly what a payer requires lets you advise clients precisely and appeal denials effectively — without reading a PDF.</div>',unsafe_allow_html=True)

    c1,c2,c3=st.columns([2,2,1])
    with c1: pad=st.text_input("Drug","",placeholder="e.g. adalimumab",label_visibility="collapsed")
    with c2: pap=st.selectbox("Payer",payer_list if payer_list else ["—"],label_visibility="collapsed")
    with c3: pago=st.button("Look Up →",use_container_width=True)

    if pago and pad:
        with st.spinner("Fetching..."):
            resp=api_get(f"/pa/{pad}/{pap}")
        if resp and resp.get("criteria"):
            for item in resp["criteria"]:
                st.markdown(f"""<div class="pa-card">
                    <div class="pa-hd">
                        <div><div class="pa-hd-t">{item.get("payer_name","?")} — {item.get("plan_name","?")}</div>
                        <div class="pa-hd-s">Policy {item.get("policy_number","")} · v{item.get("policy_version","")} · Eff {item.get("effective_date","?")}</div></div>
                        <div>{bdg("covered_with_pa" if item.get("pa_required") else "covered")}</div>
                    </div><div class="pa-body">""",unsafe_allow_html=True)

                st.markdown(f"""<div class="metrics" style="grid-template-columns:repeat(4,1fr);margin-bottom:1rem;">
                    <div class="metric {'m-amb' if item.get('pa_required') else 'm-grn'}"><span class="mv">{'Yes' if item.get('pa_required') else 'No'}</span><span class="ml">PA Required</span></div>
                    <div class="metric m-blu"><span class="mv">{item.get('auth_duration_months','—') or '—'} mo</span><span class="ml">Auth Duration</span></div>
                    <div class="metric {'m-amb' if item.get('renewal_required') else 'm-grn'}"><span class="mv">{'Yes' if item.get('renewal_required') else 'No'}</span><span class="ml">Renewal</span></div>
                    <div class="metric {'m-red' if item.get('step_required') else 'm-grn'}"><span class="mv">{'Yes' if item.get('step_required') else 'No'}</span><span class="ml">Step Therapy</span></div>
                </div>""",unsafe_allow_html=True)

                if item.get("severity"): st.markdown(f'<div class="info"><strong>Severity:</strong> {item["severity"]}</div>',unsafe_allow_html=True)
                if item.get("prescriber_specialties"): st.markdown(f'<div class="info"><strong>Prescriber must be:</strong> {", ".join(item["prescriber_specialties"])}</div>',unsafe_allow_html=True)
                if item.get("step_required") and item.get("step_drugs"):
                    st.markdown('<div style="font-size:.79rem;font-weight:700;color:#8b5cf6;margin:.8rem 0 .4rem;">🔄 Step therapy — must try first:</div>',unsafe_allow_html=True)
                    for i,drug in enumerate(item["step_drugs"],1):
                        wks=f"Min {item['step_weeks']} weeks" if item.get("step_weeks") else ""
                        st.markdown(f'<div class="st-item"><div class="st-n">{i}</div><div><div class="st-drug">{drug}</div><div class="st-det">{wks} · {item.get("step_line","").replace("_"," ")}</div></div></div>',unsafe_allow_html=True)
                if item.get("clinical_scores"):
                    st.markdown('<div style="font-size:.79rem;font-weight:700;color:#8b5cf6;margin:.8rem 0 .4rem;">📊 Clinical criteria:</div>',unsafe_allow_html=True)
                    for s in item["clinical_scores"]: st.markdown(f'<div class="pa-row"><div class="pa-ic iw">📐</div><div>{s}</div></div>',unsafe_allow_html=True)
                if item.get("raw_criteria"):
                    st.markdown('<div style="font-size:.79rem;font-weight:700;color:#8b5cf6;margin:.8rem 0 .4rem;">📄 Full PA Criteria:</div>',unsafe_allow_html=True)
                    for i,c in enumerate(item["raw_criteria"],1): st.markdown(f'<div class="pa-row"><div class="pa-ic iw">{i}</div><div>{c}</div></div>',unsafe_allow_html=True)
                if item.get("exclusions"):
                    st.markdown('<div style="font-size:.79rem;font-weight:700;color:#f87171;margin:.8rem 0 .4rem;">❌ Exclusions — will deny PA:</div>',unsafe_allow_html=True)
                    for e in item["exclusions"]: st.markdown(f'<div class="pa-row"><div class="pa-ic ir">✗</div><div style="color:#f87171;">{e}</div></div>',unsafe_allow_html=True)
                if item.get("site_of_care"): st.markdown(f'<div class="info"><strong>Site of care:</strong> {", ".join(s.replace("_"," ").title() for s in item["site_of_care"])}</div>',unsafe_allow_html=True)
                st.markdown('</div></div>',unsafe_allow_html=True)
        else:
            st.warning(f"No PA criteria found for {pad} at {pap}.")


# ══════════════════════════════════════════════════════════════════════════════
# COMPARE PLANS
# ══════════════════════════════════════════════════════════════════════════════
elif pg == "Compare Plans":
    st.markdown('<div class="sec-title">⚖️ Cross-Payer Comparison</div>',unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">Same drug, multiple payers — differences highlighted automatically.</div>',unsafe_allow_html=True)
    st.markdown('<div class="why-box"><strong>Why this matters:</strong> This is the core client deliverable — showing a drug manufacturer exactly where they\'re advantaged or disadvantaged across key payer targets in one glance.</div>',unsafe_allow_html=True)

    c1,c2=st.columns([2,3])
    with c1: cd=st.text_input("Drug","",placeholder="e.g. ustekinumab",label_visibility="collapsed")
    with c2: cp=st.multiselect("Payers",payer_list,default=payer_list[:4] if len(payer_list)>=4 else payer_list,placeholder="Select payers",label_visibility="collapsed")
    cgo=st.button("Compare →",use_container_width=False)

    if cgo and cd:
        with st.spinner("Building..."):
            resp=api_post("/compare",{"drug_name":cd,"payer_names":cp or []})
        if resp and resp.get("comparison"):
            rows=resp["comparison"]
            pnames=[r.get("payer_name","?") for r in rows]
            gtpl=f"170px {' '.join(['1fr']*len(rows))}"
            fields=[
                ("coverage_status","Coverage",lambda v:v.replace("_"," ").title() if v else "—"),
                ("pa_required","PA Required",lambda v:"⚠ Yes" if v else "✓ No"),
                ("pa_severity","Severity Req.",lambda v:v or "—"),
                ("step_required","Step Therapy",lambda v:"↻ Yes" if v else "✓ No"),
                ("step_drugs","Must Try First",lambda v:", ".join(v) if v else "—"),
                ("step_weeks","Min. Weeks",lambda v:f"{v}w" if v else "—"),
                ("ql_applies","Qty Limit",lambda v:"Yes" if v else "No"),
                ("site_of_care","Site of Care",lambda v:", ".join(s.replace("_"," ").title() for s in v)[:26] if v else "—"),
                ("buy_and_bill","Buy & Bill",lambda v:"Yes" if v else "No"),
                ("auth_duration_months","Auth Duration",lambda v:f"{v} mo" if v else "—"),
                ("policy_version","Version",lambda v:v or "—"),
                ("effective_date","Effective",lambda v:v or "—"),
            ]
            h='<div class="cmp-wrap"><div class="cmp-hdr" style="grid-template-columns:'+gtpl+';"><span>Field</span>'+"".join(f"<span>{n}</span>" for n in pnames)+"</div>"
            for field,label,fmt in fields:
                vals=[fmt(r.get(field)) for r in rows]
                uniq=set(v for v in vals if v not in("—",""))
                cells="".join(f'<span style="color:{"#f87171" if len(uniq)>1 and v not in("—","") else "#8b8aaa"};">{v}</span>' for v in vals)
                h+=f'<div class="cmp-row" style="grid-template-columns:{gtpl};"><span class="cmp-lbl">{label}</span>{cells}</div>'
            h+="</div>"
            st.markdown(h,unsafe_allow_html=True)
            st.markdown('<div style="font-size:.71rem;color:#3b3857;margin-top:5px;">🔴 Red = differs across payers</div>',unsafe_allow_html=True)

            cc=[{"P":r.get("payer_name",""),"N":len(r.get("pa_criteria") or [])} for r in rows]
            if any(c["N"]>0 for c in cc):
                fig=px.bar(cc,x="P",y="N",color="N",color_continuous_scale=["#34d399","#fbbf24","#ef4444"])
                fig.update_traces(texttemplate="%{y}",textposition="outside",textfont_color="#8b8aaa")
                fig.update_xaxes(color="#3b3857",showgrid=False)
                fig.update_yaxes(visible=False)
                fig.update_coloraxes(showscale=False)
                st.plotly_chart(ch(fig,230),use_container_width=True)
        else:
            st.info("No comparison data — ingest policies first.")


# ══════════════════════════════════════════════════════════════════════════════
# CHANGELOG
# ══════════════════════════════════════════════════════════════════════════════
elif pg == "Changelog":
    st.markdown('<div class="sec-title">📅 Policy Change Tracker</div>',unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">Clause-level diffs between policy versions — know what actually changed.</div>',unsafe_allow_html=True)
    st.markdown('<div class="why-box"><strong>Why this matters:</strong> Payers update policies quarterly, sometimes overnight. Each change is classified as <strong>🔴 Clinical</strong> (affects patient access) or <strong>🟢 Cosmetic</strong> (formatting only) — so you never waste time on noise.</div>',unsafe_allow_html=True)

    c1,c2,c3,c4=st.columns([2,2,2,1])
    with c1: cp=st.selectbox("Payer",["All payers"]+payer_list,label_visibility="collapsed")
    with c2: cd=st.text_input("Drug","",placeholder="Drug (optional)",label_visibility="collapsed")
    with c3: cs=st.text_input("Since",(datetime.now()-timedelta(days=90)).strftime("%Y-%m-%d"),label_visibility="collapsed")
    with c4: cgo=st.button("Load →",use_container_width=True)
    sf=st.radio("",["All","🔴 Clinical","🟢 Cosmetic"],horizontal=True,label_visibility="collapsed")

    if cgo:
        with st.spinner("Loading..."):
            resp=api_get("/changelog",{"payer":None if cp=="All payers" else cp,"drug":cd or None,"since":cs or None})
        if resp and resp.get("changes"):
            changes=resp["changes"]
            nc=sum(c.get("clinical_changes",0) for c in changes)
            ng=sum(c.get("cosmetic_changes",0) for c in changes)
            na=sum(c.get("administrative_changes",0) for c in changes)

            st.markdown(f"""<div class="metrics" style="grid-template-columns:repeat(4,1fr);">
                <div class="metric"><span class="mv">{resp["total_changes"]}</span><span class="ml">Total Updates</span></div>
                <div class="metric m-red"><span class="mv">{nc}</span><span class="ml">🔴 Clinical</span></div>
                <div class="metric m-grn"><span class="mv">{ng}</span><span class="ml">🟢 Cosmetic</span></div>
                <div class="metric"><span class="mv">{na}</span><span class="ml">⚪ Admin</span></div>
            </div>""",unsafe_allow_html=True)

            fig=go.Figure(go.Bar(x=["Clinical","Cosmetic","Admin"],y=[nc,ng,na],
                marker_color=["#dc2626","#16a34a","#374151"],
                text=[nc,ng,na],textposition="outside",textfont=dict(color="#8b8aaa")))
            fig.update_xaxes(showgrid=False,color="#3b3857",tickfont_size=11)
            fig.update_yaxes(visible=False)
            st.plotly_chart(ch(fig,180),use_container_width=True)

            def passes(c):
                if "Clinical" in sf: return c.get("clinical_changes",0)>0
                if "Cosmetic" in sf: return c.get("cosmetic_changes",0)>0 and c.get("clinical_changes",0)==0
                return True

            filtered=[c for c in changes if passes(c)]
            st.markdown(f'<div style="font-size:.72rem;color:#3b3857;margin-bottom:.8rem;">Showing {len(filtered)} of {len(changes)} updates</div>',unsafe_allow_html=True)

            for ch_ in filtered:
                nc_=ch_.get("clinical_changes",0)
                ng_=ch_.get("cosmetic_changes",0)
                na_=ch_.get("administrative_changes",0)
                vcss="v-c" if nc_>0 else("v-g" if ng_>0 else "v-a")
                icon="🔴" if nc_>0 else("🟢" if ng_>0 else "⚪")
                with st.expander(f"{icon} {ch_.get('payer_name','')} — {ch_.get('drug_name','')} — v{ch_.get('old_version','?')} → v{ch_.get('new_version','?')}"):
                    st.markdown(f'<div class="verd {vcss}">{icon} {ch_.get("significance_verdict","")} <span style="font-size:.71rem;font-weight:400;margin-left:auto;opacity:.65;">{nc_} clinical · {ng_} cosmetic · {na_} admin</span></div>',unsafe_allow_html=True)
                    st.markdown(f'<div style="font-size:.77rem;color:#3b3857;margin:4px 0 8px;">Policy {ch_.get("policy_id","")} · {ch_.get("plan_name","")} · {str(ch_.get("detected_at",""))[:10]}</div>',unsafe_allow_html=True)
                    st.markdown(f'<div style="font-size:.82rem;color:#6b6888;margin-bottom:10px;"><strong style="color:#8b8aaa;">Summary:</strong> {ch_.get("summary","")}</div>',unsafe_allow_html=True)
                    for cc_ in ch_.get("changes",[]):
                        sig=cc_.get("significance","administrative")
                        msg=cc_.get("human_readable","")
                        rat=cc_.get("significance_rationale","")
                        ct=cc_.get("change_type","")
                        dcss="di-c" if sig=="clinical" else("di-g" if sig=="cosmetic" else "di-a")
                        di="➕" if "added" in ct else("➖" if "removed" in ct else "✏️")
                        st.markdown(f'<div class="di {dcss}"><span style="font-size:.88rem;">{di}</span><div class="di-txt">{msg} {sigb(sig)}<br><small style="opacity:.5;">{rat}</small></div></div>',unsafe_allow_html=True)
                        if cc_.get("old_value") and cc_.get("new_value"):
                            b1,b2=st.columns(2)
                            b1.code(f"Before: {cc_['old_value']}",language=None)
                            b2.code(f"After:  {cc_['new_value']}",language=None)
        else:
            st.info("No policy changes found. Load demo data or ingest policies first.")


# ══════════════════════════════════════════════════════════════════════════════
# MARKET POSITION
# ══════════════════════════════════════════════════════════════════════════════
elif pg == "Market Position":
    st.markdown('<div class="sec-title">🏆 Competitive Market Position</div>',unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">Class size, competitors, biosimilar pressure — inputs to every rebate contract.</div>',unsafe_allow_html=True)
    st.markdown('<div class="why-box"><strong>Why this matters:</strong> "Preferred 1-of-2" vs "1-of-5 with 7 biosimilars" are completely different rebate situations. This drives every formulary negotiation.</div>',unsafe_allow_html=True)

    c1,c2=st.columns([3,1])
    with c1: compd=st.text_input("Drug","",placeholder="e.g. adalimumab · pembrolizumab · dupilumab",label_visibility="collapsed")
    with c2: compgo=st.button("Analyze →",use_container_width=True)

    st.markdown('<div style="font-size:.77rem;color:#3b3857;margin:1rem 0 .4rem;">Or browse a therapeutic class:</div>',unsafe_allow_html=True)
    c1,c2=st.columns([3,1])
    with c1: classq=st.selectbox("Class",[""]+list(set(class_list+["TNF Inhibitor","IL-23 Inhibitor","PD-1 Inhibitor","CD20 Inhibitor"])),label_visibility="collapsed")
    with c2: classgo=st.button("View Class →",use_container_width=True)

    if compgo and compd:
        with st.spinner(f"Analyzing '{compd}'..."):
            resp=api_get(f"/competitive/{compd}")
        if resp:
            cs_=resp.get("class_size",0)
            bc_=resp.get("biosimilar_count",0)
            st.markdown(f"""<div class="metrics" style="grid-template-columns:repeat(4,1fr);">
                <div class="metric"><span class="mv">{resp.get("drug_class","—")}</span><span class="ml">Drug Class</span></div>
                <div class="metric {'m-red' if cs_>3 else 'm-amb' if cs_>1 else 'm-grn'}"><span class="mv">{cs_}</span><span class="ml">Class Size</span></div>
                <div class="metric {'m-red' if bc_>3 else 'm-amb' if bc_>0 else 'm-grn'}"><span class="mv">{bc_}</span><span class="ml">Biosimilars</span></div>
                <div class="metric"><span class="mv">{resp.get("payers_tracking",0)}</span><span class="ml">Payers Tracking</span></div>
            </div>""",unsafe_allow_html=True)
            st.markdown(f'<div style="font-size:.88rem;color:#c4b5fd;font-weight:600;margin-bottom:.5rem;">{resp.get("competitive_label","")}</div>',unsafe_allow_html=True)
            if resp.get("rebate_context"):
                st.markdown(f'<div class="rebate"><div class="rebate-lbl">💰 Rebate Economics</div><div class="rebate-txt">{resp["rebate_context"]}</div></div>',unsafe_allow_html=True)
            if resp.get("competitors_in_class"):
                st.markdown(f'<div class="info"><strong>Competitors:</strong> {", ".join(c.title() for c in resp["competitors_in_class"])}</div>',unsafe_allow_html=True)
        else:
            st.warning(f"'{compd}' not found. Try 'adalimumab' or 'humira'.")

    if classgo and classq:
        with st.spinner(f"Loading {classq}..."):
            resp=api_get(f"/class-landscape/{classq}")
        if resp and resp.get("drugs"):
            st.dataframe(pd.DataFrame([{"Drug":d["canonical"].title(),"Brand":", ".join(d.get("brand_names",[])[:2]),"HCPCS":", ".join(d.get("hcpcs",[])), "Mechanism":d.get("mechanism",""),"Route":d.get("route",""),"Peers":d.get("class_size",0),"Biosimilars":d.get("biosimilar_count",0)} for d in resp["drugs"]]),use_container_width=True,hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# AUTO-CRAWL
# ══════════════════════════════════════════════════════════════════════════════
elif pg == "Auto-Crawl":
    st.markdown('<div class="sec-title">🤖 Automated Policy Retrieval</div>',unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">Type a drug name — ClaimPath Rx finds, downloads, and ingests payer policies automatically.</div>',unsafe_allow_html=True)
    st.markdown('<div class="why-box"><strong>The demo wow moment:</strong> An analyst currently visits 5–10 different payer websites manually, each with a different layout. This replaces that entire workflow with a single drug name input.</div>',unsafe_allow_html=True)

    if sup_payers:
        g_='<div class="pg">'+"".join(f'<div class="pt"><div class="ptd"></div><div><div class="ptn">{p["name"]}</div><div class="ptt">{p["strategy"].replace("_"," ").title()}</div></div></div>' for p in sup_payers)+'</div>'
        st.markdown(g_,unsafe_allow_html=True)

    c1,c2=st.columns([2,1])
    with c1: autod=st.text_input("Drug to retrieve","",placeholder="e.g. adalimumab · ustekinumab · pembrolizumab")
    with c2: autops=st.multiselect("Limit payers",[p["key"] for p in sup_payers],format_func=lambda k:next((p["name"] for p in sup_payers if p["key"]==k),k),placeholder="All payers")

    st.markdown('<div class="info">Checks known direct PDF URLs first (instant), then falls back to dynamic page crawling. Some sites may block automation — reported gracefully.</div>',unsafe_allow_html=True)
    autogo=st.button("🤖  Start Auto-Retrieval",use_container_width=False)

    if autogo and autod:
        with st.spinner(f"Crawling payer sites for '{autod}' — 30–90 seconds..."):
            result=api_post("/auto-ingest",{"drug_name":autod,"payer_keys":autops or []},timeout=240)
        if result:
            st.markdown(f"""<div class="metrics" style="grid-template-columns:repeat(3,1fr);">
                <div class="metric"><span class="mv">{result.get("discovered",0)}</span><span class="ml">Discovered</span></div>
                <div class="metric m-amb"><span class="mv">{result.get("downloaded",0)}</span><span class="ml">Downloaded</span></div>
                <div class="metric m-grn"><span class="mv">{result.get("ingested",0)}</span><span class="ml">Ingested</span></div>
            </div>""",unsafe_allow_html=True)
            for s in result.get("sources",[]): st.markdown(f'<div class="di di-g"><span>✅</span><div class="di-txt"><strong>{s["payer"]}</strong> — {s["policy_number"]} — {s.get("drugs_extracted",0)} drugs<br><small style="opacity:.5;">{s["pdf_url"]}</small></div></div>',unsafe_allow_html=True)
            for e in result.get("errors",[]): st.markdown(f'<div class="di di-c"><span>⚠️</span><span class="di-txt">{e}</span></div>',unsafe_allow_html=True)
            if result.get("ingested",0)>0:
                st.success("Done! Go to Drug Coverage to search your new policies.")
                st.cache_data.clear()


# ══════════════════════════════════════════════════════════════════════════════
# SEARCH
# ══════════════════════════════════════════════════════════════════════════════
elif pg == "Search":
    st.markdown('<div class="sec-title">🔎 Semantic Policy Search</div>',unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">Natural language Q&A across all ingested policy documents.</div>',unsafe_allow_html=True)
    st.markdown('<div class="why-box"><strong>Why this matters:</strong> Answers ad-hoc questions across all policies at once — "Which payers require biosimilar trial first?" or "What are infusion center restrictions for IV biologics?" — in seconds.</div>',unsafe_allow_html=True)

    q=st.text_area("Question","",height=90,placeholder="Ask anything:\n• Does Cigna cover Rituxan for lupus?\n• What step therapy does UHC require for Humira?\n• Which payers require biosimilar trial before originator?\n• Site of care restrictions for IV biologics in RA",label_visibility="collapsed")
    c1,c2,c3=st.columns([2,2,1])
    with c1: sp=st.selectbox("Payer",["All"]+payer_list,label_visibility="collapsed")
    with c2: sd=st.selectbox("Drug",["All"]+drug_list,label_visibility="collapsed")
    with c3: sgo=st.button("Search →",use_container_width=True)

    if sgo and q:
        with st.spinner("Searching..."):
            resp=api_post("/search",{"query":q,"top_k":6,"filter_payer":None if sp=="All" else sp,"filter_drug":None if sd=="All" else sd})
        if resp and resp.get("results"):
            for i,r in enumerate(resp["results"]):
                score=int(r.get("score",0)*100)
                sc="#34d399" if score>=80 else("#fbbf24" if score>=60 else "#524f6e")
                with st.expander(f"{score}% — {r.get('payer_name','?')} — {r.get('drug_name','?')}",expanded=(i==0)):
                    st.markdown(f'<span style="background:#0d0b1e;color:{sc};padding:2px 8px;border-radius:20px;font-size:.69rem;font-weight:700;">{score}% match</span>',unsafe_allow_html=True)
                    st.markdown(r.get("text",""))
                    st.caption(f"Policy: {r.get('policy_id','')} · v{r.get('policy_version','')} · {r.get('coverage_status','')}")
        else:
            st.info("No results. Try broader terms or ingest more policies.")


# ══════════════════════════════════════════════════════════════════════════════
# INGEST
# ══════════════════════════════════════════════════════════════════════════════
elif pg == "Ingest":
    st.markdown('<div class="sec-title">📥 Manual Policy Ingestion</div>',unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">Upload a PDF or paste a URL for any payer not in auto-crawl.</div>',unsafe_allow_html=True)
    st.markdown('<div class="why-box"><strong>What happens:</strong> The AI parser extracts all coverage criteria, normalizes them, computes diffs against the previous version, and adds everything to the knowledge graph and search index automatically.</div>',unsafe_allow_html=True)

    method=st.radio("",["📄 Upload PDF","🔗 Paste URL"],horizontal=True,label_visibility="collapsed")
    c1,c2=st.columns(2)
    with c1:
        ingp=st.text_input("Payer name *","",placeholder="e.g. Aetna")
        ingl=st.text_input("Plan name *","",placeholder="e.g. Aetna Commercial")
        ingid=st.text_input("Policy ID *","",placeholder="e.g. CLAIMPATH-BIOLOGIC-2024")
    with c2:
        ingn=st.text_input("Policy number","",placeholder="e.g. CPB 0786")
        ingv=st.text_input("Version","2024.Q4")
        inge=st.text_input("Effective date","",placeholder="2024-10-01")

    if "Upload" in method:
        uploaded=st.file_uploader("",type=["pdf"],label_visibility="collapsed")
        if st.button("Ingest PDF →") and uploaded and ingp:
            with st.spinner(f"Parsing {uploaded.name} — 1–3 minutes..."):
                try:
                    r=httpx.post(f"{API}/ingest/upload",files={"file":(uploaded.name,uploaded.getvalue(),"application/pdf")},
                        params={"payer_name":ingp,"plan_name":ingl,"policy_id":ingid,"policy_version":ingv,"policy_number":ingn,"effective_date":inge},timeout=300)
                    r.raise_for_status()
                    res=r.json()
                    st.markdown(f'<div class="di di-g"><span>✅</span><div class="di-txt"><strong>Ingested!</strong> {res.get("drugs_extracted",0)} drugs · {res.get("chunks_indexed",0)} chunks · {res.get("diffs_created",0)} diffs<br>Drugs: {", ".join(res.get("drug_names",[]))}</div></div>',unsafe_allow_html=True)
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Failed: {e}")
    else:
        urlin=st.text_input("PDF URL","",placeholder="https://www.aetna.com/cpb/...")
        if st.button("Ingest from URL →") and urlin and ingp:
            with st.spinner("Downloading and normalizing..."):
                res=api_post("/ingest/url",{"url":urlin,"payer_name":ingp,"plan_name":ingl,"policy_id":ingid,"policy_version":ingv,"policy_number":ingn,"effective_date":inge})
                if res and res.get("status")=="success":
                    st.markdown(f'<div class="di di-g"><span>✅</span><div class="di-txt">{res.get("drugs_extracted",0)} drugs · {res.get("diffs_created",0)} diffs — {", ".join(res.get("drug_names",[]))}</div></div>',unsafe_allow_html=True)
                    st.cache_data.clear()

    st.markdown('<div style="margin-top:1.5rem;font-size:.77rem;color:#3b3857;margin-bottom:.4rem;">Public payer policy portals:</div>',unsafe_allow_html=True)
    for name,url in [
        ("Aetna Clinical Policy Bulletins","https://www.aetna.com/health-care-professionals/clinical-policy-bulletins/medical-clinical-policy-bulletins.html"),
        ("UnitedHealthcare Medical Policies","https://www.uhcprovider.com/en/policies-protocols/advance-notification-med-policies.html"),
        ("Cigna Coverage Policies","https://www.cigna.com/healthcare-professionals/coverage-policies"),
        ("BCBS Federal Program","https://www.fepblue.org/benefit-information/benefit-resources/clinical-policies"),
        ("Humana Prior Auth","https://www.humana.com/provider/medical-resources/pharmacy-resources/specialty-pharmacy/prior-authorization"),
    ]:
        st.markdown(f'<a href="{url}" style="color:#6d28d9;font-size:.79rem;display:block;margin-bottom:3px;">• {name}</a>',unsafe_allow_html=True)

st.markdown('</div>',unsafe_allow_html=True)
