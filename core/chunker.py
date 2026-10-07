import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from .document_loader import LoadedDocument

@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def token_count(self) -> int:
        return self.metadata.get("token_count", len(self.text.split()))

class SemanticChunker:
    """
    Intelligent Chunking Engine supporting:
    1. Recursive Token & Paragraph splitting with customizable overlap.
    2. Header-Aware Markdown Semantic splitting (preserves breadcrumb hierarchies).
    3. Document Structure metadata tagging.
    """
    def __init__(self, chunk_size: int = 600, chunk_overlap: int = 120):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(self, doc: LoadedDocument) -> List[Chunk]:
        if doc.file_type in ["markdown", "md"]:
            return self._chunk_markdown(doc)
        elif doc.sections and doc.file_type == "pdf":
            return self._chunk_pdf_sections(doc)
        else:
            return self._chunk_text(doc.content, doc.filename)

    def _chunk_text(self, text: str, doc_id: str, base_meta: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        base_meta = base_meta or {}
        if not text.strip():
            return []

        # Split into logical paragraphs first
        paragraphs = re.split(r'\n\s*\n', text)
        chunks: List[Chunk] = []
        current_words: List[str] = []
        current_word_count = 0
        target_words = int(self.chunk_size * 0.75) # ~0.75 words per token
        overlap_words = int(self.chunk_overlap * 0.75)

        for p in paragraphs:
            p_words = p.split()
            if not p_words:
                continue

            if current_word_count + len(p_words) <= target_words:
                current_words.extend(p_words)
                current_word_count += len(p_words)
            else:
                # If single paragraph is longer than target_words, split sentences
                if not current_words:
                    sentences = re.split(r'(?<=[.?!])\s+', p)
                    for s in sentences:
                        s_words = s.split()
                        if current_word_count + len(s_words) <= target_words:
                            current_words.extend(s_words)
                            current_word_count += len(s_words)
                        else:
                            if current_words:
                                chunk_text = " ".join(current_words)
                                c_idx = len(chunks) + 1
                                meta = {
                                    **base_meta,
                                    "doc_id": doc_id,
                                    "chunk_index": c_idx,
                                    "word_count": len(current_words),
                                    "token_count": int(len(current_words) * 1.33)
                                }
                                chunks.append(Chunk(
                                    chunk_id=f"{doc_id}_chunk_{c_idx}",
                                    doc_id=doc_id,
                                    text=chunk_text,
                                    metadata=meta
                                ))
                                current_words = current_words[-overlap_words:] if overlap_words > 0 else []
                                current_word_count = len(current_words)
                            current_words.extend(s_words)
                            current_word_count += len(s_words)
                else:
                    chunk_text = " ".join(current_words)
                    c_idx = len(chunks) + 1
                    meta = {
                        **base_meta,
                        "doc_id": doc_id,
                        "chunk_index": c_idx,
                        "word_count": len(current_words),
                        "token_count": int(len(current_words) * 1.33)
                    }
                    chunks.append(Chunk(
                        chunk_id=f"{doc_id}_chunk_{c_idx}",
                        doc_id=doc_id,
                        text=chunk_text,
                        metadata=meta
                    ))
                    # Retain overlap from end of previous chunk
                    current_words = current_words[-overlap_words:] if overlap_words > 0 else []
                    current_words.extend(p_words)
                    current_word_count = len(current_words)

        if current_words:
            chunk_text = " ".join(current_words)
            c_idx = len(chunks) + 1
            meta = {
                **base_meta,
                "doc_id": doc_id,
                "chunk_index": c_idx,
                "word_count": len(current_words),
                "token_count": int(len(current_words) * 1.33)
            }
            chunks.append(Chunk(
                chunk_id=f"{doc_id}_chunk_{c_idx}",
                doc_id=doc_id,
                text=chunk_text,
                metadata=meta
            ))

        # Update total chunks count in metadata
        for c in chunks:
            c.metadata["total_chunks"] = len(chunks)

        return chunks

    def _chunk_markdown(self, doc: LoadedDocument) -> List[Chunk]:
        all_chunks: List[Chunk] = []
        if not doc.sections:
            return self._chunk_text(doc.content, doc.filename, {"file_type": "markdown"})
        
        for sec in doc.sections:
            sec_title = sec.get("title", "General")
            sec_text = sec.get("text", "")
            if not sec_text.strip():
                continue
            
            sec_meta = {
                "file_type": "markdown",
                "section_title": sec_title,
                "doc_id": doc.filename
            }
            # Prepend section title context to chunk text for better semantic search
            enriched_text = f"## {sec_title}\n\n{sec_text}"
            sec_chunks = self._chunk_text(enriched_text, doc.filename, sec_meta)
            all_chunks.extend(sec_chunks)

        # Re-index chunks
        for idx, c in enumerate(all_chunks):
            c.chunk_id = f"{doc.filename}_chunk_{idx+1}"
            c.metadata["chunk_index"] = idx + 1
            c.metadata["total_chunks"] = len(all_chunks)

        return all_chunks

    def _chunk_pdf_sections(self, doc: LoadedDocument) -> List[Chunk]:
        all_chunks: List[Chunk] = []
        for sec in doc.sections:
            page_num = sec.get("page_number", 1)
            page_text = sec.get("text", "")
            if not page_text.strip():
                continue
            
            page_meta = {
                "file_type": "pdf",
                "page_number": page_num,
                "doc_id": doc.filename
            }
            page_chunks = self._chunk_text(page_text, doc.filename, page_meta)
            all_chunks.extend(page_chunks)

        for idx, c in enumerate(all_chunks):
            c.chunk_id = f"{doc.filename}_chunk_{idx+1}"
            c.metadata["chunk_index"] = idx + 1
            c.metadata["total_chunks"] = len(all_chunks)

        return all_chunks
