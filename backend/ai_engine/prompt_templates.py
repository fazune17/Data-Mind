import json


def analysis_plan_prompt(question, df, schema_info):
    guidance_str = "\n".join(schema_info.get("synonym_guidance", []))
    columns_str = ", ".join([f"{col} ({dtype})" for col, dtype in schema_info.get("columns_with_types", {}).items()])
    numeric_str = ", ".join(schema_info.get("numeric_columns", []))
    date_str = ", ".join(schema_info.get("date_columns", [])) if schema_info.get("date_columns") else "None detected"
    cat_str = ", ".join(schema_info.get("categorical_columns", []))

    return f"""
You are DataMind, an expert AI analytical planner.
Convert the user question into a structured analytical plan grounded strictly on the dataset schema.

EXACT DATASET COLUMNS & TYPES:
{columns_str}

COLUMN CATEGORIES:
- Numeric columns: {numeric_str}
- Date/Temporal columns: {date_str}
- Categorical columns: {cat_str}

SAMPLE RECORDS:
{json.dumps(schema_info.get('sample_preview', []), default=str)}

DYNAMIC COLUMN MAPPINGS FOR THIS DATASET:
{guidance_str}

USER QUESTION:
{question}

SUPPORTED OPERATIONS:
1. "duplicate_count":
   USE THIS whenever user asks about duplicate records or duplicate detection.
   {{"operation": "duplicate_count"}}

2. "missing_values":
   USE THIS whenever user asks for missing values in each column or missing values chart.
   {{"operation": "missing_values", "chart_type": "bar"}}

3. "data_quality":
   USE THIS whenever user asks about invalid values, invalid records, data quality, completeness rate, valid data rate, column-wise classification, or dataset diagnostics.
   {{"operation": "data_quality"}}

4. "sql_query": (PREFERRED for multi-metric, trends, comparisons, and groupings)
   Provide executable ANSI SQL on table 'dataset'.
   IMPORTANT: In SQLite, COUNT() strictly takes only 1 argument or *. NEVER write COUNT(DISTINCT a, b).
   Examples:
   - For duplicates in SQL:
     SELECT (SELECT COUNT(*) FROM dataset) - (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM dataset)) AS duplicate_count
   - For multiple metrics (e.g. total revenue and total profit):
     SELECT SUM(Revenue_INR) AS total_revenue, SUM(Profit_INR) AS total_profit FROM dataset
   - For monthly trends:
     SELECT substr(Order_Date, 1, 7) AS month, SUM(Revenue_INR) AS monthly_sales FROM dataset GROUP BY month ORDER BY month
   - For average of a numeric column:
     SELECT AVG(quiz_percent) AS avg_score FROM dataset
   - For top categories / products (e.g. highest selling, highest revenue, top 5):
     SELECT Category, SUM(Revenue_INR) AS total_revenue FROM dataset GROUP BY Category ORDER BY total_revenue DESC LIMIT 5

5. "multi_aggregate":
   {{"operation": "multi_aggregate", "metrics": [{{"column": "Revenue_INR", "aggregation": "sum", "label": "Total Revenue"}}, {{"column": "Profit_INR", "aggregation": "sum", "label": "Total Profit"}}]}}

6. "group_by_aggregate":
   {{"operation": "group_by_aggregate", "group_column": "learning_track", "value_column": "quiz_percent", "aggregation": "avg", "limit": 5, "chart_type": "bar"}}

7. "monthly_trend":
   {{"operation": "monthly_trend", "date_column": "Order_Date", "value_column": "Revenue_INR", "chart_type": "line"}}

RULES:
- ONLY use existing column names from the dataset. Never invent or hallucinate column names.
- Always select an appropriate chart_type: "bar", "line", "pie", or "none". For trends use "line", for comparisons use "bar".
- Never convert invalid values to zero. Statistical aggregations must be calculated on valid observations only.
- If the question cannot be answered from the dataset, return operation "unsupported".

Return ONLY valid JSON matching this schema:
{{
    "operation": "sql_query",
    "sql": "SELECT ...",
    "chart_type": "bar"
}}
"""


def insight_prompt(question, results):
    return f"""
You are DataMind, an expert senior business and data analyst.
Explain the verified analytical results clearly and accurately to the user.

USER QUESTION:
{question}

VERIFIED ANALYTICAL RESULTS:
{json.dumps(results, default=str)}

CRITICAL PRESENTATION RULES:
1. MULTIPLE METRICS: If the user asked for multiple metrics (such as total revenue and total profit), ALWAYS present and display each metric separately. Never sum different financial metrics together.
   Example:
   - **Total Revenue:** ₹22,619,335 (or ₹2,26,19,335)
   - **Total Profit:** ₹6,523,995 (or ₹65,23,995)
2. FINANCIAL VALUES: Format Indian currency values with ₹ and proper commas. Format percentages with % (e.g. 6.9125%).
3. FACTUAL ACCURACY: Use only the exact numbers from the verified results. Never invent or alter numbers.
4. STRUCTURE: Use Markdown formatting:
   - Section heading with ###
   - Key findings highlighted in **bold**
   - Clean bullet points for listings
5. DATA QUALITY, COMPLETENESS & DUPLICATES:
   - Always clearly distinguish between:
     * **Completeness Rate:** (Non-missing cells / Total cells) * 100
     * **Valid Data Rate:** (Valid cells / Total cells) * 100
     Never label non-missing observations as valid observations when invalid values exist.
   - For duplicate analysis, present the reconciled metrics:
     * Duplicate Rows Beyond First Occurrence
     * Total Rows Belonging to Duplicate Groups
     * Strictly Unique Rows & Distinct Records
   - For numerical calculations:
     * State the exact number of valid observations used (e.g., "Calculated strictly on 120 valid observations, excluding 4 missing values and 1 invalid text observation ('eighty')").
     * State that duplicate rows were preserved per dataset analysis policy.
6. TONE: Professional, concise, actionable.

Provide the final answer directly.
"""
