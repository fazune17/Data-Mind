"""
DataMind Dynamic Schema Grounding & Column Semantic Mapper
Provides dataset-agnostic schema introspection, column resolution,
and semantic synonym mapping for SQL generation and analytical queries.
"""

import re
import difflib
import pandas as pd
import numpy as np


# Universal business concept clusters (dataset-agnostic)
SEMANTIC_CONCEPTS = {
    "revenue": [
        "revenue", "sales", "turnover", "total_sales", "total_revenue",
        "gross_sales", "net_sales", "amount", "total_amount", "order_value",
        "sales_amount", "invoiced_amount", "billing_amount"
    ],
    "profit": [
        "profit", "net_profit", "gross_profit", "margin", "earnings",
        "income", "net_income", "operating_profit", "profit_margin"
    ],
    "quantity": [
        "quantity", "qty", "units", "units_sold", "volume", "count",
        "number_of_items", "order_quantity", "quantity_sold", "items"
    ],
    "price": [
        "price", "unit_price", "rate", "selling_price", "mrp", "list_price",
        "unit_rate", "product_price"
    ],
    "cost": [
        "cost", "unit_cost", "total_cost", "cogs", "cost_of_goods", "expense",
        "purchase_price", "buying_price"
    ],
    "discount": [
        "discount", "discount_percent", "discount_pct", "discount_rate",
        "discount_amount", "discount_inr", "discount_value", "rebate"
    ],
    "date": [
        "date", "order_date", "transaction_date", "invoice_date", "sale_date",
        "created_at", "timestamp", "time", "purchase_date", "day", "month", "year"
    ],
    "product": [
        "product", "product_name", "item", "item_name", "sku", "product_id",
        "article", "commodity", "title", "model"
    ],
    "category": [
        "category", "product_category", "department", "segment", "type",
        "group", "class", "family", "genre"
    ],
    "region": [
        "region", "location", "city", "state", "country", "territory",
        "zone", "area", "market", "branch", "store_location"
    ],
    "customer": [
        "customer", "customer_name", "client", "account", "buyer",
        "consumer", "customer_id", "user"
    ],
    "customer_segment": [
        "customer_segment", "segment", "customer_type", "client_type",
        "tier", "persona"
    ],
    "sales_channel": [
        "sales_channel", "channel", "platform", "source", "distribution_channel"
    ],
    "payment_method": [
        "payment_method", "payment_type", "payment_mode", "tender_type"
    ]
}


def normalize_term(term):
    """Normalize a string by lowercasing, stripping currency suffixes and punctuation."""
    if not isinstance(term, str):
        return ""
    t = term.lower().strip()
    # Remove currency or unit suffixes like _inr, _usd, _eur, _pct, _percent
    t = re.sub(r'_(inr|usd|eur|gbp|pct|percent|percentage)$', '', t)
    # Remove special characters
    t = re.sub(r'[^a-z0-9]', '', t)
    return t


def resolve_column(df, term):
    """
    Dynamically maps a user-supplied term or assumed column to the actual
    exact column in the DataFrame.
    Returns the exact column name or None.
    """
    if not term or not isinstance(term, str):
        return None

    columns = list(df.columns)
    term_str = term.strip()

    # 1. Exact match
    if term_str in columns:
        return term_str

    # 2. Case-insensitive match
    col_map_lower = {col.lower(): col for col in columns}
    if term_str.lower() in col_map_lower:
        return col_map_lower[term_str.lower()]

    # 3. Normalized match (without underscores/currency)
    norm_term = normalize_term(term_str)
    col_map_norm = {normalize_term(col): col for col in columns}
    if norm_term in col_map_norm:
        return col_map_norm[norm_term]

    # 4. Semantic Concept Cluster Matching
    # Identify which concept the input term belongs to
    matched_concept = None
    for concept, synonyms in SEMANTIC_CONCEPTS.items():
        if term_str.lower() in synonyms or norm_term in [normalize_term(s) for s in synonyms]:
            matched_concept = concept
            break

    if matched_concept:
        # Search dataset columns for matching synonym
        for syn in SEMANTIC_CONCEPTS[matched_concept]:
            if syn in col_map_lower:
                return col_map_lower[syn]
            norm_syn = normalize_term(syn)
            if norm_syn in col_map_norm:
                return col_map_norm[norm_syn]
            # Substring match within column name
            for col in columns:
                if syn in col.lower() or normalize_term(col) == norm_syn:
                    return col

    # 5. Fuzzy Substring / Levenshtein match
    for col in columns:
        if term_str.lower() in col.lower() or col.lower() in term_str.lower():
            return col

    # 6. Difflib close match (cutoff 0.7)
    close_matches = difflib.get_close_matches(term_str.lower(), [c.lower() for c in columns], n=1, cutoff=0.7)
    if close_matches:
        return col_map_lower[close_matches[0]]

    return None


def inspect_dataset_schema(df):
    """
    Extracts rich schema metadata for prompting Gemini and query grounding.
    """
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    # Identify date columns
    date_cols = []
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            date_cols.append(col)
        elif any(d_kw in col.lower() for d_kw in ['date', 'time', 'timestamp', 'day', 'month', 'year']):
            date_cols.append(col)
        elif df[col].dtype == 'object':
            sample_non_null = df[col].dropna().head(10).astype(str).tolist()
            if sample_non_null and all(re.match(r'^\d{4}[-/]\d{2}[-/]\d{2}', s) for s in sample_non_null):
                date_cols.append(col)

    categorical_cols = [c for c in df.columns if c not in numeric_cols and c not in date_cols]

    # Detect dynamic semantic equivalents in this specific dataset
    synonym_guidance = []
    for concept, synonyms in SEMANTIC_CONCEPTS.items():
        matched_actual = resolve_column(df, concept)
        if matched_actual:
            synonym_guidance.append(f"- For '{concept}', use column '{matched_actual}'")

    sample_preview = df.head(3).astype(object).where(pd.notna(df.head(3)), None).to_dict(orient="records")

    columns_with_types = {str(col): str(df[col].dtype) for col in df.columns}

    return {
        "exact_columns": [str(c) for c in df.columns],
        "columns_with_types": columns_with_types,
        "numeric_columns": numeric_cols,
        "date_columns": date_cols,
        "categorical_columns": categorical_cols,
        "sample_preview": sample_preview,
        "synonym_guidance": synonym_guidance,
        "total_rows": len(df),
        "total_columns": len(df.columns)
    }
