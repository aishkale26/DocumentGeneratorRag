"""
Enterprise Prompt Templates for Document Generation and Multi-Strategy Summarization.
"""

STUFF_SUMMARIZATION_PROMPT = """You are an expert executive document analyst.
Summarize the following document accurately and thoroughly.

STRICT REQUIREMENTS:
1. Executive Summary: Provide a 2-3 paragraph high-level overview.
2. Key Pillars & Takeaways: Extract core facts, metrics, policies, or operational mechanisms using bullet points.
3. Critical Findings / Action Items: Identify any deadlines, responsibilities, risks, or compliance requirements.
4. Factual Grounding: Do NOT invent facts or extrapolate beyond what is explicitly stated in the document.

DOCUMENT CONTENT:
---
{document_content}
---

Provide a well-structured Markdown summary:"""

MAP_CHUNK_PROMPT = """You are an expert document summarizer.
Analyze the following section (Chunk {chunk_index} of {total_chunks}) from document '{doc_id}'.

SECTION CONTENT:
---
{chunk_text}
---

TASK:
Extract and concisely summarize the essential key points, data metrics, rules, procedures, and findings from this section.
Keep the summary informative, dense with facts, and devoid of filler words. Bullet points are preferred."""

REDUCE_SYNTHESIS_PROMPT = """You are an elite corporate intelligence synthesizer.
You have been provided with individual section summaries from the document '{doc_id}'.

SECTION SUMMARIES:
---
{intermediate_summaries}
---

TASK:
Synthesize these individual section summaries into a single, cohesive, comprehensive Master Executive Summary.

STRUCTURE YOUR OUTPUT AS FOLLOWS:
# 📑 Master Executive Summary: {doc_id}

## 1. Executive Briefing
(Concise synthesis of the document's core purpose, scope, and primary objectives)

## 2. Core Operational / Functional Highlights
(Detailed thematic breakdown of all mechanisms, rules, numbers, and key operational items discussed)

## 3. Key Findings, Policies & Metrics
(Bulleted table or list of specific facts, statutory requirements, thresholds, and technical/business figures)

## 4. Risks, Dependencies & Recommended Action Items
(Actionable next steps, risk mitigation protocols, and responsible stakeholders)

Ensure the synthesis flows logically, eliminates redundancy, and preserves all vital metrics."""

REFINE_INITIAL_PROMPT = """You are an expert document analyst.
Produce a comprehensive initial summary for the opening section of '{doc_id}'.

SECTION CONTENT:
---
{chunk_text}
---

Provide a structured summary of the key facts, objectives, and findings from this first section:"""

REFINE_ITERATIVE_PROMPT = """You are an expert document analyst refining an ongoing document summary.

CURRENT CONSOLIDATED SUMMARY:
---
{existing_summary}
---

NEW SECTION CONTENT (Section {chunk_index} of {total_chunks}):
---
{chunk_text}
---

TASK:
Incorporate the new facts, updates, and findings from the new section into the consolidated summary.
Refine the summary so that it remains a coherent, structured, non-repetitive narrative reflecting the entire document up to this point."""

QUERY_FOCUSED_SUMMARIZATION_PROMPT = """You are a domain research assistant.
Answer the specific user query by summarizing ONLY the relevant facts from the provided context chunks.

TARGET QUERY / TOPIC:
"{user_query}"

RETRIEVED CONTEXT CHUNKS:
---
{context_text}
---

REQUIREMENTS:
1. Focus directly on the query topic. Ignore unrelated context.
2. Cite the source document and section/page for every key assertion (e.g. `[DocName, Section/Page]`).
3. If the context does not contain sufficient details to answer the query, clearly state what information is missing instead of hallucinating.
4. Format output in structured Markdown with bullet points and bold highlights."""

DOCUMENT_GENERATION_PROMPT = """You are an enterprise technical writer and business architect.
Your task is to draft a comprehensive, publication-ready **{document_type}** titled **"{document_title}"**.

TARGET SPECIFICATIONS & USER INSTRUCTIONS:
{user_instructions}

RETRIEVED GROUNDING CONTEXT:
---
{grounding_context}
---

DOCUMENT TEMPLATE & STRUCTURE:
---
{template_content}
---

STRICT ENTERPRISE GUIDELINES:
1. Grounding & Citations: Fill every section of the template thoroughly using facts, metrics, and procedures from the retrieved grounding context.
2. Maintain professional, precise, and authoritative tone suitable for C-level executives and technical audit teams.
3. Wherever data or metrics are cited from the context, include clear source tags (e.g. `[Source: DocumentName]`).
4. Replace all template placeholders (`{{...}}` or `[...]`) with real synthesized content.
5. Render clean tables, code blocks, and formatted lists where appropriate.
6. Do NOT leave any sections empty or incomplete."""
