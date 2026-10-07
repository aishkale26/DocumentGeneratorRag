import os
import json
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import asdict
from .chunker import Chunk

class VectorStore:
    """
    High-Performance, Zero-External-Dependency Vector Store.
    Uses vectorized NumPy matrix operations for sub-millisecond similarity search
    with persistent disk serialization and metadata filtering.
    """
    def __init__(self, persist_dir: Optional[str] = None):
        if persist_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.persist_dir = os.path.join(base_dir, ".cache", "vector_store")
        else:
            self.persist_dir = persist_dir

        os.makedirs(self.persist_dir, exist_ok=True)
        self.chunks: List[Chunk] = []
        self.embeddings: Optional[np.ndarray] = None # Shape: (N, D)
        self.index_file = os.path.join(self.persist_dir, "index_meta.json")
        self.matrix_file = os.path.join(self.persist_dir, "embeddings.npy")
        self.load()

    def add_chunks(self, chunks: List[Chunk], embeddings: List[List[float]]):
        if not chunks or not embeddings:
            return

        new_embeddings = np.array(embeddings, dtype=np.float32)
        # Ensure unit normalization for fast dot product = cosine similarity
        norms = np.linalg.norm(new_embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        new_embeddings = new_embeddings / norms

        if self.embeddings is None or len(self.chunks) == 0:
            self.embeddings = new_embeddings
            self.chunks = list(chunks)
        else:
            self.embeddings = np.vstack([self.embeddings, new_embeddings])
            self.chunks.extend(chunks)

        self.save()

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        threshold: float = 0.0,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Chunk, float]]:
        if self.embeddings is None or len(self.chunks) == 0:
            return []

        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        # Vectorized dot product cosine similarity
        scores = np.dot(self.embeddings, q_vec)

        # Apply metadata filtering if specified
        valid_indices = []
        for idx, chunk in enumerate(self.chunks):
            if metadata_filter:
                match = True
                for k, v in metadata_filter.items():
                    if chunk.metadata.get(k) != v and getattr(chunk, k, None) != v:
                        match = False
                        break
                if not match:
                    continue
            
            if scores[idx] >= threshold:
                valid_indices.append(idx)

        if not valid_indices:
            return []

        # Sort top-k matches
        valid_indices = sorted(valid_indices, key=lambda i: scores[i], reverse=True)[:top_k]
        results = [(self.chunks[i], float(scores[i])) for i in valid_indices]
        return results

    def get_all_chunks(self) -> List[Chunk]:
        return self.chunks

    def get_document_chunks(self, doc_id: str) -> List[Chunk]:
        return [c for c in self.chunks if c.doc_id == doc_id or c.metadata.get("doc_id") == doc_id]

    def delete_document(self, doc_id: str):
        if not self.chunks:
            return

        keep_indices = [i for i, c in enumerate(self.chunks) if c.doc_id != doc_id and c.metadata.get("doc_id") != doc_id]
        if len(keep_indices) == len(self.chunks):
            return

        self.chunks = [self.chunks[i] for i in keep_indices]
        if keep_indices and self.embeddings is not None:
            self.embeddings = self.embeddings[keep_indices]
        else:
            self.embeddings = None
        self.save()

    def clear(self):
        self.chunks = []
        self.embeddings = None
        if os.path.exists(self.index_file):
            os.remove(self.index_file)
        if os.path.exists(self.matrix_file):
            os.remove(self.matrix_file)

    def save(self):
        if not self.chunks or self.embeddings is None:
            return

        serialized_chunks = [
            {
                "chunk_id": c.chunk_id,
                "doc_id": c.doc_id,
                "text": c.text,
                "metadata": c.metadata
            }
            for c in self.chunks
        ]
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(serialized_chunks, f, indent=2)

        np.save(self.matrix_file, self.embeddings)

    def load(self):
        if os.path.exists(self.index_file) and os.path.exists(self.matrix_file):
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    serialized = json.load(f)
                    self.chunks = [Chunk(**c) for c in serialized]
                self.embeddings = np.load(self.matrix_file)
            except Exception:
                self.chunks = []
                self.embeddings = None
