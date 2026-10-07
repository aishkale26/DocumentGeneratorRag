import os
import re
import json
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

from .db_connector import SecurePostgresConnector, DatabaseConfig
from .latency_tracker import LatencyTracker

load_dotenv()

NL2SQL_SYSTEM_PROMPT = """You are an expert, security-certified PostgreSQL Database Agent.
Your task is to convert the user's natural language question into a single, syntactically correct, read-only PostgreSQL SELECT query.

DATABASE SCHEMA:
---
{schema_ddl}
---

STRICT SECURITY & GENERATION RULES:
1. Generate ONLY a single read-only `SELECT` query. Never generate `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `GRANT`, or `EXEC`.
2. Wrap table and column names accurately according to the schema provided.
3. For user lookups, support case-insensitive matching using `ILIKE` or `LOWER(column) = LOWER('value')` or substring match `%value%`.
4. Enforce a safe `LIMIT 20` unless the user specifies a lower count.
5. Return ONLY the raw SQL statement inside a markdown code block ```sql ... ``` without any extraneous commentary.

USER QUERY:
"{user_query}"
"""

SQL_SUMMARIZATION_PROMPT = """You are an enterprise business intelligence analyst.
Summarize the database query results clearly and concisely for the user.

USER'S ORIGINAL QUESTION:
"{user_query}"

EXECUTED SQL QUERY:
`{sql_query}`

RETRIEVED DATABASE RECORDS (JSON):
---
{records_json}
---

INSTRUCTIONS:
1. Directly answer the user's specific question based strictly on the retrieved records.
2. If multiple records are returned, format them in a clean Markdown table.
3. Highlight any critical data points.
4. If no records were found, explain clearly and suggest verifying the search key or table schema.
"""

class SecureSQLAgent:
    """
    Secure Natural Language to SQL (NL2SQL) & Database Summarization Agent:
    1. Schema-Grounded SQL Generation (via Gemini or Ollama).
    2. AST / Regex SQL Sanitization & Dynamic PII Masking.
    3. Safe Query Execution.
    4. Dynamic Result Synthesis.
    """
    def __init__(
        self,
        db_connector: Optional[SecurePostgresConnector] = None,
        provider: str = "gemini",
        llm_model: str = "gemini-2.5-flash",
        ollama_base_url: str = "http://localhost:11434"
    ):
        self.db = db_connector or SecurePostgresConnector()
        self.provider = provider
        self.llm_model = llm_model
        self.ollama_base_url = ollama_base_url

    def set_provider(
        self,
        provider: str,
        model_name: Optional[str] = None,
        llm_model: Optional[str] = None,
        ollama_base_url: Optional[str] = None,
        **kwargs
    ):
        """Switches inference backend between Gemini and Ollama."""
        self.provider = provider
        selected_model = model_name or llm_model
        if selected_model:
            self.llm_model = selected_model
        if ollama_base_url:
            self.ollama_base_url = ollama_base_url

    def _call_llm(self, prompt: str) -> str:
        """Invokes the active LLM backend."""
        if self.provider == "gemini":
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                return ""
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=self.llm_model,
                    contents=prompt
                )
                return response.text or ""
            except Exception as e:
                print(f"[SecureSQLAgent] Gemini LLM Error: {e}")
                return ""
        elif self.provider == "ollama":
            try:
                import urllib.request
                import json
                base_url = self.ollama_base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
                req = urllib.request.Request(
                    f"{base_url}/api/generate",
                    data=json.dumps({
                        "model": self.llm_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.1}
                    }).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data.get("response", "")
            except Exception as e:
                print(f"[SecureSQLAgent] Ollama Error: {e}")
                return ""
        return ""

    def generate_sql(self, user_query: str) -> str:
        """
        Translates a natural language user query into a safe SELECT SQL query
        grounded in the active database schema.
        """
        schema_ddl = self.db.get_schema_ddl()
        prompt = NL2SQL_SYSTEM_PROMPT.format(
            schema_ddl=schema_ddl,
            user_query=user_query
        )

        response_text = self._call_llm(prompt)
        
        # Extract SQL from code block
        match = re.search(r"```(?:sql)?\s*(.*?)\s*```", response_text, re.DOTALL | re.IGNORECASE)
        if match:
            raw_sql = match.group(1).strip()
        else:
            raw_sql = response_text.strip()

        # If LLM is offline or returns empty, generate generic query from schema
        if not raw_sql or not raw_sql.upper().startswith("SELECT"):
            raw_sql = self._schema_based_fallback(user_query)

        return raw_sql

    def _schema_based_fallback(self, query: str) -> str:
        """Dynamic schema-based fallback when LLM is unavailable."""
        schema = self.db.get_schema_ddl()
        tables = re.findall(r"CREATE\s+TABLE\s+([a-zA-Z0-9_\.\"]+)", schema, re.IGNORECASE)
        if tables:
            first_tbl = tables[0]
            return f"SELECT * FROM {first_tbl} LIMIT 10"
        return "SELECT current_database(), current_user, version();"

    def answer_and_summarize(
        self,
        user_query: str,
        mask_pii: bool = True,
        tracker: Optional[LatencyTracker] = None
    ) -> Dict[str, Any]:
        """
        Complete Text-to-SQL + Database Summarization pipeline:
        1. NL2SQL translation.
        2. Execution against database with security validation & PII masking.
        3. Conversational grounded summarization.
        """
        tracker = tracker or LatencyTracker(f"NL2SQL_{user_query[:15]}")
        
        # 1. Generate SQL
        tracker.start_stage("NL2SQL_Generation")
        sql_query = self.generate_sql(user_query)

        # 2. Execute SQL
        tracker.start_stage("Secure_SQL_Execution")
        db_result = self.db.execute_safe_query(sql_query, mask_pii=mask_pii)

        # 3. Summarize Results
        tracker.start_stage("SQL_Result_Summarization")
        if not db_result["success"]:
            summary = f"❌ **Database Query Blocked or Connection Error:**\n\n`{db_result['error']}`\n\n*Executed SQL:* `{sql_query}`"
        elif not db_result["rows"]:
            summary = f"ℹ️ **No matching records found** in database for query: *'{user_query}'*.\n\n*Executed SQL:* `{db_result['sql']}`"
        else:
            records_json = json.dumps(db_result["rows"], indent=2)
            summary_prompt = SQL_SUMMARIZATION_PROMPT.format(
                user_query=user_query,
                sql_query=db_result["sql"],
                records_json=records_json
            )
            tracker.record_ttft()
            summary = self._call_llm(summary_prompt)
            if not summary:
                # Built-in dynamic structured formatter
                first_row = db_result["rows"][0]
                fields_md = "\n".join([f"- **{k}:** `{v}`" for k, v in first_row.items()])
                summary = (
                    f"### 📋 Retrieved Database Record(s) ({len(db_result['rows'])} row(s))\n\n"
                    f"{fields_md}\n\n"
                    f"*Executed SQL:* `{db_result['sql']}`"
                )

        tracker.finish(tokens_generated=len(summary.split()))

        return {
            "user_query": user_query,
            "generated_sql": sql_query,
            "executed_sql": db_result.get("sql", sql_query),
            "success": db_result["success"],
            "row_count": db_result.get("row_count", 0),
            "rows": db_result.get("rows", []),
            "columns": db_result.get("columns", []),
            "summary_text": summary,
            "latency_report": tracker.get_breakdown()
        }
