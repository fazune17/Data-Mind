
import pandas as pd
from pathlib import Path


def load_dataset(file_path):
    """Load a CSV or Excel file into a DataFrame."""

    extension = Path(file_path).suffix.lower()

    if extension == '.csv':
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                first_line = f.readline()
            if first_line:
                import csv
                reader = csv.reader([first_line])
                headers = [h.strip() for h in next(reader, []) if h.strip()]
                if len(headers) != len(set(headers)):
                    raise ValueError("Duplicate column names detected.")
        except ValueError:
            raise
        except Exception:
            pass
        df = pd.read_csv(file_path)

    elif extension in ('.xlsx', '.xls'):
        try:
            df = pd.read_excel(file_path, engine='openpyxl')
        except Exception:
            df = pd.read_excel(file_path)

    else:
        raise ValueError("Unsupported file format.")

    if df.empty:
        raise ValueError("The uploaded dataset is empty.")

    if len(df.columns) > 100:
        raise ValueError("Maximum 100 columns allowed.")

    if len(df) > 100000:
        raise ValueError("Maximum 100,000 rows allowed.")

    if not df.columns.is_unique:
        raise ValueError("Duplicate column names detected.")

    return df


def get_dataset_schema(df):

    schema = {}

    for column in df.columns:

        schema[str(column)] = str(df[column].dtype)

    return schema


def get_dataset_profile(df):
    from analytics.data_quality import generate_data_quality_report, sanitize_dataframe_for_analysis

    quality_report = generate_data_quality_report(df)
    clean_df = sanitize_dataframe_for_analysis(df)

    profile = {
        "total_rows": quality_report["total_rows"],
        "total_columns": quality_report["total_columns"],
        "total_cells": quality_report["total_cells"],
        "missing_values": quality_report["total_missing_cells"],
        "non_missing_values": quality_report["total_non_missing_cells"],
        "invalid_values": quality_report["total_invalid_cells"],
        "valid_values": quality_report["total_valid_cells"],
        "completeness_rate": quality_report["completeness_rate"],
        "valid_data_rate": quality_report["valid_data_rate"],
        "duplicate_rows": quality_report["duplicate_rows"],
        "duplicate_summary": quality_report["duplicate_summary"],
        # Backward-compatible aliases
        "overall_completeness": quality_report["completeness_rate"],
        "recommendations": quality_report["recommendations"],
        "columns": {}
    }

    for column in df.columns:
        series = df[column]
        clean_series = clean_df[column]
        q_info = quality_report["columns"].get(column, {})

        column_info = {
            "data_type": q_info.get("data_type", str(series.dtype)),
            "raw_dtype": str(series.dtype),
            "total_records": q_info.get("total_records", len(series)),
            "non_missing_records": q_info.get("non_missing_records", len(series) - int(series.isnull().sum())),
            "valid_records": q_info.get("valid_records", len(series)),
            "missing_records": q_info.get("missing_records", int(series.isnull().sum())),
            "invalid_records": q_info.get("invalid_records", 0),
            "completeness_percentage": q_info.get("completeness_percentage", 100.0),
            "validity_percentage": q_info.get("validity_percentage", 100.0),
            "missing": q_info.get("missing_records", int(series.isnull().sum())),
            "valid": q_info.get("valid_records", len(series)),
            "invalid": q_info.get("invalid_records", 0),
            "invalid_samples": q_info.get("invalid_samples", []),
            "completeness": q_info.get("completeness_percentage", 100.0),
            "unique": int(series.nunique())
        }

        # Check if numeric either natively or sanitized
        if pd.api.types.is_numeric_dtype(clean_series):
            valid_nums = clean_series.dropna()
            if not valid_nums.empty:
                column_info.update({
                    "mean": round(float(valid_nums.mean()), 4),
                    "median": round(float(valid_nums.median()), 4),
                    "min": round(float(valid_nums.min()), 4),
                    "max": round(float(valid_nums.max()), 4),
                    "sum": round(float(valid_nums.sum()), 4)
                })
        elif pd.api.types.is_numeric_dtype(series):
            valid_nums = series.dropna()
            if not valid_nums.empty:
                column_info.update({
                    "mean": round(float(valid_nums.mean()), 4),
                    "median": round(float(valid_nums.median()), 4),
                    "min": round(float(valid_nums.min()), 4),
                    "max": round(float(valid_nums.max()), 4),
                    "sum": round(float(valid_nums.sum()), 4)
                })

        profile["columns"][str(column)] = column_info

    return profile


def get_dataset_preview(df, limit=10):

    preview = df.head(limit).copy()

    preview = preview.astype(object).where(
        pd.notna(preview), None
    )

    return {
        "columns": [str(col) for col in preview.columns],
        "rows": preview.to_dict(orient="records")
    }
