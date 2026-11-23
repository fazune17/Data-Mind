import sqlite3
import time
import json
import re
import sqlparse
import pandas as pd
from ai_engine.gemini_client import generate_ai_response
from .schema_mapper import inspect_dataset_schema, resolve_column


DISALLOWED_SQL_KEYWORDS = {
    'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'TRUNCATE',
    'REPLACE', 'ATTACH', 'DETACH', 'PRAGMA', 'EXEC', 'EXECUTE',
    'CREATE', 'GRANT', 'REVOKE', 'OUTFILE', 'DUMPFILE'
}

STANDARD_SQL_FUNCTIONS_KEYWORDS = {
    'SELECT', 'FROM', 'WHERE', 'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT',
    'OFFSET', 'AS', 'AND', 'OR', 'NOT', 'IN', 'IS', 'NULL', 'LIKE',
    'DESC', 'ASC', 'JOIN', 'ON', 'SUM', 'AVG', 'COUNT', 'MIN', 'MAX',
    'ROUND', 'STRFTIME', 'SUBSTR', 'DATASET', 'DISTINCT',
    'BETWEEN', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'CAST', 'COALESCE',
    'ALL', 'ANY', 'EXISTS'
}


def validate_sql_security(query):
    """
    Validates SQL query security:
    - Must be a single statement
    - Must be a SELECT operation
    - Must not contain any destructive or system modification keywords
    - Trailing semicolons are stripped safely
    """
    clean = query.strip()
    if clean.endswith(';'):
        clean = clean[:-1].strip()

    if ';' in clean:
        raise ValueError("Multiple SQL statements (semicolon chaining) are strictly prohibited.")

    parsed = sqlparse.parse(clean)
    if len(parsed) != 1:
        raise ValueError("Only a single SQL query statement is permitted.")

    stmt = parsed[0]
    stmt_type = stmt.get_type()
    if stmt_type != 'SELECT':
        raise ValueError(f"Operation '{stmt_type}' is not permitted. Only SELECT queries are allowed.")

    tokens = [t.value.upper() for t in stmt.flatten() if t.ttype in (sqlparse.tokens.Keyword, sqlparse.tokens.DML, sqlparse.tokens.DDL)]
    for token in tokens:
        if token in DISALLOWED_SQL_KEYWORDS:
            raise ValueError(f"Destructive or restricted SQL keyword '{token}' is prohibited.")

    return clean


def repair_and_validate_columns(df, query):
    """
    Validates and repairs column names in SQL query using dynamic schema resolution.
    Preserves SQL keywords, functions, aliases, and string literals.
    """
    parsed = sqlparse.parse(query)
    if not parsed:
        return query

    stmt = parsed[0]
    tokens = list(stmt.flatten())

    # Collect all user-defined aliases in the query so they are never overwritten
    defined_aliases = set()
    for i, tok in enumerate(tokens):
        if tok.ttype in (sqlparse.tokens.Keyword, sqlparse.tokens.Keyword.DML) and tok.value.upper() == 'AS':
            for j in range(i + 1, len(tokens)):
                if not tokens[j].is_whitespace:
                    alias_name = tok.value.strip('`"\'')
                    defined_aliases.add(tokens[j].value.strip('`"\'').lower())
                    break

    repaired_tokens = []
    prev_was_as = False

    for t in tokens:
        val = t.value
        
        # Don't touch string literals
        if t.ttype in (sqlparse.tokens.Literal.String, sqlparse.tokens.Literal.String.Single, sqlparse.tokens.Literal.String.Symbol):
            repaired_tokens.append(val)
            prev_was_as = False
            continue

        # If previous token was 'AS', this is an alias: preserve as-is
        if prev_was_as and not t.is_whitespace:
            repaired_tokens.append(val)
            prev_was_as = False
            continue

        if not t.is_whitespace and t.ttype in (sqlparse.tokens.Keyword, sqlparse.tokens.Keyword.DML):
            if val.upper() == 'AS':
                prev_was_as = True
            else:
                prev_was_as = False
            repaired_tokens.append(val)
            continue

        # If it looks like an identifier/column name
        if val.isidentifier():
            if val.upper() in STANDARD_SQL_FUNCTIONS_KEYWORDS or val.lower() in defined_aliases:
                repaired_tokens.append(val)
            else:
                # Attempt to resolve column dynamically
                resolved = resolve_column(df, val)
                if resolved:
                    # Enclose in backticks if it has spaces or special chars
                    repaired_tokens.append(f"`{resolved}`" if " " in resolved else resolved)
                else:
                    repaired_tokens.append(val)
        else:
            repaired_tokens.append(val)

    return ''.join(repaired_tokens)


