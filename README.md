# ⚡ DocGenius RAG Studio
### Enterprise Document Generation, Multi-Strategy Summarization & Latency-Optimized RAG

A high-performance, modular Python platform engineered for **Sub-Second Hybrid Retrieval**, **Multi-Strategy Parallel Summarization** (Stuff, Map-Reduce, Refine, Query-Focused), and **Template-Grounded Document Generation** with flag-based support for both **Google Gemini Cloud** and **Local Private Ollama**.

---

## 🌟 Key Features

1. **🎛️ Flag-Based Dual Provider (Cloud & On-Premises)**:
   - **Google Gemini Cloud API**: High throughput (150+ tok/s), ultra-low TTFT (250-350ms), zero local GPU required.
   - **Local Ollama Server**: 100% private offline execution (`http://localhost:11434`), zero data egress, support for `llama3:8b`, `mistral`, `llama3.2`, `qwen2.5`, `nomic-embed-text`, etc.
   - Runtime switching via `config.yaml` or Streamlit Sidebar radio toggle.

2. **📑 Multi-Strategy Document Summarizer**:
   - **Stuff Summarization**: Lowest latency single-prompt synthesis for short/medium documents.
   - **Map-Reduce Summarization**: Concurrently maps chunk summaries across worker threads, then reduces into an executive master brief (handles 100+ pages without context loss).
   - **Refine Summarization**: Sequential rolling synthesis for chronological narratives.
   - **Query-Focused Grounded Summarization**: RAG-powered topic synthesis (e.g., *"Summarize all escrow reconciliation and APMC cess rules"*).

3. **✍️ Template-Grounded Document Generator**:
   - Pre-built enterprise templates: **Executive Summary**, **Standard Operating Procedure (SOP)**, **Incident Post-Mortem & RCA**, **Audit & Compliance Report**, and **Technical Architecture Spec**.
   - Section-aware semantic grounding with verified citations.
   - Instant export to **Markdown** and **HTML**.

4. **🔍 Sub-Second Hybrid Retrieval Engine**:
   - **Dense Semantic Embeddings** (Gemini `text-embedding-004` / Local `nomic-embed-text`) + **Sparse BM25 Keyword Search**.
   - **Reciprocal Rank Fusion (RRF)** and **Maximal Marginal Relevance (MMR)** diversity re-ranking.
   - Dual-tier in-memory LRU + disk hash caching reducing repeat query latency to `< 1ms`.

5. **⚡ Real-Time Latency Telemetry & Profiling**:
   - Stage-by-stage latency tracking: Ingestion $\rightarrow$ Chunking $\rightarrow$ Embedding $\rightarrow$ Retrieval $\rightarrow$ TTFT $\rightarrow$ Token Throughput.
   - Automated bottleneck identification.

---

## 📂 Project Structure

```text
DocumentGeneration&Summarizetion/
├── .env.example
├── README.md
├── LATENCY_AND_IMPLEMENTATION_GUIDE.md  # Exhaustive Latency & Design Blueprint
├── requirements.txt
├── config.yaml                         # System parameters & Provider flags
├── app.py                              # Streamlit Interactive Web Studio
├── core/
│   ├── __init__.py
│   ├── config.py                       # Configuration & Dataclasses (Gemini & Ollama)
│   ├── latency_tracker.py              # High-precision Latency Profiler
│   ├── document_loader.py              # Multi-format parser (PDF, DOCX, MD, TXT, CSV, JSON)
│   ├── chunker.py                      # Semantic & Header-aware Chunker
│   ├── embeddings.py                   # Gemini & Ollama Cached Vector Engine
│   ├── vector_store.py                 # Vectorized NumPy Cosine Store
│   ├── retriever.py                    # Hybrid Dense + BM25 with RRF & MMR
│   ├── prompt_templates.py             # Enterprise Prompt Templates
│   ├── summarizer.py                   # Multi-Strategy Summarizer (Stuff, MapReduce, Refine)
│   └── document_generator.py           # Grounded Template Document Generator
├── templates/                          # Enterprise Markdown Templates
│   ├── executive_summary.md
│   ├── sop_template.md
│   ├── incident_postmortem.md
│   ├── audit_compliance_report.md
│   └── technical_spec.md
├── samples/                            # Pre-loaded Enterprise Domain Documents
│   ├── remsl_mandi_trading_sop.md
│   ├── neml_payment_gateway_spec.md
│   └── quarterly_financial_audit.md
└── tests/
    └── test_rag_pipeline.py            # Unit & Integration Test Suite
```

---

## 🚀 Quick Start Guide

### 1. Installation
```bash
cd "C:\Users\neml10742\Downloads\clone\DocumentGeneration&Summarizetion"
pip install -r requirements.txt
```

### 2. Configure Provider in `config.yaml`
```yaml
# Set provider to "gemini" or "ollama"
provider: "ollama"

ollama:
  base_url: "http://localhost:11434"
  llm_model: "llama3:8b"
  embedding_model: "nomic-embed-text"
```

### 3. Run Automated Test Suite
```bash
python -m unittest tests/test_rag_pipeline.py
```

### 4. Launch the Web Studio
```bash
python -m streamlit run app.py
```
*Access the interactive studio at `http://localhost:8501` to toggle between Gemini Cloud and Local Ollama on the fly.*
