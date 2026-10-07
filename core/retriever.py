import math
import re
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from .chunker import Chunk
from .embeddings import EmbeddingEngine
from .vector_store import VectorStore
from .latency_tracker import LatencyTracker

@dataclass
class RetrievalResult:
    chunk: Chunk
    score: float
    dense_score: float = 0.0
    sparse_score: float = 0.0
    rank: int = 1

class BM25Index:
    """
    In-Memory Okapi BM25 Index for keyword/sparse lexical retrieval.
    """
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = 0
        self.avg_doc_len = 0.0
        self.doc_lens: List[int] = []
        self.doc_freqs: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.term_freqs: List[Dict[str, int]] = []

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r'\b\w+\b', text.lower())

    def fit(self, chunks: List[Chunk]):
        self.corpus_size = len(chunks)
        if self.corpus_size == 0:
            return

        self.doc_lens = []
        self.term_freqs = []
        self.doc_freqs = {}
        total_len = 0

        for chunk in chunks:
            tokens = self._tokenize(chunk.text)
            doc_len = len(tokens)
            self.doc_lens.append(doc_len)
            total_len += doc_len
            
            tf: Dict[str, int] = {}
            seen = set()
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
                if t not in seen:
                    self.doc_freqs[t] = self.doc_freqs.get(t, 0) + 1
                    seen.add(t)
            self.term_freqs.append(tf)

        self.avg_doc_len = total_len / float(self.corpus_size) if self.corpus_size > 0 else 0.0
        
        # Calculate IDF
        self.idf = {}
        for term, freq in self.doc_freqs.items():
            # Standard Lucene/BM25 formula
            self.idf[term] = math.log(1.0 + (self.corpus_size - freq + 0.5) / (freq + 0.5))

    def get_scores(self, query: str) -> List[float]:
        if self.corpus_size == 0:
            return []

        q_tokens = self._tokenize(query)
        scores = [0.0] * self.corpus_size

        for term in q_tokens:
            if term not in self.idf:
                continue
            idf_val = self.idf[term]
            for doc_idx, tf_dict in enumerate(self.term_freqs):
                freq = tf_dict.get(term, 0)
                if freq == 0:
                    continue
                doc_len = self.doc_lens[doc_idx]
                numerator = freq * (self.k1 + 1.0)
                denominator = freq + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_len))
                scores[doc_idx] += idf_val * (numerator / denominator)

        # Normalize BM25 scores between 0 and 1
        max_s = max(scores) if scores else 0.0
        if max_s > 0:
            scores = [s / max_s for s in scores]
        return scores