def rewrite_sql_count_compatibility(query):
    """
    Rewrites SQLite-incompatible COUNT expressions:
    - In SQLite, COUNT() strictly accepts a single expression or *.
    - Multi-column COUNT(DISTINCT a, b, ...) is rewritten to:
      (SELECT COUNT(*) FROM (SELECT DISTINCT a, b, ... FROM dataset))
    - Multi-column COUNT(a, b, ...) without DISTINCT is rewritten to COUNT(*).
    Preserves nested expressions like COUNT(CASE WHEN x IN ('a', 'b') ...).
    """
    if not isinstance(query, str) or 'COUNT' not in query.upper():
        return query

    pos = 0
    upper_q = query.upper()
    while True:
        idx = upper_q.find('COUNT', pos)
        if idx == -1:
            break

        # Check word boundary before COUNT
        if idx > 0 and (upper_q[idx - 1].isalnum() or upper_q[idx - 1] == '_'):
            pos = idx + 5
            continue

        # Look for opening paren
        after = idx + 5
        while after < len(query) and query[after].isspace():
            after += 1

        if after >= len(query) or query[after] != '(':
            pos = idx + 5
            continue

        # Find matching closing paren
        depth = 0
        end_paren = -1
        in_str = False
        str_char = ''
        for i in range(after, len(query)):
            ch = query[i]
            if ch in ("'", '"') and (i == 0 or query[i - 1] != '\\'):
                if not in_str:
                    in_str = True
                    str_char = ch
                elif ch == str_char:
                    in_str = False
            elif not in_str:
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth == 0:
                        end_paren = i
                        break

        if end_paren == -1:
            pos = idx + 5
            continue

        inner = query[after + 1:end_paren].strip()

        # Count top-level commas at depth 0 outside quotes
        top_commas = 0
        depth = 0
        in_str = False
        str_char = ''
        for ch in inner:
            if ch in ("'", '"'):
                if not in_str:
                    in_str = True
                    str_char = ch
                elif ch == str_char:
                    in_str = False
            elif not in_str:
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                elif ch == ',' and depth == 0:
                    top_commas += 1

        if top_commas > 0:
            inner_upper = inner.upper().strip()
            if inner_upper.startswith('DISTINCT'):
                cols = inner[8:].strip()
                replacement = f"(SELECT COUNT(*) FROM (SELECT DISTINCT {cols} FROM dataset))"
            else:
                replacement = "COUNT(*)"

            query = query[:idx] + replacement + query[end_paren + 1:]
            upper_q = query.upper()
            pos = idx + len(replacement)
        else:
            pos = end_paren + 1

    return query


def execute_sql_query(df, query):
    """
    Executes a validated SELECT query on a DataFrame using an in-memory SQLite database.
    Restricts to safe SELECT operations only.
    """
    from .data_quality import sanitize_dataframe_for_analysis

    safe_query = validate_sql_security(query)
    repaired_query = repair_and_validate_columns(df, safe_query)
    repaired_query = rewrite_sql_count_compatibility(repaired_query)

    start_time = time.time()

    clean_df = sanitize_dataframe_for_analysis(df)

    conn = sqlite3.connect(":memory:", timeout=10)
    try:
        # Load sanitized dataframe into SQLite tables (preserves all rows/duplicates)
        clean_df.to_sql("dataset", conn, if_exists="replace", index=False)
        clean_df.to_sql("sales", conn, if_exists="replace", index=False)

        cursor = conn.cursor()
        try:
            cursor.execute(repaired_query)
        except sqlite3.OperationalError as op_err:
            # Check if operational error was due to missing column
            err_msg = str(op_err)
            if "no such column" in err_msg.lower():
                raise ValueError(
                    f"{err_msg}. Available dataset columns are: {', '.join(df.columns)}"
                )
            raise ValueError(f"SQL execution error: {err_msg}")

        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows_raw = cursor.fetchall()

        rows = []
        for r in rows_raw[:500]:  # limit to 500 rows for response payload
            rows.append(dict(zip(columns, r)))

        execution_time_ms = round((time.time() - start_time) * 1000, 2)

        return {
            "columns": columns,
            "rows": rows,
            "count": len(rows_raw),
            "execution_time_ms": execution_time_ms,
            "executed_sql": repaired_query
        }
    finally:
        conn.close()


def generate_sql_from_nl(question, df, schema=None):
    """
    Translates a natural language question into an ANSI SQL query for the table 'dataset'.
    Grounds strictly on actual dataset columns, types, and sample records.
    """
    schema_info = inspect_dataset_schema(df)
    
    guidance_str = "\n".join(schema_info["synonym_guidance"])
    columns_str = ", ".join([f"{col} ({dtype})" for col, dtype in schema_info["columns_with_types"].items()])
    numeric_str = ", ".join(schema_info["numeric_columns"])
    date_str = ", ".join(schema_info["date_columns"]) if schema_info["date_columns"] else "None explicitly detected"
    cat_str = ", ".join(schema_info["categorical_columns"])

    prompt = f"""
You are an expert SQL engineer for DataMind.
Convert the user question into an ANSI SQL query for the table 'dataset'.

DATASET COLUMNS & TYPES:
{columns_str}

COLUMN CATEGORIES:
- Numeric columns: {numeric_str}
- Date/Temporal columns: {date_str}
- Categorical columns: {cat_str}

SAMPLE RECORDS:
{json.dumps(schema_info['sample_preview'], default=str)}

DYNAMIC COLUMN MAPPINGS FOR THIS DATASET:
{guidance_str}

USER QUESTION:
{question}

CRITICAL RULES:
1. ONLY USE EXISTING COLUMNS FROM 'DATASET COLUMNS & TYPES'. Never invent or assume column names.
2. If asking for multiple metrics (e.g. total revenue and total profit), select each metric separately:
   Example: SELECT SUM(Revenue_INR) AS total_revenue, SUM(Profit_INR) AS total_profit FROM dataset
3. For monthly trends, group by month string:
   Example: SELECT substr(Order_Date, 1, 7) AS month, SUM(Revenue_INR) AS monthly_sales FROM dataset GROUP BY month ORDER BY month
4. For top products/categories/regions, GROUP BY that column and ORDER BY aggregation DESC LIMIT N.
5. For averages, use AVG(column).
6. Return ONLY the raw SQL query. No explanation, no markdown code fences like ```sql.
"""

    response_text = generate_ai_response(prompt).strip()
    if response_text.startswith("```"):
        lines = response_text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        response_text = "\n".join(lines).strip()

    return response_text
