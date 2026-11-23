"""
DataMind Data Quality and Validation Module.
Provides deep column-by-column inspection, invalid value detection,
accurate multi-metric duplicate tracking, automated consistency verification,
and safe data sanitization for analytics.
"""

import re
import pandas as pd
import numpy as np


def is_missing_value(val):
    """Check if a value represents a missing or blank entry."""
    if val is None or pd.isna(val):
        return True
    if isinstance(val, (str, bytes)):
        s = str(val).strip().lower()
        if s in ('', 'nan', 'none', 'null', 'na', 'n/a', '<na>', 'undefined'):
            return True
    return False


def infer_column_domain_type(series, col_name):
    """
    Infers the logical/domain data type of a series:
    'Date', 'Percentage', 'Numeric', 'Boolean', 'Identifier', 'Categorical', 'Text'.
    """
    non_missing = series[~series.map(is_missing_value)]
    total_valid = len(non_missing)
    if total_valid == 0:
        return 'Text'

    col_lower = str(col_name).lower()

    # 1. Identifier heuristic
    if any(k in col_lower for k in ['_id', '_key', 'id', 'key', 'code', 'number']) and not any(k in col_lower for k in ['percent', 'amount', 'price', 'cost', 'revenue', 'count', 'score']):
        if non_missing.nunique() > total_valid * 0.7:
            return 'Identifier'

    # 2. Numeric / Duration / Percentage heuristic
    cleaned_num_strings = non_missing.astype(str).str.replace(r'[$₹€£%,\s]', '', regex=True)
    numeric_parsed = pd.to_numeric(cleaned_num_strings, errors='coerce')
    num_valid_ratio = numeric_parsed.notna().sum() / total_valid

    is_duration = any(k in col_lower for k in ['minute', 'second', 'hour', 'duration', 'ms'])
    is_percent_name = any(k in col_lower for k in ['percent', 'pct', 'rate', 'score', 'percentage', 'discount'])
    if num_valid_ratio >= 0.5 or pd.api.types.is_numeric_dtype(series) or is_duration:
        if is_percent_name:
            return 'Percentage'
        return 'Numeric'

    # 3. Date heuristic (must have actual date patterns like YYYY-MM-DD or high valid parse ratio)
    sample_str = non_missing.astype(str).head(10).tolist()
    has_date_format = any(re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', s) for s in sample_str)
    date_parsed = pd.to_datetime(non_missing.astype(str), errors='coerce', format='mixed')
    date_valid_ratio = date_parsed.notna().sum() / total_valid
    if (any(k in col_lower for k in ['date', 'day', 'month', 'year']) or has_date_format) and date_valid_ratio >= 0.5:
        return 'Date'

    # 4. Boolean / Binary heuristic
    bool_canonical = {'yes', 'no', 'true', 'false', '1', '0', '1.0', '0.0', 'y', 'n'}
    bool_ratio = non_missing.astype(str).str.strip().str.lower().isin(bool_canonical).sum() / total_valid
    if bool_ratio >= 0.6 or any(k in col_lower for k in ['is_', 'has_', 'earned', 'flag', 'status']):
        if non_missing.nunique() <= 3:
            return 'Boolean'

    # 5. Categorical vs General Text
    if non_missing.nunique() <= min(30, max(5, int(total_valid * 0.2))):
        return 'Categorical'

    return 'Text'


def analyze_column_quality(series, col_name, total_rows):
    """
    Analyzes data quality for a single column.
    Distinguishes:
    - Total Records (T)
    - Missing Records (M)
    - Non-Missing Records (NM = T - M)
    - Invalid Records (I)
    - Valid Records (V = T - M - I)
    - Completeness Percentage (NM / T * 100)
    - Validity Percentage (V / T * 100)
    Ensures V + M + I == T exactly.
    """
    is_missing = series.map(is_missing_value)
    missing_count = int(is_missing.sum())
    non_missing = series[~is_missing]
    non_missing_count = len(non_missing)

    inferred_type = infer_column_domain_type(series, col_name)

    invalid_count = 0
    invalid_samples = []

    if non_missing_count > 0:
        if inferred_type == 'Date':
            date_parsed = pd.to_datetime(non_missing.astype(str), errors='coerce', format='mixed')
            invalid_mask = date_parsed.isna()
            invalid_count = int(invalid_mask.sum())
            invalid_samples = non_missing[invalid_mask].astype(str).unique()[:5].tolist()

        elif inferred_type in ('Numeric', 'Percentage'):
            cleaned_strings = non_missing.astype(str).str.replace(r'[$₹€£%,\s]', '', regex=True)
            numeric_parsed = pd.to_numeric(cleaned_strings, errors='coerce')
            invalid_mask = numeric_parsed.isna()

            if inferred_type == 'Percentage':
                # Flag values outside 0-100 range as invalid for percentages
                out_of_range = (numeric_parsed < 0) | (numeric_parsed > 100)
                invalid_mask = invalid_mask | out_of_range

            invalid_count = int(invalid_mask.sum())
            invalid_samples = non_missing[invalid_mask].astype(str).unique()[:5].tolist()

        elif inferred_type == 'Boolean':
            bool_canonical = {'yes', 'no', 'true', 'false', '1', '0', '1.0', '0.0', 'y', 'n'}
            invalid_mask = ~non_missing.astype(str).str.strip().str.lower().isin(bool_canonical)
            invalid_count = int(invalid_mask.sum())
            invalid_samples = non_missing[invalid_mask].astype(str).unique()[:5].tolist()

    # Reconciled mathematical calculations
    valid_count = total_rows - missing_count - invalid_count
    if valid_count < 0:
        valid_count = 0

    completeness_percentage = round((non_missing_count / total_rows) * 100, 2) if total_rows > 0 else 0.0
    validity_percentage = round((valid_count / total_rows) * 100, 2) if total_rows > 0 else 0.0
    duplicate_count = int(non_missing.duplicated().sum())

    return {
        "column": col_name,
        "data_type": inferred_type,
        "total_records": total_rows,
        "non_missing_records": non_missing_count,
        "valid_records": valid_count,
        "missing_records": missing_count,
        "invalid_records": invalid_count,
        # Backward-compatible aliases
        "valid_count": valid_count,
        "missing_count": missing_count,
        "invalid_count": invalid_count,
        "invalid_samples": invalid_samples,
        "duplicate_count": duplicate_count,
        "completeness_percentage": completeness_percentage,
        "validity_percentage": validity_percentage
    }


def verify_data_quality_consistency(report):
    """
    Automated consistency verification:
    - Valid + Missing + Invalid == Total records for every column.
    - Sum of column-wise missing == dataset total missing cells.
    - Sum of column-wise invalid == dataset total invalid cells.
    - Completeness percentage matches actual missing count.
    - Valid data percentage matches actual valid count.
    - Duplicate counts reconcile with unique records.
    """
    total_rows = report["total_rows"]
    total_columns = report["total_columns"]
    total_cells = report["total_cells"]

    sum_missing = 0
    sum_invalid = 0
    sum_valid = 0
    sum_non_missing = 0

    for col, info in report["columns"].items():
        t = info["total_records"]
        v = info["valid_records"]
        m = info["missing_records"]
        i = info["invalid_records"]
        nm = info["non_missing_records"]

        # Check 1: T == V + M + I
        if t != v + m + i:
            raise ValueError(f"Consistency check failed for column '{col}': Total ({t}) != Valid ({v}) + Missing ({m}) + Invalid ({i})")

        # Check 2: NM == T - M
        if nm != t - m:
            raise ValueError(f"Consistency check failed for column '{col}': Non-Missing ({nm}) != Total ({t}) - Missing ({m})")

        # Check 3: Completeness %
        expected_comp = round((nm / t) * 100, 2) if t > 0 else 0.0
        if info["completeness_percentage"] != expected_comp:
            raise ValueError(f"Completeness % mismatch in '{col}': got {info['completeness_percentage']}, expected {expected_comp}")

        # Check 4: Validity %
        expected_validity = round((v / t) * 100, 2) if t > 0 else 0.0
        if info["validity_percentage"] != expected_validity:
            raise ValueError(f"Validity % mismatch in '{col}': got {info['validity_percentage']}, expected {expected_validity}")

        sum_missing += m
        sum_invalid += i
        sum_valid += v
        sum_non_missing += nm

    # Check 5: Total cell sums
    if sum_missing != report["total_missing_cells"]:
        raise ValueError(f"Total missing cells discrepancy: sum({sum_missing}) != report({report['total_missing_cells']})")

    if sum_invalid != report["total_invalid_cells"]:
        raise ValueError(f"Total invalid cells discrepancy: sum({sum_invalid}) != report({report['total_invalid_cells']})")

    if sum_valid != report["total_valid_cells"]:
        raise ValueError(f"Total valid cells discrepancy: sum({sum_valid}) != report({report['total_valid_cells']})")

    if sum_non_missing != report["total_non_missing_cells"]:
        raise ValueError(f"Total non-missing cells discrepancy: sum({sum_non_missing}) != report({report['total_non_missing_cells']})")

    # Check 6: Dataset rate formulas
    expected_comp_rate = round((report["total_non_missing_cells"] / total_cells) * 100, 2) if total_cells > 0 else 0.0
    if report["completeness_rate"] != expected_comp_rate:
        raise ValueError(f"Completeness Rate discrepancy: got {report['completeness_rate']}%, expected {expected_comp_rate}%")

    expected_valid_rate = round((report["total_valid_cells"] / total_cells) * 100, 2) if total_cells > 0 else 0.0
    if report["valid_data_rate"] != expected_valid_rate:
        raise ValueError(f"Valid Data Rate discrepancy: got {report['valid_data_rate']}%, expected {expected_valid_rate}%")

    # Check 7: Duplicate reconciliation
    dup = report["duplicate_summary"]
    if dup["unique_rows_strictly_non_repeated"] + dup["total_rows_in_duplicate_groups"] != total_rows:
        raise ValueError("Duplicate reconciliation failed: Unique non-repeated + Total in duplicate groups != Total rows")

    if dup["distinct_records"] + dup["duplicate_rows_beyond_first"] != total_rows:
        raise ValueError("Duplicate reconciliation failed: Distinct records + Duplicates beyond first != Total rows")

    return True


def generate_data_quality_report(df):
    """
    Generates a comprehensive dataset quality analysis with strict mathematical consistency:
    - Distinguishes Completeness Rate from Valid Data Rate.
    - Reconciles Total, Non-Missing, Valid, Missing, and Invalid counts for every column.
    - Provides complete 3-metric duplicate analysis.
    """
    total_rows = len(df)
    total_columns = len(df.columns)
    total_cells = total_rows * total_columns if total_rows > 0 else 1

    duplicate_summary = get_duplicate_summary(df)

    columns_report = {}
    total_valid_cells = 0
    total_missing_cells = 0
    total_invalid_cells = 0
    total_non_missing_cells = 0

    recommendations = []

    for col in df.columns:
        col_res = analyze_column_quality(df[col], col, total_rows)
        columns_report[col] = col_res
        total_valid_cells += col_res["valid_records"]
        total_missing_cells += col_res["missing_records"]
        total_invalid_cells += col_res["invalid_records"]
        total_non_missing_cells += col_res["non_missing_records"]

        # Actionable recommendations
        if col_res["invalid_records"] > 0:
            samples_str = ", ".join(f"'{s}'" for s in col_res["invalid_samples"][:3])
            recommendations.append(
                f"Column '{col}' has {col_res['invalid_records']} invalid observations (e.g. {samples_str}). Exclude invalid entries from statistical aggregations."
            )
        if col_res["missing_records"] > 0:
            recommendations.append(
                f"Column '{col}' has {col_res['missing_records']} missing values ({round(col_res['missing_records']/total_rows*100, 1)}% missing). Verify data collection or apply imputation."
            )

    if duplicate_summary["duplicate_rows_beyond_first"] > 0:
        recommendations.append(
            f"Dataset contains {duplicate_summary['duplicate_rows_beyond_first']} redundant duplicate records "
            f"({duplicate_summary['total_rows_in_duplicate_groups']} rows belong to duplicate groups). "
            f"Review duplicate policy to decide if deduplication is required for unique entity tracking."
        )

    # Two distinct rates as required:
    # 1. Completeness Rate = (Number of non-missing cells / Total cells) * 100
    completeness_rate = round((total_non_missing_cells / total_cells) * 100, 2)

    # 2. Valid Data Rate = (Number of valid cells / Total cells) * 100
    valid_data_rate = round((total_valid_cells / total_cells) * 100, 2)

    report = {
        "total_rows": total_rows,
        "total_columns": total_columns,
        "total_cells": total_cells,
        "total_missing_cells": total_missing_cells,
        "total_non_missing_cells": total_non_missing_cells,
        "total_invalid_cells": total_invalid_cells,
        "total_valid_cells": total_valid_cells,
        "completeness_rate": completeness_rate,
        "valid_data_rate": valid_data_rate,
        # Backward-compatible alias
        "overall_completeness_percentage": completeness_rate,
        "duplicate_rows": duplicate_summary["duplicate_rows_beyond_first"],
        "duplicate_summary": duplicate_summary,
        "columns": columns_report,
        "recommendations": recommendations
    }

    # Run automated consistency verification
    verify_data_quality_consistency(report)

    return report


def get_duplicate_summary(df, subset=None):
    """
    Accurate duplicate record detection supporting full rows or column subsets.
    Provides three separate mathematically consistent metrics:
    1. Duplicate Rows Beyond First Occurrence (redundant rows: df.duplicated(keep='first'))
    2. Total Rows Belonging to Duplicate Groups (all clustered rows: df.duplicated(keep=False))
    3. Unique Rows (strictly single occurrence: ~df.duplicated(keep=False))
    4. Distinct Records (unique logical entity signatures: len(df.drop_duplicates()))
    """
    total_rows = len(df)
    if subset and isinstance(subset, list):
        valid_cols = [c for c in subset if c in df.columns]
        if valid_cols:
            sub = valid_cols
            criteria_desc = f"based on column(s): {', '.join(valid_cols)}"
        else:
            sub = None
            criteria_desc = "based on all columns (exact row matches)"
    else:
        sub = None
        criteria_desc = "based on all columns (exact row matches)"

    dup_beyond_first = int(df.duplicated(subset=sub, keep='first').sum())
    dup_in_groups = int(df.duplicated(subset=sub, keep=False).sum())
    strictly_unique = int((~df.duplicated(subset=sub, keep=False)).sum())
    distinct_records = int(len(df.drop_duplicates(subset=sub)))

    # Mathematical reconciliation
    # strictly_unique + dup_in_groups == total_rows
    # distinct_records + dup_beyond_first == total_rows
    reconciled = (strictly_unique + dup_in_groups == total_rows) and (distinct_records + dup_beyond_first == total_rows)

    return {
        "total_records": total_rows,
        "duplicate_rows_beyond_first": dup_beyond_first,
        "total_rows_in_duplicate_groups": dup_in_groups,
        "unique_rows_strictly_non_repeated": strictly_unique,
        "distinct_records": distinct_records,
        # Backward-compatible aliases
        "duplicate_records": dup_beyond_first,
        "unique_records": distinct_records,
        "criteria": criteria_desc,
        "mathematically_reconciled": reconciled,
        "explanation": (
            f"Duplicate Analysis ({criteria_desc}):\n"
            f"- Duplicate Rows Beyond First Occurrence: {dup_beyond_first} redundant copies.\n"
            f"- Total Rows Belonging to Duplicate Groups: {dup_in_groups} rows ({dup_in_groups // max(1, dup_beyond_first)} rows per duplicate cluster).\n"
            f"- Strictly Unique Rows (single occurrence): {strictly_unique} rows.\n"
            f"- Distinct Logical Records: {distinct_records} records.\n"
            f"Reconciliation: {strictly_unique} unique + {dup_in_groups} duplicate-grouped = {total_rows} total rows."
        )
    }


def sanitize_dataframe_for_analysis(df):
    """
    Prepares a DataFrame for SQLite execution and analytical math without
    altering dataset row count or deleting duplicate rows:
    - In numeric/percentage columns, converts valid numeric strings to floats/ints.
    - Converts non-numeric/invalid text (e.g. 'eighty', 'unknown', 'N/A') to np.nan (SQLite NULL).
    - Ensures SQLite functions like AVG(), SUM(), MIN(), MAX() ignore invalid entries
      instead of casting them to 0.0.
    """
    clean_df = df.copy()

    for col in clean_df.columns:
        series = clean_df[col]
        
        if series.dtype == 'object' or pd.api.types.is_string_dtype(series):
            non_missing = series[~series.map(is_missing_value)]
            if len(non_missing) > 0:
                cleaned_str = non_missing.astype(str).str.replace(r'[$₹€£%,\s]', '', regex=True)
                converted = pd.to_numeric(cleaned_str, errors='coerce')
                valid_num_count = converted.notna().sum()
                
                # If at least 50% of non-missing values can be parsed as numbers
                if valid_num_count / len(non_missing) >= 0.5:
                    full_cleaned_str = series.astype(str).str.replace(r'[$₹€£%,\s]', '', regex=True)
                    clean_series = pd.to_numeric(full_cleaned_str, errors='coerce')
                    clean_df[col] = clean_series

    return clean_df


def get_missing_values_chart_data(df):
    """
    Returns missing-value counts for all columns structured for long-form Chart.js rendering.
    Guarantees every column is present on X-axis, with missing count on Y-axis.
    """
    records = []
    total_rows = len(df)

    for col in df.columns:
        is_missing = df[col].map(is_missing_value)
        missing_count = int(is_missing.sum())
        non_missing_count = total_rows - missing_count
        records.append({
            "column": str(col),
            "missing_count": missing_count,
            "non_missing_count": non_missing_count,
            "total_records": total_rows
        })

    return {
        "data": records,
        "chart": {
            "type": "bar",
            "columns": ["column", "missing_count"]
        },
        "total_results": len(records)
    }
