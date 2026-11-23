import pandas as pd
import numpy as np
from .schema_mapper import resolve_column
from .sql_service import execute_sql_query


ALLOWED_AGGREGATIONS = {
    "sum", "mean", "min", "max", "count", "avg"
}

ALLOWED_CHARTS = {
    "bar", "line", "pie", "doughnut", "none"
}


def safe_resolve_column(df, column, must_be_numeric=False):
    """Resolve column name through dynamic schema mapping and validate type."""
    if not isinstance(column, str):
        raise ValueError("Invalid column name.")

    resolved = resolve_column(df, column)
    if not resolved:
        raise ValueError(
            f"Column '{column}' does not exist in the dataset. Available columns: {', '.join(df.columns)}"
        )

    if must_be_numeric:
        if not pd.api.types.is_numeric_dtype(df[resolved]):
            clean_s = pd.to_numeric(df[resolved].astype(str).str.replace(r'[$₹€£%,\s]', '', regex=True), errors='coerce')
            if clean_s.notna().sum() == 0:
                raise ValueError(
                    f"Column '{resolved}' must be numeric for this calculation."
                )

    return resolved


def execute_analysis(df, plan):
    from .data_quality import (
        generate_data_quality_report,
        get_duplicate_summary,
        get_missing_values_chart_data,
        sanitize_dataframe_for_analysis
    )

    operation = plan.get("operation")
    chart_type = plan.get("chart_type", "none")
    if chart_type == "doughnut":
        chart_type = "pie"

    if chart_type not in ALLOWED_CHARTS:
        chart_type = "none"

    limit = plan.get("limit", 10)
    if not isinstance(limit, int) or limit < 1 or limit > 100:
        limit = 10

    if operation == "unsupported":
        raise ValueError(
            plan.get("reason", "The requested information cannot be calculated from this dataset.")
        )

    # Dedicated Operation: Duplicate Record Detection
    if operation in ("duplicate_count", "duplicate_detection", "duplicates"):
        subset_cols = plan.get("columns") or plan.get("subset")
        dup_summary = get_duplicate_summary(df, subset=subset_cols)
        return {
            "data": [{
                "total_records": dup_summary["total_records"],
                "duplicate_rows_beyond_first": dup_summary["duplicate_rows_beyond_first"],
                "total_rows_in_duplicate_groups": dup_summary["total_rows_in_duplicate_groups"],
                "unique_rows_strictly_non_repeated": dup_summary["unique_rows_strictly_non_repeated"],
                "distinct_records": dup_summary["distinct_records"],
                # Backward-compatible aliases
                "duplicate_records": dup_summary["duplicate_rows_beyond_first"],
                "unique_records": dup_summary["distinct_records"],
                "criteria": dup_summary["criteria"],
                "explanation": dup_summary["explanation"]
            }],
            "chart": {
                "type": "none",
                "columns": ["duplicate_rows_beyond_first", "total_rows_in_duplicate_groups", "unique_rows_strictly_non_repeated"]
            },
            "total_results": 1
        }

    # Dedicated Operation: Missing Values Analysis with Chart
    if operation in ("missing_values", "missing_value_analysis"):
        return get_missing_values_chart_data(df)

    # Dedicated Operation: Comprehensive Data Quality Report
    if operation in ("data_quality", "quality_report"):
        dq = generate_data_quality_report(df)
        rows = []
        for col, c in dq["columns"].items():
            rows.append({
                "column": col,
                "type": c["data_type"],
                "total_records": c["total_records"],
                "non_missing_records": c["non_missing_records"],
                "valid_records": c["valid_records"],
                "missing_records": c["missing_records"],
                "invalid_records": c["invalid_records"],
                "invalid_samples": ", ".join(f"'{s}'" for s in c["invalid_samples"][:3]) if c["invalid_samples"] else "None",
                "completeness_percentage": f"{c['completeness_percentage']}%",
                "validity_percentage": f"{c['validity_percentage']}%"
            })
        return {
            "data": rows,
            "chart": {
                "type": "none",
                "columns": ["column", "valid_records", "missing_records", "invalid_records"]
            },
            "total_results": len(rows),
            "summary": {
                "total_rows": dq["total_rows"],
                "total_columns": dq["total_columns"],
                "total_cells": dq["total_cells"],
                "total_missing_cells": dq["total_missing_cells"],
                "total_non_missing_cells": dq["total_non_missing_cells"],
                "total_invalid_cells": dq["total_invalid_cells"],
                "total_valid_cells": dq["total_valid_cells"],
                "completeness_rate": f"{dq['completeness_rate']}%",
                "valid_data_rate": f"{dq['valid_data_rate']}%",
                "duplicate_summary": dq["duplicate_summary"],
                "overall_completeness": f"{dq['completeness_rate']}%",
                "recommendations": dq["recommendations"]
            }
        }

    # 1. SQL Query Execution (Most flexible, accurate, and powerful)
    if operation == "sql_query" or plan.get("sql"):
        sql = plan.get("sql") or plan.get("query")
        if not sql:
            raise ValueError("SQL query missing from analytical plan.")
        
        sql_res = execute_sql_query(df, sql)
        rows = sql_res["rows"]
        columns = sql_res["columns"]

        # Check for wide single-row multi-column aggregates (e.g., missing values across all columns)
        # Transpose into long-form records so every column is an X-axis category with counts on Y-axis
        if len(rows) == 1 and len(columns) > 1:
            first_row = rows[0]
            is_missing_query = any(c.lower().startswith("missing_") for c in columns)
            numeric_vals = [isinstance(first_row[c], (int, float)) for c in columns]
            
            if is_missing_query or (all(numeric_vals) and chart_type in ("bar", "pie")):
                pivoted_records = []
                for c in columns:
                    clean_col_label = c.replace("missing_", "").replace("Missing_", "")
                    pivoted_records.append({
                        "column": clean_col_label,
                        "count": first_row[c]
                    })
                return {
                    "data": pivoted_records,
                    "chart": {
                        "type": "bar",
                        "columns": ["column", "count"]
                    },
                    "total_results": len(pivoted_records),
                    "raw_sql_rows": rows
                }
        
        # If user asked for line chart or trend, preserve chart type
        if "month" in [c.lower() for c in columns] or "date" in [c.lower() for c in columns]:
            chart_type = "line"
        elif len(columns) == 2 and len(rows) > 1 and chart_type == "none":
            chart_type = "bar"

        return {
            "data": rows,
            "chart": {
                "type": chart_type,
                "columns": columns
            },
            "total_results": sql_res["count"]
        }

    # 2. Multi-Metric Separate Aggregations (e.g. Total Revenue and Total Profit)
    if operation in ("multi_aggregate", "multiple_metrics") or (operation == "aggregate" and isinstance(plan.get("metrics"), list)):
        metrics = plan.get("metrics", [])
        if not metrics and plan.get("value_column"):
            # Single metric fallback
            metrics = [{"column": plan.get("value_column"), "aggregation": plan.get("aggregation", "sum")}]

        results_data = []
        for m in metrics:
            col_name = m.get("column")
            agg_name = m.get("aggregation", "sum").lower()
            if agg_name in ("avg", "average"):
                agg_name = "mean"

            actual_col = safe_resolve_column(df, col_name, must_be_numeric=True)
            raw_series = df[actual_col]
            clean_s = pd.to_numeric(raw_series.astype(str).str.replace(r'[$₹€£%,\s]', '', regex=True), errors='coerce')
            valid_obs = clean_s.dropna()
            val = float(getattr(valid_obs, agg_name)()) if not valid_obs.empty else 0.0
            label = m.get("label") or f"{agg_name.capitalize()} of {actual_col}"
            results_data.append({
                "metric": label,
                "column": actual_col,
                "value": round(val, 4),
                "valid_observations": len(valid_obs),
                "missing_observations": int(raw_series.isna().sum()),
                "invalid_observations": int(raw_series.notna().sum() - len(valid_obs)),
                "total_records": len(df)
            })

        return {
            "data": results_data,
            "chart": {
                "type": "none",
                "columns": ["metric", "value"]
            },
            "total_results": len(results_data)
        }

    # 3. Monthly Sales Trends
    if operation in ("monthly_trend", "time_series", "sales_trend"):
        date_col = plan.get("date_column") or "date"
        val_col = plan.get("value_column") or "revenue"
        
        actual_date_col = safe_resolve_column(df, date_col)
        actual_val_col = safe_resolve_column(df, val_col, must_be_numeric=True)

        df_temp = df.copy()
        # Clean numeric value column
        df_temp[actual_val_col] = pd.to_numeric(df_temp[actual_val_col].astype(str).str.replace(r'[$₹€£%,\s]', '', regex=True), errors='coerce')
        # Convert date to YYYY-MM
        try:
            df_temp['__month__'] = pd.to_datetime(df_temp[actual_date_col], errors='coerce').dt.strftime('%Y-%m')
            df_temp = df_temp.dropna(subset=['__month__', actual_val_col])
        except Exception:
            df_temp['__month__'] = df_temp[actual_date_col].astype(str).str.slice(0, 7)
            df_temp = df_temp.dropna(subset=['__month__', actual_val_col])

        trend_df = (
            df_temp.groupby('__month__')[actual_val_col]
            .sum()
            .reset_index()
            .rename(columns={'__month__': 'Month', actual_val_col: 'Monthly Sales'})
            .sort_values('Month')
        )

        return {
            "data": trend_df.to_dict(orient="records"),
            "chart": {
                "type": "line",
                "columns": list(trend_df.columns)
            },
            "total_results": len(trend_df)
        }

    # 4. Group by Revenue (Dynamic: checks if revenue column already exists)
    if operation == "group_by_revenue":
        group = safe_resolve_column(df, plan.get("group_column"))
        
        # Check if direct revenue column exists
        rev_col = resolve_column(df, "revenue") or resolve_column(df, "sales")
        if rev_col and pd.api.types.is_numeric_dtype(df[rev_col]):
            result = (
                df.groupby(group, dropna=False)[rev_col]
                .sum()
                .reset_index()
                .sort_values(rev_col, ascending=False)
                .head(limit)
            )
            col_val_name = rev_col
        else:
            # Multiply quantity * price
            quantity = safe_resolve_column(df, plan.get("quantity_column", "quantity"), must_be_numeric=True)
            price = safe_resolve_column(df, plan.get("price_column", "price"), must_be_numeric=True)
            revenue_series = df[quantity] * df[price]
            df_calc = pd.DataFrame({group: df[group], "revenue": revenue_series})
            result = (
                df_calc.groupby(group, dropna=False)["revenue"]
                .sum()
                .reset_index()
                .sort_values("revenue", ascending=False)
                .head(limit)
            )
            col_val_name = "revenue"

        return {
            "data": result.astype(object).where(pd.notna(result), None).to_dict(orient="records"),
            "chart": {
                "type": chart_type if chart_type != "none" else "bar",
                "columns": [group, col_val_name]
            },
            "total_results": len(result)
        }

    # 5. Group by Aggregate
    if operation == "group_by_aggregate":
        group = safe_resolve_column(df, plan.get("group_column"))
        value = safe_resolve_column(df, plan.get("value_column"), must_be_numeric=True)
        aggregation = plan.get("aggregation", "sum").lower()
        if aggregation in ("avg", "average"):
            aggregation = "mean"

        if aggregation not in ALLOWED_AGGREGATIONS:
            raise ValueError(f"Invalid aggregation '{aggregation}'. Allowed: sum, mean, min, max, count.")

        clean_val = pd.to_numeric(df[value].astype(str).str.replace(r'[$₹€£%,\s]', '', regex=True), errors='coerce')
        df_calc = pd.DataFrame({group: df[group], value: clean_val})

        result = (
            df_calc.groupby(group, dropna=False)[value]
            .agg(aggregation)
            .reset_index()
            .sort_values(value, ascending=False)
            .head(limit)
        )

        return {
            "data": result.astype(object).where(pd.notna(result), None).to_dict(orient="records"),
            "chart": {
                "type": chart_type if chart_type != "none" else "bar",
                "columns": [group, value]
            },
            "total_results": len(result)
        }

    # 6. Single Aggregate
    if operation == "aggregate":
        column = safe_resolve_column(df, plan.get("value_column"), must_be_numeric=True)
        aggregation = plan.get("aggregation", "sum").lower()
        if aggregation in ("avg", "average"):
            aggregation = "mean"

        if aggregation not in ALLOWED_AGGREGATIONS:
            raise ValueError(f"Invalid aggregation '{aggregation}'.")

        raw_series = df[column]
        clean_s = pd.to_numeric(raw_series.astype(str).str.replace(r'[$₹€£%,\s]', '', regex=True), errors='coerce')
        valid_obs = clean_s.dropna()
        if valid_obs.empty:
            raise ValueError(f"No valid numeric observations in column '{column}'.")

        value = getattr(valid_obs, aggregation)()

        result = [{
            "metric": f"{aggregation.capitalize()} of {column}",
            "value": round(float(value), 4),
            "valid_observations": len(valid_obs),
            "missing_observations": int(raw_series.isna().sum()),
            "invalid_observations": int(raw_series.notna().sum() - len(valid_obs)),
            "total_records": len(df)
        }]

        return {
            "data": result,
            "chart": {"type": "none", "columns": ["metric", "value"]},
            "total_results": 1
        }

    # 7. Value Counts
    if operation == "value_counts":
        column = safe_resolve_column(df, plan.get("group_column"))
        result = (
            df[column]
            .value_counts(dropna=False)
            .head(limit)
            .rename_axis(column)
            .reset_index(name="count")
        )

        return {
            "data": result.astype(object).where(pd.notna(result), None).to_dict(orient="records"),
            "chart": {"type": chart_type if chart_type != "none" else "bar", "columns": [column, "count"]},
            "total_results": len(result)
        }

    # 8. Top N
    if operation == "top_n":
        column = safe_resolve_column(df, plan.get("sort_column"), must_be_numeric=True)
        ascending = plan.get("ascending", False)
        result = df.sort_values(column, ascending=ascending).head(limit)

        return {
            "data": result.astype(object).where(pd.notna(result), None).to_dict(orient="records"),
            "chart": {"type": chart_type if chart_type != "none" else "bar", "columns": list(result.columns[:3])},
            "total_results": len(result)
        }

    # 9. Correlation
    if operation == "correlation":
        col1 = safe_resolve_column(df, plan.get("column_a"), must_be_numeric=True)
        col2 = safe_resolve_column(df, plan.get("column_b"), must_be_numeric=True)
        value = float(df[col1].corr(df[col2]))

        result = pd.DataFrame({
            "column_a": [col1],
            "column_b": [col2],
            "correlation": [round(value, 4)]
        })

        return {
            "data": result.to_dict(orient="records"),
            "chart": {"type": "none", "columns": ["column_a", "column_b", "correlation"]},
            "total_results": 1
        }

    raise ValueError(f"Unsupported analytical operation '{operation}'.")
