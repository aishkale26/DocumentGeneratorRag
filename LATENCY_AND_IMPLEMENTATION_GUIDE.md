# ⚡ Comprehensive Guide: Latency Engineering & Key Implementation Factors for Enterprise Document Generation & Summarization RAG

## Executive Overview
When deploying an enterprise-grade Retrieval-Augmented Generation (RAG) and Document Summarization system, **Latency**, **Data Privacy (Cloud vs On-Premises)**, and **Factual Grounding** are the three most critical pillars.

This platform provides **flag-based runtime switching** between **Google Gemini (Cloud API)** and **Local Ollama (100% Private Offline Inference)**.

---

## 1. The RAG Latency Anatomy & Mathematical Formulation

The total wall-clock latency of a RAG query or document generation pipeline is the sum of distinct sequential and concurrent stages:

$$T_{\text{total}} = T_{\text{load}} + T_{\text{chunk}} + T_{\text{query\_emb}} + T_{\text{retrieval}} + T_{\text{rerank}} + T_{\text{prompt\_assembly}} + T_{\text{TTFT}} + \frac{N_{\text{out}}}{\text{Throughput}_{\text{decode}}}$$

### Breakdown of Latency Components:
| Component | Typical Latency (Unoptimized) | Cloud Gemini (Optimized) | Local Ollama (GPU Q4_K_M) | Local Ollama (CPU-Only) |
| :--- | :--- | :--- | :--- | :--- |
| **$T_{\text{load}}$ (Document Parsing)** | 500ms – 3,000ms | **10ms – 80ms** | **10ms – 80ms** | **10ms – 80ms** |
| **$T_{\text{chunk}}$ (Text Chunking)** | 50ms – 200ms | **2ms – 15ms** | **2ms – 15ms** | **2ms – 15ms** |
| **$T_{\text{query\_emb}}$ (Embedding)** | 150ms – 400ms | **< 1ms (Cached) / 60ms** | **< 1ms (Cached) / 25ms** | **< 1ms (Cached) / 120ms** |
| **$T_{\text{retrieval}}$ (Vector + BM25)** | 80ms – 300ms | **1ms – 8ms** | **1ms – 8ms** | **1ms – 8ms** |
| **$T_{\text{rerank}}$ (Fusion / MMR)** | 50ms – 500ms | **5ms – 20ms** | **5ms – 20ms** | **5ms – 20ms** |
| **$T_{\text{TTFT}}$ (Time to First Token)** | 800ms – 2,500ms | **250ms – 350ms** | **180ms – 450ms** | **1,500ms – 4,000ms** |
| **$T_{\text{decode}}$ (Token Generation)** | 3,000ms – 12,000ms | **120 – 160 tok/s** | **45 – 90 tok/s** | **8 – 18 tok/s** |

---

## 2. Local Ollama vs Cloud Gemini: Architectural & Latency Factors

```mermaid
flowchart TD
    subgraph Cloud ["1. Google Gemini Cloud API"]
        G_In["Prompt / Chunks"] --> G_Net["HTTPS TLS Network Roundtrip (50-120ms)"]
        G_Net --> G_GPU["Google TPU/GPU Farm (Massive Parallelism)"]
        G_GPU --> G_Out["High Throughput (150+ tok/s)"]
    end

    subgraph Local ["2. Local Ollama Server (100% Private)"]
        O_In["Prompt / Chunks"] --> O_IPC["Localhost Unix Socket / TCP (< 1ms)"]
        O_IPC --> O_VRAM["Local GPU VRAM (RTX / Metal / ROCm)"]
        O_VRAM --> O_Out["Zero Data Egress, 40-90 tok/s"]
    end
```

### Key Considerations for Local Ollama Deployment:
1. **GPU VRAM Allocation & Layer Offloading:**
   - For `llama3:8b` (Q4_K_M quantized), minimum VRAM is **5.8 GB**.
   - If layers spill into system RAM (CPU fallback), generation speed drops from **65 tok/s to 12 tok/s** (5.4x latency increase).
2. **Parallel Map-Reduce Worker Throttling:**
   - In Cloud API mode, we run up to 5 concurrent Map calls (`max_workers=5`).
   - In Local Ollama mode, our engine automatically throttles workers to **2 concurrent threads** to prevent GPU VRAM thrashing and CUDA out-of-memory errors.
