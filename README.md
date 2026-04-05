<div align="center">

<img src="https://img.shields.io/badge/ClaimPath-Rx-8b5cf6?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xOSAzSDVhMiAyIDAgMCAwLTIgMnYxNGEyIDIgMCAwIDAgMiAyaDE0YTIgMiAwIDAgMCAyLTJWNWEyIDIgMCAwIDAtMi0yek0xMSAxN0g5di01SDd2LTJoMlY4aDJ2MmgydjJoLTJ2NXoiLz48L3N2Zz4=&labelColor=06060f"/>

# ClaimPath Rx

### Medical Benefit Drug Policy Intelligence Platform

*AI-powered ingestion, normalization, and real-time tracking of medical benefit drug policies across all major health plans*

<br/>

[![Live Demo](https://img.shields.io/badge/🌐_Live_Demo-chaitanyadubal.github.io/Claimpath--rx-8b5cf6?style=for-the-badge&labelColor=0d0d1a)](https://chaitanyadubal.github.io/Claimpath-rx)
[![API Docs](https://img.shields.io/badge/📡_API_Docs-Swagger_UI-0ea5e9?style=for-the-badge&labelColor=0d0d1a)](https://claimpath-rx.onrender.com/docs)
[![Built at ASU](https://img.shields.io/badge/🏫_Built_at-ASU_Innovation_Hacks_2.0-fbbf24?style=for-the-badge&labelColor=0d0d1a)](https://www.asu.edu)

<br/>

![Python](https://img.shields.io/badge/Python-3.11-3776ab?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-AuraDB-008cc1?style=flat-square&logo=neo4j&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-dc244c?style=flat-square&logo=qdrant&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-Llama_3.3_70B-f55036?style=flat-square&logo=groq&logoColor=white)
![GitHub Pages](https://img.shields.io/badge/GitHub_Pages-Frontend-222?style=flat-square&logo=github&logoColor=white)

</div>

---

## 🎯 The Problem

A pharmaceutical market access analyst needs to answer: *"Which plans cover Drug X, and what do they require for prior authorization?"*

Today they open **10 different PDFs** from 10 different payer websites — each formatted differently, updated at different times, with no way to compare side-by-side. This takes **hours**.

**ClaimPath Rx solves this in seconds.**

---

## ✨ What It Does

| Feature | What it solves |
|---|---|
| 🔍 **Drug Coverage Lookup** | See every payer's coverage status in one normalized view. Search by name, brand, or J-code. |
| 📋 **PA Criteria** | Full prior authorization requirements — diagnoses, step therapy, clinical scores, prescriber requirements |
| ⚖️ **Cross-Payer Comparison** | Side-by-side diff of 2–5 payers for the same drug. Differences highlighted automatically |
| 📅 **Policy Changelog** | Clause-level diffs between versions. Every change tagged 🔴 Clinical or 🟢 Cosmetic |
| 🏆 **Market Position** | Class size, competitors, biosimilar count — inputs to every rebate contract |
| 🤖 **Auto-Crawl** | One drug name → automatically retrieves policies from Aetna, UHC, Cigna, BCBS, Humana |
| 🔎 **Semantic Search** | Natural language Q&A across all ingested policies using AI vector embeddings |
| 📥 **Manual Ingest** | Upload a PDF or paste a URL — AI extracts, normalizes, diffs, indexes automatically |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    ClaimPath Rx                          │
├──────────────┬──────────────────────────────────────────┤
│   Frontend   │  Pure HTML/CSS/JS SPA                    │
│  (GitHub     │  • Animated particle canvas background   │
│   Pages)     │  • Custom cursor with glow ring          │
│              │  • Zero-reload single-page navigation    │
│              │  • Calls FastAPI via fetch()             │
├──────────────┴──────────────────────────────────────────┤
│                   FastAPI Backend                        │
│                  (Render.com Free)                       │
├────────────────┬────────────────┬───────────────────────┤
│   Neo4j        │    Qdrant      │      Groq LLM         │
│   AuraDB       │  Vector DB     │  Llama 3.3 70B        │
│                │  BGE-M3 1024d  │  + LLM Extractor      │
│  Policy Graph  │  Semantic      │  Policy Parser        │
│  Drug Nodes    │  Search Index  │  Diff Classifier      │
│  Payer Nodes   │                │                       │
└────────────────┴────────────────┴───────────────────────┘
```

### Data Flow
```
PDF / URL
   │
   ▼
PDF Parser ──► LLM Extractor (Groq) ──► Normalized Schema
                                              │
                        ┌─────────────────────┤
                        ▼                     ▼
                   Neo4j Graph          Qdrant Vectors
                 (Drug + Coverage     (BGE-M3 Embeddings
                    Nodes)             for Semantic Search)
                        │
                        ▼
                 Policy Differ
              (Clinical vs Cosmetic
                Classification)
```

---

## 🚀 Three Innovation Gaps

This project addresses three specific challenges beyond basic ingestion:

### Gap 1 — Auto-Crawler 🤖
Automatically discovers, downloads, and ingests policy PDFs from 5 major payers using known direct URLs with dynamic HTML fallback. No more manual PDF hunting.

### Gap 2 — Competitive Position 🏆
For any drug, returns therapeutic class size, biosimilar count, competitor list, and rebate economics context. `"Preferred 1-of-2"` vs `"1-of-5 with 7 biosimilars"` completely changes rebate leverage.

### Gap 3 — Clinical Significance Classifier 📅
Every policy diff is classified as:
- 🔴 **Clinical** — affects patient access (step drug added, PA criteria tightened)
- 🟢 **Cosmetic** — formatting only (header renamed, section reordered)
- ⚪ **Administrative** — billing/coding changes

So analysts never waste time reading irrelevant changes.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Pure HTML5, CSS3, Vanilla JS — no framework |
| **Backend** | FastAPI + Uvicorn (Python 3.11) |
| **Graph Database** | Neo4j AuraDB Free |
| **Vector Database** | Qdrant Cloud Free |
| **Embeddings** | BAAI/BGE-M3 (1024-dim, runs locally) |
| **LLM** | Groq API — Llama 3.3 70B Versatile |
| **PDF Parsing** | pdfplumber + custom extraction pipeline |
| **Frontend Hosting** | GitHub Pages |
| **Backend Hosting** | Render.com (Free tier) |

---

## ⚡ Quick Start (Local)

### Prerequisites
- Python 3.11+
- Neo4j AuraDB account (free)
- Qdrant Cloud account (free)
- Groq API key (free)

### 1. Clone & Install

```bash
git clone https://github.com/chaitanyadubal/Claimpath-rx.git
cd Claimpath-rx
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

### 2. Set Environment Variables

Create a `.env` file in the root:

```env
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
QDRANT_URL=https://your-instance.us-west-1-0.aws.cloud.qdrant.io
QDRANT_API_KEY=your-qdrant-key
GROQ_API_KEY=your-groq-key
EMBEDDING_MODEL=BAAI/bge-m3
LLM_MODEL=llama-3.3-70b-versatile
```

### 3. Load Demo Data

```bash
python scripts/load_demo_data.py
```

This loads **9 demo coverage records** across:
- Adalimumab × Aetna, UHC, Cigna
- Infliximab × Aetna, UHC
- Ustekinumab × Aetna, BCBS Federal
- Pembrolizumab × Aetna
- Dupilumab × UHC

### 4. Run the Backend

```bash
uvicorn backend.main:app --reload --port 8000
```

API docs available at: `http://localhost:8000/docs`

### 5. Open the Frontend

Open `docs/index.html` directly in your browser — it auto-detects localhost.

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/coverage/{drug}` | Coverage across all payers |
| `GET` | `/pa/{drug}/{payer}` | Full PA criteria |
| `GET` | `/changelog` | Policy version diffs |
| `POST` | `/compare` | Cross-payer comparison |
| `POST` | `/search` | Semantic search |
| `POST` | `/auto-ingest` | Auto-crawl payer sites |
| `GET` | `/competitive/{drug}` | Market position |
| `GET` | `/class-landscape/{class}` | Therapeutic class view |
| `POST` | `/ingest/url` | Ingest from URL |
| `POST` | `/ingest/upload` | Ingest PDF upload |
| `GET` | `/stats` | Platform statistics |
| `GET` | `/health` | Health check |

---

## 🗂️ Project Structure

```
Claimpath-rx/
├── docs/
│   └── index.html              # Frontend SPA (GitHub Pages)
├── backend/
│   ├── main.py                 # FastAPI app + all endpoints
│   ├── api/
│   │   └── query_router.py     # Query routing logic
│   ├── core/
│   │   ├── config.py           # Settings & env vars
│   │   ├── models.py           # Pydantic data models
│   │   └── drug_master.py      # Drug normalization + Gap 2
│   ├── crawler/
│   │   └── payer_crawler.py    # Auto-crawl (Gap 1)
│   ├── diff/
│   │   └── policy_differ.py    # Diff + significance (Gap 3)
│   ├── graph/
│   │   └── neo4j_manager.py    # Neo4j operations
│   ├── ingestion/
│   │   ├── pdf_parser.py       # PDF extraction
│   │   └── llm_extractor.py    # LLM normalization
│   └── vector/
│       └── qdrant_manager.py   # Vector indexing + search
├── frontend/
│   └── app.py                  # Streamlit UI (backup)
├── scripts/
│   └── load_demo_data.py       # Demo data loader
├── render.yaml                 # Render deployment config
└── requirements.txt
```

---

## 🎓 Built For

**ASU Innovation Hacks 2.0** — April 2026  
*Anton Rx Challenge: Medical Benefit Drug Policy Tracker*

**Team:** Solo submission  
**Developer:** Chaitanya Dubal — MSc Information Technology, Arizona State University

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with 💜 at Arizona State University**

[Live Demo](https://chaitanyadubal.github.io/Claimpath-rx) · [API Docs](https://claimpath-rx.onrender.com/docs) · [LinkedIn](https://linkedin.com/in/chaitanyadubal)

</div>