class HybridRetriever:
    """
    Enterprise Hybrid Retriever:
    1. Dense Vector Cosine Similarity (Semantic concepts & embeddings)
    2. Sparse Okapi BM25 (Exact terms, codes, part numbers, error codes)
    3. Reciprocal Rank Fusion (RRF) & Weighted Score Blending
    4. Maximal Marginal Relevance (MMR) for diversity
    """
    def __init__(
        self,
        vector_store: VectorStore,
        embedding_engine: EmbeddingEngine,
        alpha: float = 0.65, # 0.65 Dense, 0.35 Sparse
        top_k: int = 5,
        similarity_threshold: float = 0.25,
        enable_mmr: bool = True,
        mmr_diversity: float = 0.3
    ):
        self.vector_store = vector_store
        self.embedding_engine = embedding_engine
        self.alpha = alpha
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
        self.enable_mmr = enable_mmr
        self.mmr_diversity = mmr_diversity
        self.bm25 = BM25Index()
        self._sync_bm25()

    def _sync_bm25(self):
        chunks = self.vector_store.get_all_chunks()
        self.bm25.fit(chunks)

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        tracker: Optional[LatencyTracker] = None,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        k = top_k or self.top_k
        all_chunks = self.vector_store.get_all_chunks()
        if not all_chunks:
            return []

        # Ensure BM25 index is aligned with vector store
        if self.bm25.corpus_size != len(all_chunks):
            self._sync_bm25()

        # 1. Dense Semantic Search
        if tracker:
            tracker.start_stage("Dense_Query_Embedding")
        q_emb = self.embedding_engine.embed_query(query)

        if tracker:
            tracker.start_stage("Dense_Vector_Search")
        dense_results = self.vector_store.search(
            query_embedding=q_emb,
            top_k=len(all_chunks),
            threshold=0.0,
            metadata_filter=metadata_filter
        )
        dense_dict = {c.chunk_id: score for c, score in dense_results}

        # 2. Sparse BM25 Search
        if tracker:
            tracker.start_stage("Sparse_BM25_Search")
        bm25_scores = self.bm25.get_scores(query)

        # 3. Hybrid Fusion (Weighted Score Combination)
        if tracker:
            tracker.start_stage("Hybrid_Score_Fusion_and_Rerank")
        fused_scores: List[Tuple[Chunk, float, float, float]] = []

        for idx, chunk in enumerate(all_chunks):
            # Apply metadata filter
            if metadata_filter:
                match = True
                for fk, fv in metadata_filter.items():
                    if chunk.metadata.get(fk) != fv:
                        match = False
                        break
                if not match:
                    continue

            d_score = dense_dict.get(chunk.chunk_id, 0.0)
            s_score = bm25_scores[idx] if idx < len(bm25_scores) else 0.0
            
            # Hybrid combined score
            fused_score = (self.alpha * d_score) + ((1.0 - self.alpha) * s_score)
            
            if fused_score >= self.similarity_threshold or d_score >= self.similarity_threshold:
                fused_scores.append((chunk, fused_score, d_score, s_score))

        # Sort descending by fused score
        fused_scores.sort(key=lambda x: x[1], reverse=True)

        # 4. Optional Maximal Marginal Relevance (MMR)
        if self.enable_mmr and len(fused_scores) > k:
            selected = self._apply_mmr(fused_scores, q_emb, k)
        else:
            selected = fused_scores[:k]

        results = []
        for rank, (chunk, fused, dense, sparse) in enumerate(selected, 1):
            results.append(RetrievalResult(
                chunk=chunk,
                score=round(fused, 4),
                dense_score=round(dense, 4),
                sparse_score=round(sparse, 4),
                rank=rank
            ))

        if tracker:
            tracker.end_stage(retrieved_count=len(results), top_score=results[0].score if results else 0)

        return results

    def _apply_mmr(
        self,
        scored_chunks: List[Tuple[Chunk, float, float, float]],
        query_emb: List[float],
        k: int
    ) -> List[Tuple[Chunk, float, float, float]]:
        """Maximal Marginal Relevance (MMR) for retrieval diversity."""
        if not scored_chunks or k <= 0:
            return []

        selected: List[Tuple[Chunk, float, float, float]] = [scored_chunks[0]]
        candidates = scored_chunks[1:]
        q_vec = np.array(query_emb, dtype=np.float32)

        while len(selected) < k and candidates:
            best_mmr_score = -float("inf")
            best_idx = 0

            for i, cand in enumerate(candidates):
                sim_to_query = cand[1] # relevance score
                # Calculate max similarity to already selected chunks (redundancy penalty)
                max_sim_to_selected = 0.0
                cand_emb = np.array(self.embedding_engine.embed_text(cand[0].text), dtype=np.float32)
                for sel in selected:
                    sel_emb = np.array(self.embedding_engine.embed_text(sel[0].text), dtype=np.float32)
                    dot = float(np.dot(cand_emb, sel_emb))
                    if dot > max_sim_to_selected:
                        max_sim_to_selected = dot

                # MMR Equation: λ * Sim(D, Q) - (1-λ) * max(Sim(D, Dj))
                mmr_val = (1.0 - self.mmr_diversity) * sim_to_query - (self.mmr_diversity * max_sim_to_selected)
                if mmr_val > best_mmr_score:
                    best_mmr_score = mmr_val
                    best_idx = i

            selected.append(candidates.pop(best_idx))

        return selected
