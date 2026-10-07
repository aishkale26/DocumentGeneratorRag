import os
import hashlib
import json
import urllib.request
import urllib.error
import numpy as np
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

class EmbeddingEngine:
    """
    Enterprise Embedding Engine supporting:
    1. Google Gemini Embeddings (e.g. text-embedding-004, 768 dims).
    2. Local Ollama Embeddings (e.g. nomic-embed-text, mxbai-embed-large, all-minilm).
    3. High-speed In-Memory & Disk Hash Caching (sub-millisecond repeat queries).
    4. Resilient Pure-Python Fallback Vectorizer.
    """
    def __init__(
        self,
        provider: str = "gemini",
        model_name: Optional[str] = None,
        ollama_base_url: str = "http://localhost:11434",
        cache_dir: Optional[str] = None
    ):
        self.provider = provider.lower() # "gemini" or "ollama"
        self.ollama_base_url = ollama_base_url.rstrip("/")
        
        if model_name:
            self.model_name = model_name
        else:
            self.model_name = "text-embedding-004" if self.provider == "gemini" else "nomic-embed-text"

        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        self.memory_cache: Dict[str, List[float]] = {}
        
        if cache_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.cache_dir = os.path.join(base_dir, ".cache", "embeddings")
        else:
            self.cache_dir = cache_dir
            
        os.makedirs(self.cache_dir, exist_ok=True)
        self.client = None
        if self.provider == "gemini":
            self._init_gemini_client()

    def set_provider(self, provider: str, model_name: Optional[str] = None):
        self.provider = provider.lower()
        if model_name:
            self.model_name = model_name
        else:
            self.model_name = "text-embedding-004" if self.provider == "gemini" else "nomic-embed-text"
        
        if self.provider == "gemini":
            self._init_gemini_client()

    def _init_gemini_client(self):
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception:
                try:
                    import google.generativeai as legacy_genai
                    legacy_genai.configure(api_key=self.api_key)
                    self.client = "legacy"
                except Exception:
                    self.client = None

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(f"{self.provider}_{self.model_name}_{text.strip()}".encode("utf-8")).hexdigest()

    def _get_from_cache(self, text: str) -> Optional[List[float]]:
        h = self._hash_text(text)
        if h in self.memory_cache:
            return self.memory_cache[h]
        
        disk_path = os.path.join(self.cache_dir, f"{h}.json")
        if os.path.exists(disk_path):
            try:
                with open(disk_path, "r", encoding="utf-8") as f:
                    emb = json.load(f)
                    self.memory_cache[h] = emb
                    return emb
            except Exception:
                pass
        return None

    def _save_to_cache(self, text: str, embedding: List[float]):
        h = self._hash_text(text)
        self.memory_cache[h] = embedding
        disk_path = os.path.join(self.cache_dir, f"{h}.json")
        try:
            with open(disk_path, "w", encoding="utf-8") as f:
                json.dump(embedding, f)
        except Exception:
            pass

    def _embed_ollama(self, text: str) -> Optional[List[float]]:
        """Call local Ollama embeddings endpoint."""
        url = f"{self.ollama_base_url}/api/embeddings"
        payload = json.dumps({"model": self.model_name, "prompt": text}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                emb = data.get("embedding", [])
                if emb:
                    norm = np.linalg.norm(emb)
                    if norm > 0:
                        emb = (np.array(emb) / norm).tolist()
                    return emb
        except Exception:
            # Try new Ollama /api/embed endpoint
            try:
                embed_url = f"{self.ollama_base_url}/api/embed"
                embed_payload = json.dumps({"model": self.model_name, "input": text}).encode("utf-8")
                req2 = urllib.request.Request(embed_url, data=embed_payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req2, timeout=15) as resp2:
                    data2 = json.loads(resp2.read().decode("utf-8"))
                    embs = data2.get("embeddings", [])
                    if embs and len(embs) > 0:
                        emb = embs[0]
                        norm = np.linalg.norm(emb)
                        if norm > 0:
                            emb = (np.array(emb) / norm).tolist()
                        return emb
            except Exception:
                pass
        return None

    def embed_text(self, text: str) -> List[float]:
        cached = self._get_from_cache(text)
        if cached is not None:
            return cached

        # 1. Local Ollama Provider
        if self.provider == "ollama":
            emb = self._embed_ollama(text)
            if emb is not None:
                self._save_to_cache(text, emb)
                return emb

        # 2. Gemini Cloud Provider
        elif self.provider == "gemini" and self.client is not None:
            try:
                if self.client == "legacy":
                    import google.generativeai as legacy_genai
                    res = legacy_genai.embed_content(
                        model=f"models/{self.model_name}",
                        content=text,
                        task_type="retrieval_document"
                    )
                    emb = res["embedding"]
                else:
                    res = self.client.models.embed_content(
                        model=self.model_name,
                        contents=text
                    )
                    if hasattr(res, "embedding") and hasattr(res.embedding, "values"):
                        emb = list(res.embedding.values)
                    elif hasattr(res, "embeddings") and len(res.embeddings) > 0:
                        emb = list(res.embeddings[0].values)
                    else:
                        emb = list(res.embedding)

                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb = (np.array(emb) / norm).tolist()
                
                self._save_to_cache(text, emb)
                return emb
            except Exception:
                pass

        # 3. Resilient Local Fallback Embedder
        emb = self._local_fallback_embedding(text)
        self._save_to_cache(text, emb)
        return emb

    def embed_query(self, query: str) -> List[float]:
        cached = self._get_from_cache(f"query::{query}")
        if cached is not None:
            return cached

        if self.provider == "ollama":
            emb = self._embed_ollama(query)
            if emb is not None:
                self._save_to_cache(f"query::{query}", emb)
                return emb

        elif self.provider == "gemini" and self.client is not None:
            try:
                if self.client == "legacy":
                    import google.generativeai as legacy_genai
                    res = legacy_genai.embed_content(
                        model=f"models/{self.model_name}",
                        content=query,
                        task_type="retrieval_query"
                    )
                    emb = res["embedding"]
                else:
                    res = self.client.models.embed_content(
                        model=self.model_name,
                        contents=query
                    )
                    if hasattr(res, "embedding") and hasattr(res.embedding, "values"):
                        emb = list(res.embedding.values)
                    elif hasattr(res, "embeddings") and len(res.embeddings) > 0:
                        emb = list(res.embeddings[0].values)
                    else:
                        emb = list(res.embedding)

                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb = (np.array(emb) / norm).tolist()

                self._save_to_cache(f"query::{query}", emb)
                return emb
            except Exception:
                pass

        emb = self._local_fallback_embedding(query)
        self._save_to_cache(f"query::{query}", emb)
        return emb

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        for t in texts:
            embeddings.append(self.embed_text(t))
        return embeddings

    def _local_fallback_embedding(self, text: str, dim: int = 768) -> List[float]:
        """Deterministic Subword Hashing Vectorizer for offline execution."""
        words = text.lower().split()
        vec = np.zeros(dim, dtype=np.float32)
        if not words:
            return vec.tolist()

        for w in words:
            h_word = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16) % dim
            vec[h_word] += 1.0
            if len(w) >= 3:
                for i in range(len(w) - 2):
                    ng = w[i:i+3]
                    h_ng = int(hashlib.md5(ng.encode("utf-8")).hexdigest(), 16) % dim
                    vec[h_ng] += 0.5

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()
