
import pandas as pd
import numpy as np
from .data_quality import generate_data_quality_report, sanitize_dataframe_for_analysis


def perform_eda(df):
    clean_df = sanitize_dataframe_for_analysis(df)
    quality_report = generate_data_quality_report(df)

    result = {
        "overview": {
            "total_rows": quality_report["total_rows"],
            "total_columns": quality_report["total_columns"],
            "total_cells": quality_report["total_cells"],
            "missing_values": quality_report["total_missing_cells"],
            "invalid_values": quality_report["total_invalid_cells"],
            "valid_values": quality_report["total_valid_cells"],
            "completeness_rate": quality_report["completeness_rate"],
            "valid_data_rate": quality_report["valid_data_rate"],
            "duplicate_rows": quality_report["duplicate_rows"],
            "duplicate_summary": quality_report["duplicate_summary"],
            "overall_completeness": quality_report["completeness_rate"]
        },
        "data_quality": quality_report,
        "numerical_analysis": {},
        "categorical_analysis": {},
        "outliers": {},
        "correlation": {},
        "chart_recommendations": []
    }

    numerical_columns = clean_df.select_dtypes(
        include=np.number
    ).columns.tolist()

    categorical_columns = [
        c for c in df.columns if c not in numerical_columns
    ]

    # Numerical analysis on valid observations only
    for col in numerical_columns:
        series = clean_df[col].dropna()

        if series.empty:
            continue

        result["numerical_analysis"][col] = {
            "valid_observations": len(series),
            "missing_or_invalid": len(df) - len(series),
            "mean": round(float(series.mean()), 4),
            "median": round(float(series.median()), 4),
            "std": round(float(series.std()), 4) if len(series) > 1 else 0,
            "min": round(float(series.min()), 4),
            "max": round(float(series.max()), 4),
            "sum": round(float(series.sum()), 4)
        }

        # IQR outlier detection
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1

        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        outlier_count = int(
            ((series < lower) | (series > upper)).sum()
        )

        result["outliers"][col] = {
            "lower_bound": float(lower),
            "upper_bound": float(upper),
            "outlier_count": outlier_count
        }

        result["chart_recommendations"].append({
            "column": col,
            "chart": "histogram",
            "reason": "Numerical distribution analysis"
        })

    # Categorical analysis
    for col in categorical_columns:

        series = df[col].dropna()

        result["categorical_analysis"][col] = {
            "unique_values": int(series.nunique()),
            "top_values": {
                str(k): int(v)
                for k, v in series.value_counts().head(5).items()
            }
        }

        result["chart_recommendations"].append({
            "column": col,
            "chart": "bar",
            "reason": "Categorical frequency analysis"
        })

    # Correlation analysis
    if len(numerical_columns) >= 2:

        corr = clean_df[numerical_columns].corr()

        result["correlation"] = (
            corr.round(3).fillna(0).to_dict()
        )

        result["chart_recommendations"].append({
            "columns": numerical_columns,
            "chart": "heatmap",
            "reason": "Numerical correlation analysis"
        })

    # Missing values
    result["missing_value_analysis"] = {
        str(col): int(value)
        for col, value in df.isnull().sum().items()
    }

    return result