3. **Local Embedding Models:**
   - Using `nomic-embed-text` or `mxbai-embed-large` locally eliminates external API quotas and delivers local query embeddings in **~25ms** on GPU.

---

## 3. Factor 1: Chunking Strategy vs Latency & Context Retention

| Chunk Size (Tokens) | Overlap (Tokens) | Retrieval Recall | Embedding Latency | Context Window Bloat | LLM TTFT | Recommended Use Case |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **150 – 300** | 30 – 50 | High granularity | Ultra-low (<50ms) | Very Low | **Fastest (<300ms)** | Specific fact lookup, FAQ matching, error codes |
| **500 – 800** | 100 – 150 | **Optimal (High Precision & Rich Context)** | Balanced (60-100ms) | Moderate | **Optimal (~450ms)** | **Enterprise RAG, SOPs, Contract Summaries (Default)** |
| **1,200 – 2,000** | 200 – 300 | High context | Higher (150-300ms) | High | Slower (~900ms) | Multi-section document generation & Map-Reduce stages |

---

## 4. Factor 2: Summarization Strategy vs Latency & Quality

| Summarization Strategy | Computational Complexity | Number of LLM Calls | Wall-Clock Latency (10-Page Doc) | Wall-Clock Latency (100-Page Doc) | Pros & Cons |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Stuff Strategy** | $O(1)$ | 1 call | **1.2 – 2.5 seconds** | Fails / Exceeds context | **Lowest Latency**. Suffers from "Lost in the Middle" on large text. |
| **Map-Reduce (Parallel)** | $O(N)$ Map + $O(1)$ Reduce | $N + 1$ calls | **2.8 – 4.5 seconds** *(Concurrent)* | **6.0 – 9.5 seconds** *(Concurrent)* | **Fast & Scalable**. Processes unlimited pages; preserves all section facts. |
| **Refine (Rolling)** | $O(N)$ Sequential | $N$ calls | 12.0 – 18.0 seconds | 90 – 180 seconds | **Highest Quality for Narratives**, but **Extreme Latency** ($N \times \text{LLM Call}$). |
| **Query-Focused (RAG)** | $O(\text{Top-K})$ | 1 call | **1.5 – 3.0 seconds** | **1.5 – 3.0 seconds** | **Sub-second precision**. Summarizes only the relevant $K$ chunks for a specific topic. |

---

## 5. Factor 3: Hybrid Retrieval (Dense + BM25) & Re-ranking Latency

$$\text{Score}_{\text{hybrid}} = \alpha \cdot \text{Score}_{\text{dense}} + (1 - \alpha) \cdot \text{Score}_{\text{BM25}}$$

- **Dense Search (Gemini / Nomic):** Concepts, semantic context, natural language questions.
- **Sparse BM25:** Exact codes (`LOT-BLG-2026-8941`), statutory clauses, APMC cess figures (`1.5%`).
- **Maximal Marginal Relevance (MMR):** Eliminates duplicate retrieved chunks in **< 10ms** without heavy Cross-Encoder latency.

---

## 6. Flag-Based Switching Configuration (`config.yaml`)

Switching between Cloud and Local inference is controlled either via `config.yaml` or directly from the Streamlit UI sidebar:

```yaml
# Set provider to "gemini" or "ollama"
provider: "ollama"

ollama:
  base_url: "http://localhost:11434"
  llm_model: "llama3:8b"
  embedding_model: "nomic-embed-text"
  timeout_seconds: 60
  temperature: 0.2
  num_ctx: 8192
```

---

## 7. Latency Summary Checklist for Enterprise RAG Deployment

- [x] **Dual Provider Support:** Gemini Cloud API + Local Ollama Server.
- [x] **Embedding Cache:** Implemented dual-layer Memory + Disk hash caching.
- [x] **Vector Store:** Vectorized NumPy cosine similarity matrix ($<10\text{ms}$ lookup).
- [x] **Hybrid Retrieval:** Combined Dense (65%) + BM25 (35%) + MMR diversity re-ranking.
- [x] **Summarization Engine:** Implemented parallelized Map-Reduce with worker pools.
- [x] **Document Generator:** Template-based grounded generation with section citations.
- [x] **Telemetry:** Real-time stage latency tracking with bottleneck diagnostics.
- [x] **User Interface:** Responsive Streamlit portal with streaming token output and provider switcher.
