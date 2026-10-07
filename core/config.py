import os
import yaml
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class ModelsConfig:
    llm_model: str = "gemini-2.5-flash"
    fallback_llm_model: str = "gemini-1.5-flash"
    embedding_model: str = "text-embedding-004"
    temperature: float = 0.2
    max_output_tokens: int = 4096

@dataclass
class OllamaConfig:
    base_url: str = "http://localhost:11434"
    llm_model: str = "llama3:8b"
    embedding_model: str = "nomic-embed-text"
    timeout_seconds: int = 60
    temperature: float = 0.2
    num_ctx: int = 8192

@dataclass
class RAGConfig:
    chunk_size: int = 600
    chunk_overlap: int = 120
    top_k: int = 5
    similarity_threshold: float = 0.35
    hybrid_alpha: float = 0.65
    enable_mmr: bool = True
    mmr_diversity: float = 0.3

@dataclass
class SummarizationConfig:
    default_strategy: str = "map_reduce"
    map_chunk_size: int = 1500
    max_parallel_calls: int = 5
    stuff_max_tokens: int = 8000

@dataclass
class GenerationConfig:
    strict_grounding: bool = True
    hallucination_guardrail: bool = True
    export_formats: List[str] = field(default_factory=lambda: ["markdown", "html", "txt"])

@dataclass
class LatencyTrackingConfig:
    enabled: bool = True
    slow_query_threshold_ms: int = 3000
    log_breakdowns: bool = True

@dataclass
class AppConfig:
    name: str = "DocGenius RAG Studio"
    version: str = "1.1.0"
    description: str = "Enterprise Document Generation & Summarization RAG"
    provider: str = "gemini" # "gemini" or "ollama"
    models: ModelsConfig = field(default_factory=ModelsConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    summarization: SummarizationConfig = field(default_factory=SummarizationConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    latency_tracking: LatencyTrackingConfig = field(default_factory=LatencyTrackingConfig)

def load_config(config_path: Optional[str] = None) -> AppConfig:
    if config_path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "config.yaml")
    
    if not os.path.exists(config_path):
        return AppConfig()
    
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    
    app_data = data.get("app", {})
    provider = data.get("provider", "gemini")
    models_data = data.get("models", {})
    ollama_data = data.get("ollama", {})
    rag_data = data.get("rag", {})
    summ_data = data.get("summarization", {})
    gen_data = data.get("generation", {})
    lat_data = data.get("latency_tracking", {})

    return AppConfig(
        name=app_data.get("name", "DocGenius RAG Studio"),
        version=app_data.get("version", "1.1.0"),
        description=app_data.get("description", "Enterprise Document Generation & Summarization RAG"),
        provider=provider,
        models=ModelsConfig(**models_data) if models_data else ModelsConfig(),
        ollama=OllamaConfig(**ollama_data) if ollama_data else OllamaConfig(),
        rag=RAGConfig(**rag_data) if rag_data else RAGConfig(),
        summarization=SummarizationConfig(**summ_data) if summ_data else SummarizationConfig(),
        generation=GenerationConfig(**gen_data) if gen_data else GenerationConfig(),
        latency_tracking=LatencyTrackingConfig(**lat_data) if lat_data else LatencyTrackingConfig()
    )
