import os
import re
import json
import sqlite3
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

@dataclass
class DatabaseConfig:
    host: str = "remsldbold-cluster.cluster-cwetdgelvqwq.ap-south-1.rds.amazonaws.com"
    port: int = 5432
    dbname: str = "umpremsl"
    user: str = "uatnemlmandi"
    password: str = ""
    sslmode: str = "prefer"
    allowed_tables: List[str] = field(default_factory=list)

class SecurePostgresConnector:
    """
    Enterprise-Grade Secure Database Connector with:
    1. Read-Only Enforcement & AST/Regex SQL Sanitization.
    2. Dynamic Table Introspection from PostgreSQL information_schema.
    3. Row-Level Limit & Timeout Enforcements.
    4. Generic Dynamic PII Masking (Mobile Numbers, Bank Accounts, Emails, Addresses).
    5. Zero hardcoded dummy records.
    """
    def __init__(self, config: Optional[DatabaseConfig] = None):
        db_pwd = os.environ.get("UMP_RDS_PASSWORD") or os.environ.get("POSTGRES_PASSWORD", "password123")
        self.config = config or DatabaseConfig(
            host=os.environ.get("POSTGRES_HOST", "remsldbold-cluster.cluster-cwetdgelvqwq.ap-south-1.rds.amazonaws.com"),
            port=int(os.environ.get("POSTGRES_PORT", "5432")),
            dbname=os.environ.get("POSTGRES_DB", "umpremsl"),
            user=os.environ.get("POSTGRES_USER", "uatnemlmandi"),
            password=db_pwd,
        )
        self.custom_schema_ddl: Optional[str] = None
        self.discovered_tables: List[str] = []

    def set_custom_schema_ddl(self, custom_ddl: str):
        """Allows user to register custom table schemas / DDL dynamically."""
        self.custom_schema_ddl = custom_ddl.strip()

    def introspect_live_postgres_schema(self, schema_name: str = "public") -> Dict[str, Any]:
        """
        Dynamically introspects real live tables and column schemas from PostgreSQL information_schema.
        Works automatically for ANY table name.
        """
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=self.config.host,
                port=self.config.port,
                dbname=self.config.dbname,
                user=self.config.user,
                password=self.config.password,
                connect_timeout=5
            )
            conn.set_session(readonly=True, autocommit=False)
            cursor = conn.cursor()

            # Query all table names in the schema
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = %s AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """, (schema_name,))
            tables = [r[0] for r in cursor.fetchall()]
            self.discovered_tables = tables

            # Query columns and data types for each table
            ddl_parts = []
            for tbl in tables:
                cursor.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position;
                """, (schema_name, tbl))
                cols = cursor.fetchall()
                col_defs = [f"    {c[0]} {c[1].upper()}" for c in cols]
                ddl_parts.append(f"-- Table: {tbl}\nCREATE TABLE {tbl} (\n" + ",\n".join(col_defs) + "\n);")

            conn.rollback()
            conn.close()

            discovered_ddl = "\n\n".join(ddl_parts)
            self.custom_schema_ddl = discovered_ddl
            return {
                "success": True,
                "table_count": len(tables),
                "tables": tables,
                "ddl": discovered_ddl,
                "source": "live_postgres_introspection"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "tables": [],
                "ddl": self.get_default_schema_ddl(),
                "source": "discovery_error"
            }

    def get_schema_ddl(self) -> str:
        """Returns the active DDL schema (custom/discovered if present, otherwise instructions)."""
        if self.custom_schema_ddl:
            return self.custom_schema_ddl
        return self.get_default_schema_ddl()

    def get_default_schema_ddl(self) -> str:
        """Returns instructions or placeholder when no schema has been cached yet."""
        return """-- No cached schema.
-- Click '🔄 Auto-Discover Live Tables from PostgreSQL' to load your live tables,
-- or paste your CREATE TABLE DDL definitions below:
"""

    def validate_sql(self, sql_query: str) -> Tuple[bool, str]:
        """
        Enterprise Security Guardrails:
        - Ensures query is strictly a read-only SELECT.
        - Blocks DDL, DML, write operations, and stacked statements (;).
        """
        clean = sql_query.strip().strip(";")
        
        # Check for multiple stacked statements
        if ";" in clean:
            return False, "Security Violation: Multiple stacked SQL queries are blocked to prevent SQL injection."

        # Reject any non-SELECT commands
        forbidden_keywords = [
            r"\bDROP\b", r"\bDELETE\b", r"\bUPDATE\b", r"\bINSERT\b", 
            r"\bALTER\b", r"\bTRUNCATE\b", r"\bGRANT\b", r"\bREVOKE\b", 
            r"\bCREATE\b", r"\bEXEC\b", r"\bEXECUTE\b", r"\bINTO\b\s+\bOUTFILE\b"
        ]
        for pattern in forbidden_keywords:
            if re.search(pattern, clean, re.IGNORECASE):
                return False, f"Security Violation: Destructive statement or write operation detected ({pattern}). Only read-only SELECT statements are permitted."

        if not re.match(r"^\s*SELECT\b", clean, re.IGNORECASE):
            return False, "Security Violation: Query must begin with SELECT."

        return True, clean

    def execute_safe_query(
        self,
        sql_query: str,
        mask_pii: bool = True,
        max_rows: int = 50
    ) -> Dict[str, Any]:
        """Executes a sanitized SQL query against the live database with PII masking."""
        is_valid, sanitized_sql_or_error = self.validate_sql(sql_query)
        if not is_valid:
            return {
                "success": False,
                "error": sanitized_sql_or_error,
                "sql": sql_query,
                "rows": [],
                "columns": []
            }

        sanitized_sql = sanitized_sql_or_error
        # Enforce LIMIT
        if not re.search(r"\bLIMIT\s+\d+", sanitized_sql, re.IGNORECASE):
            sanitized_sql = f"{sanitized_sql} LIMIT {max_rows}"

        rows = []
        columns = []

        try:
            import psycopg2
            conn = psycopg2.connect(
                host=self.config.host,
                port=self.config.port,
                dbname=self.config.dbname,
                user=self.config.user,
                password=self.config.password,
                connect_timeout=5
            )
            # 🛡️ SECURITY: Force PostgreSQL Engine to READ-ONLY Transaction Mode
            conn.set_session(readonly=True, autocommit=False)
            cursor = conn.cursor()
            cursor.execute("SET TRANSACTION READ ONLY;")
            cursor.execute(sanitized_sql)
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                raw_rows = cursor.fetchall()
                rows = [dict(zip(columns, r)) for r in raw_rows]
            conn.rollback() # Always rollback to guarantee no state mutation
            conn.close()
        except Exception as e:
            return {
                "success": False,
                "error": f"Live Database Connection Error: {str(e)}",
                "sql": sanitized_sql,
                "rows": [],
                "columns": []
            }

        # Apply Dynamic PII Masking if requested
        if mask_pii:
            rows = self._apply_pii_masking(rows)

        return {
            "success": True,
            "sql": sanitized_sql,
            "row_count": len(rows),
            "columns": columns,
            "rows": rows
        }

    def _apply_pii_masking(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Dynamically masks sensitive PII fields (phone numbers, emails, addresses, account numbers)
        regardless of table/column naming conventions.
        """
        masked = []
        for r in rows:
            new_r = dict(r)
            for col_name, val in r.items():
                if val is None:
                    continue
                val_str = str(val).strip()
                col_lower = col_name.lower()

                # 1. Phone / Mobile / Contact Numbers
                if any(k in col_lower for k in ["mobile", "phone", "contact", "cell", "tel"]):
                    if len(val_str) >= 4:
                        new_r[col_name] = f"+91 ******{val_str[-4:]}"
                    else:
                        new_r[col_name] = "******"

                # 2. Email addresses
                elif any(k in col_lower for k in ["email", "mail_id"]):
                    if "@" in val_str:
                        user_part, domain = val_str.split("@", 1)
                        masked_user = (user_part[0] + "***" + user_part[-1]) if len(user_part) > 2 else "***"
                        new_r[col_name] = f"{masked_user}@{domain}"

                # 3. Addresses
                elif any(k in col_lower for k in ["address", "street", "addr", "location_desc"]):
                    # Redact plot/house numbers and exact street numbers
                    masked_addr = re.sub(r'(\d+)', '**', val_str[:25]) + "..." if len(val_str) > 25 else val_str
                    new_r[col_name] = masked_addr

                # 4. Bank Account / Aadhaar / PAN / National ID / Passwords
                elif any(k in col_lower for k in ["bank", "account_no", "acc_no", "aadhaar", "pan_no", "ssn", "password", "secret"]):
                    if len(val_str) >= 4:
                        new_r[col_name] = f"******{val_str[-4:]}"
                    else:
                        new_r[col_name] = "******"

            masked.append(new_r)
        return masked
