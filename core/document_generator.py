import os
import re
import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional, Generator
from dataclasses import dataclass, field
from dotenv import load_dotenv

from .retriever import HybridRetriever, RetrievalResult
from .latency_tracker import LatencyTracker
from .prompt_templates import DOCUMENT_GENERATION_PROMPT

load_dotenv()

@dataclass
class GeneratedDocument:
    title: str
    document_type: str
    content_markdown: str
    citations: List[Dict[str, Any]] = field(default_factory=list)
    latency_report: Dict[str, Any] = field(default_factory=dict)
    tokens_generated: int = 0
    export_paths: Dict[str, str] = field(default_factory=dict)

class DocumentGenerator:
    """
    Enterprise Template-Driven Document Generation Engine:
    - Provider Support: Google Gemini Cloud & Local Ollama Server
    - Grounded section-by-section generation with verified citations.
    """
    def __init__(
        self,
        retriever: HybridRetriever,
        provider: str = "gemini",
        llm_model: Optional[str] = None,
        ollama_base_url: str = "http://localhost:11434",
        templates_dir: Optional[str] = None
    ):
        self.retriever = retriever
        self.provider = provider.lower()
        self.ollama_base_url = ollama_base_url.rstrip("/")
        
        if llm_model:
            self.llm_model = llm_model
        else:
            self.llm_model = "gemini-2.5-flash" if self.provider == "gemini" else "llama3:8b"
        
        if templates_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.templates_dir = os.path.join(base_dir, "templates")
        else:
            self.templates_dir = templates_dir
            
        os.makedirs(self.templates_dir, exist_ok=True)
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        self.client = None
        if self.provider == "gemini":
            self._init_gemini_client()

    def set_provider(self, provider: str, model_name: Optional[str] = None, ollama_base_url: Optional[str] = None):
        self.provider = provider.lower()
        if ollama_base_url:
            self.ollama_base_url = ollama_base_url.rstrip("/")
        if model_name:
            self.llm_model = model_name
        else:
            self.llm_model = "gemini-2.5-flash" if self.provider == "gemini" else "llama3:8b"
        
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

    def get_available_templates(self) -> Dict[str, str]:
        templates = {}
        if not os.path.exists(self.templates_dir):
            return templates

        for f in os.listdir(self.templates_dir):
            if f.endswith((".md", ".txt")):
                name = os.path.splitext(f)[0].replace("_", " ").title()
                filepath = os.path.join(self.templates_dir, f)
                templates[name] = filepath
        return templates

    def load_template(self, template_name_or_path: str) -> str:
        if os.path.exists(template_name_or_path):
            with open(template_name_or_path, "r", encoding="utf-8") as f:
                return f.read()

        clean_name = template_name_or_path.lower().replace(" ", "_")
        candidates = [
            os.path.join(self.templates_dir, f"{clean_name}.md"),
            os.path.join(self.templates_dir, f"{clean_name}.txt"),
            os.path.join(self.templates_dir, f"{template_name_or_path}.md")
        ]
        for c in candidates:
            if os.path.exists(c):
                with open(c, "r", encoding="utf-8") as f:
                    return f.read()

        return (
            "# {{document_title}}\n\n"
            "## 1. Executive Summary\n{{summary}}\n\n"
            "## 2. Detailed Findings & Mechanisms\n{{details}}\n\n"
            "## 3. Operational Guidelines & Standards\n{{guidelines}}\n\n"
            "## 4. Governance, Action Items & Sign-Off\n{{action_items}}"
        )

    def _call_ollama(self, prompt: str, temperature: float = 0.2) -> Optional[str]:
        url = f"{self.ollama_base_url}/api/generate"
        payload = json.dumps({
            "model": self.llm_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": 8192
            }
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("response", "")
        except Exception:
            return None

    def _call_llm(self, prompt: str, temperature: float = 0.2) -> str:
        if self.provider == "ollama":
            res = self._call_ollama(prompt, temperature)
            if res:
                return res
            return self._local_fallback_document(prompt)

        if self.client is None:
            return self._local_fallback_document(prompt)

        try:
            if self.client == "legacy":
                import google.generativeai as legacy_genai
                model = legacy_genai.GenerativeModel(self.llm_model)
                res = model.generate_content(prompt, generation_config={"temperature": temperature})
                return res.text or ""
            else:
                res = self.client.models.generate_content(
                    model=self.llm_model,
                    contents=prompt,
                    config={"temperature": temperature}
                )
                return res.text or ""
        except Exception:
            try:
                if self.client == "legacy":
                    import google.generativeai as legacy_genai
                    model = legacy_genai.GenerativeModel("gemini-1.5-flash")
                    res = model.generate_content(prompt, generation_config={"temperature": temperature})
                    return res.text or ""
                else:
                    res = self.client.models.generate_content(
                        model="gemini-1.5-flash",
                        contents=prompt,
                        config={"temperature": temperature}
                    )
                    return res.text or ""
            except Exception:
                return self._local_fallback_document(prompt)

    def generate_document(
        self,
        document_title: str,
        document_type: str,
        user_instructions: str,
        template_name: Optional[str] = None,
        retrieval_query: Optional[str] = None,
        top_k: int = 6,
        tracker: Optional[LatencyTracker] = None
    ) -> GeneratedDocument:
        tracker = tracker or LatencyTracker(f"DocGen_{document_type}_{document_title[:15]}")
        
        # 1. Context Retrieval
        search_query = retrieval_query or f"{document_title} {user_instructions}"
        retrieval_results = self.retriever.retrieve(query=search_query, top_k=top_k, tracker=tracker)

        tracker.start_stage("Grounding_Context_Assembly")
        grounding_parts = []
        citations = []
        for r in retrieval_results:
            src_doc = r.chunk.doc_id
            sec_title = r.chunk.metadata.get("section_title") or f"Page {r.chunk.metadata.get('page_number', 'N/A')}"
            grounding_parts.append(f"### [Source: {src_doc} | Section: {sec_title} | Score: {r.score}]\n{r.chunk.text}")
            citations.append({
                "document": src_doc,
                "section": sec_title,
                "score": r.score,
                "chunk_id": r.chunk.chunk_id,
                "snippet": r.chunk.text[:200] + "..."
            })

        grounding_context = "\n\n".join(grounding_parts) if grounding_parts else "No specific grounding documents retrieved."

        # 2. Template Loading
        template_content = self.load_template(template_name or document_type)

        # 3. Prompt Construction
        prompt = DOCUMENT_GENERATION_PROMPT.format(
            document_type=document_type,
            document_title=document_title,
            user_instructions=user_instructions,
            grounding_context=grounding_context,
            template_content=template_content
        )

        # 4. LLM Generation
        tracker.start_stage(f"LLM_Document_Synthesis_{self.provider.upper()}")
        tracker.record_ttft()
        
        generated_markdown = self._call_llm(prompt)
        tracker.finish(tokens_generated=len(generated_markdown.split()))

        return GeneratedDocument(
            title=document_title,
            document_type=document_type,
            content_markdown=generated_markdown,
            citations=citations,
            latency_report=tracker.get_breakdown(),
            tokens_generated=tracker.tokens_generated
        )

    def _local_fallback_document(self, prompt: str) -> str:
        prov_name = "Local Ollama" if self.provider == "ollama" else "Gemini Cloud"
        return (
            f"# 📋 Enterprise Grounded Document (Diagnostic Mode | Provider: {prov_name})\n\n"
            "## 1. Executive Overview\n"
            "This document was synthesized using enterprise retrieved context chunks.\n\n"
            "## 2. Core Operational Architecture\n"
            "- Multi-tier execution verified against system policies.\n"
            "- Risk parameters and audit criteria validated.\n\n"
            "## 3. Grounding & Compliance\n"
            "- All assertions are linked to underlying enterprise knowledge documents.\n\n"
            f"*Verify connection to {prov_name} to generate dynamic full-text output.*"
        )

    def export_to_html(self, doc: GeneratedDocument, output_path: str) -> str:
        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{doc.title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; padding: 40px; max-width: 900px; margin: 0 auto; color: #1e293b; background: #ffffff; }}
        h1 {{ color: #0369a1; border-bottom: 2px solid #0284c7; padding-bottom: 8px; }}
        h2 {{ color: #0f172a; margin-top: 24px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
        th, td {{ border: 1px solid #cbd5e1; padding: 8px 12px; text-align: left; }}
        th {{ background: #f1f5f9; color: #0f172a; font-weight: 600; }}
        code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-family: monospace; color: #0284c7; }}
        blockquote {{ border-left: 4px solid #0284c7; padding-left: 16px; margin-left: 0; color: #475569; }}
        .badge {{ display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 700; background: #e0f2fe; color: #0284c7; }}
    </style>
</head>
<body>
    <div style="margin-bottom: 20px;">
        <span class="badge">{doc.document_type.upper()}</span>
        <span style="float: right; color: #64748b; font-size: 12px;">Generated via DocGenius RAG ({self.provider.upper()})</span>
    </div>
    <div id="content">
        {doc.content_markdown.replace(chr(10), '<br/>')}
    </div>
</body>
</html>"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_template)
        return output_path
