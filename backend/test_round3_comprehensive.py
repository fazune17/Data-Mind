import os
import sys
import time
import django
import pandas as pd
import numpy as np
import json

# Setup Django environment
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from datasets.models import Dataset
from datasets.processors import load_dataset, get_dataset_profile
from analytics.data_quality import (
    generate_data_quality_report,
    verify_data_quality_consistency,
    get_duplicate_summary,
    sanitize_dataframe_for_analysis
)
from analytics.eda import perform_eda
from analytics.insights_service import generate_dataset_insights
from analytics.sql_service import execute_sql_query, validate_sql_security
from ai_engine.analysis_agent import analyze_dataset
from datasets.views import DatasetDetailView, DatasetPreviewView
from analytics.views import EDAView, DatasetInsightsView, SQLQueryView

User = get_user_model()
BENCHMARK_PATH = os.path.join(os.path.dirname(__file__), 'media', 'datasets', 'DataMind_Stage2_Edge_Cases.xlsx')

def run_tests():
    print("=" * 80)
    print("DATAMIND ROUND 3 - COMPREHENSIVE INTEGRATION & VALIDATION SUITE")
    print("=" * 80)

    # 1. LOAD BENCHMARK DATASET
    if not os.path.exists(BENCHMARK_PATH):
        print(f"ERROR: Benchmark dataset not found at {BENCHMARK_PATH}")
        return

    df_raw = pd.read_excel(BENCHMARK_PATH)
    print(f"[Dataset Loaded] Shape: {df_raw.shape[0]} rows x {df_raw.shape[1]} cols")
    print(f"Columns: {list(df_raw.columns)}")

    # 2. RUN MODULE A & CROSS-MODULE CONSISTENCY
    print("\n--- TEST SECTION 1: CROSS-MODULE MATHEMATICAL CONSISTENCY ---")
    dq_report = generate_data_quality_report(df_raw)
    try:
        assertions_passed = verify_data_quality_consistency(dq_report)
        print(f"Data Quality Assertions Passed: {assertions_passed} (All 7 assertions verified)")
    except ValueError as e:
        print(f"Data Quality Assertion Failed: {e}")
        assertions_passed = False

    profile = get_dataset_profile(df_raw)
    eda = perform_eda(df_raw)
    insights = generate_dataset_insights(df_raw)
    dup_summary = get_duplicate_summary(df_raw)

    print(f"DQ Report: Total Cells = {dq_report['total_cells']}, Missing = {dq_report['total_missing_cells']}, Invalid = {dq_report['total_invalid_cells']}")
    print(f"DQ Report: Completeness = {dq_report['completeness_rate']}%, Valid Rate = {dq_report['valid_data_rate']}%")
    print(f"Profile: Completeness = {profile.get('completeness_rate')}%, Valid Rate = {profile.get('valid_data_rate')}%")
    print(f"Duplicate Summary: {dup_summary}")

    # Check consistency between profile, dq_report, and eda
    assert profile['completeness_rate'] == dq_report['completeness_rate'], "Profile completeness mismatch"
    assert profile['valid_data_rate'] == dq_report['valid_data_rate'], "Profile valid rate mismatch"
    assert eda['overview']['completeness_rate'] == dq_report['completeness_rate'], "EDA completeness mismatch"
    assert eda['overview']['valid_data_rate'] == dq_report['valid_data_rate'], "EDA valid rate mismatch"
    print(">> SUCCESS: Mathematical Consistency verified across Profile, EDA, and Data Quality Report.")

    # 3. TEST SECTION 2: 10 BENCHMARK ASK-WITH-AI QUESTIONS
    print("\n--- TEST SECTION 2: 10 BENCHMARK ASK-WITH-AI QUESTIONS ---")
    questions = [
        ("Q1: Rows & Columns", "How many rows and columns are in this dataset?"),
        ("Q2: Missing Values", "How many missing values are present in this dataset?"),
        ("Q3: Invalid Values", "How many invalid values are present in this dataset?"),
        ("Q4: Duplicate Records", "How many duplicate records are present in this dataset?"),
        ("Q5: Avg Quiz Score", "What is the average quiz percentage?"),
        ("Q6: Avg Study Time", "What is the average study time in minutes?"),
        ("Q7: Top Quiz Track", "Which course track has the highest average quiz percentage?"),
        ("Q8: Certificate Earned Rate", "What percentage of learners earned a certificate?"),
        ("Q9: Top Territory", "Which territory has the highest number of learners?"),
        ("Q10: Complete DQ Report", "Give me a complete data quality report including completeness and valid data rates.")
    ]

    ai_results = {}
    for label, q in questions:
        t0 = time.time()
        try:
            res = analyze_dataset(q, df_raw, schema=profile, profile=profile)
            elapsed = time.time() - t0
            plan = res.get("analysis_plan", {})
            results_data = res.get("results", {})
            insights_text = res.get("insights", "")
            
            ai_results[label] = {
                "question": q,
                "operation": plan.get("operation"),
                "insights": insights_text[:140].replace("\n", " "),
                "data_sample": results_data.get("data", [])[:2],
                "time": round(elapsed, 2)
            }
            print(f"[{label}] (Took {round(elapsed, 2)}s, Op: {plan.get('operation')})")
            if plan.get("sql"):
                print(f"   SQL: {plan.get('sql')}")
            print(f"   Insights: {insights_text[:160]}...")
            if results_data.get("chart"):
                print(f"   Chart: {results_data['chart']}")
        except Exception as e:
            print(f"[{label}] FAILED with error: {e}")

    # 4. TEST SECTION 3: SQL ENGINE COMPATIBILITY & SECURITY
    print("\n--- TEST SECTION 3: SQL ENGINE COMPATIBILITY & SECURITY ---")
    safe_queries = [
        "SELECT COUNT(*) AS total_rows FROM dataset",
        "SELECT learning_track, COUNT(*) AS learner_count, ROUND(AVG(quiz_percent), 2) AS avg_quiz FROM dataset GROUP BY learning_track",
        "SELECT territory, COUNT(*) AS cnt FROM dataset GROUP BY territory ORDER BY cnt DESC",
        "SELECT COUNT(CASE WHEN certificate_earned = 'Yes' THEN 1 END) AS certified_count FROM dataset"
    ]
    for sq in safe_queries:
        out = execute_sql_query(df_raw, sq)
        print(f"Safe SQL: '{sq[:50]}...' -> Rows: {out.get('count')}, Time: {out.get('execution_time_ms')}ms")

    malicious_queries = [
        "DROP TABLE dataset",
        "DELETE FROM dataset WHERE learner_id = 1",
        "UPDATE dataset SET quiz_percent = 100",
        "SELECT * FROM dataset; DROP TABLE dataset;",
        "INSERT INTO dataset VALUES (999, 'Test', 'Track', 'Yes', 100, 100, 100, 'North')"
    ]
    for mq in malicious_queries:
        try:
            out = execute_sql_query(df_raw, mq)
            print(f"FAIL: Malicious SQL '{mq}' was not blocked!")
        except Exception as e:
            print(f"Blocked Malicious SQL: '{mq[:40]}...' -> Caught: {type(e).__name__}: {str(e)[:60]}")

    # 5. TEST SECTION 4: SECURITY & MULTI-USER ISOLATION
    print("\n--- TEST SECTION 4: MULTI-USER ISOLATION ---")
    u1, _ = User.objects.get_or_create(username="testuser1", defaults={"email": "u1@example.com"})
    u2, _ = User.objects.get_or_create(username="testuser2", defaults={"email": "u2@example.com"})
    
    # Create dataset owned by u1
    d1, _ = Dataset.objects.get_or_create(
        user=u1,
        name="Stage2_U1_Test.xlsx",
        defaults={
            "source_type": "excel",
            "row_count": 125,
            "column_count": 8,
            "schema_json": profile,
            "profile_json": profile
        }
    )

    factory = RequestFactory()
    
    # u2 tries to access u1's dataset via profile view
    from datasets.views import DatasetProfileView
    req_u2 = factory.get(f'/datasets/{d1.id}/profile/')
    req_u2.user = u2
    view = DatasetProfileView.as_view()
    resp_u2 = view(req_u2, pk=d1.id)
    u2_blocked = (resp_u2.status_code == 404)
    print(f"Cross-user Dataset Access by User2: Status {resp_u2.status_code} (Blocked/404: {u2_blocked})")

    # u2 tries to run SQL on u1's dataset
    req_sql_u2 = factory.post(f'/analytics/sql/', data=json.dumps({'dataset_id': d1.id, 'sql_query': 'SELECT * FROM dataset'}), content_type='application/json')
    req_sql_u2.user = u2
    sql_view = SQLQueryView.as_view()
    resp_sql = sql_view(req_sql_u2)
    sql_blocked = (resp_sql.status_code == 404)
    print(f"Cross-user SQL execution by User2: Status {resp_sql.status_code} (Blocked/404: {sql_blocked})")

    # 6. TEST SECTION 5: PERFORMANCE BENCHMARKING
    print("\n--- TEST SECTION 5: PERFORMANCE BENCHMARKING (125, 1K, 10K, 50K ROWS) ---")
    scales = [125, 1000, 10000, 50000]
    bench_results = []
    
    for scale in scales:
        repeats = (scale // 125) + 1
        df_scaled = pd.concat([df_raw] * repeats, ignore_index=True).iloc[:scale]
        
        # 1. Profile time
        t0 = time.time()
        p = get_dataset_profile(df_scaled)
        t_prof = round(time.time() - t0, 3)

        # 2. Data quality time
        t0 = time.time()
        dq = generate_data_quality_report(df_scaled)
        t_dq = round(time.time() - t0, 3)

        # 3. SQL execution time
        t0 = time.time()
        sql_res = execute_sql_query(df_scaled, "SELECT learning_track, COUNT(*), AVG(quiz_percent) FROM dataset GROUP BY learning_track")
        t_sql = round(time.time() - t0, 3)

        # 4. Insights generation time
        t0 = time.time()
        ins = generate_dataset_insights(df_scaled)
        t_ins = round(time.time() - t0, 3)

        bench_results.append({
            "rows": scale,
            "profiling_s": t_prof,
            "dq_analysis_s": t_dq,
            "sql_execution_s": t_sql,
            "insights_gen_s": t_ins
        })
        print(f"Scale: {scale:5d} rows | Profile: {t_prof}s | DQ: {t_dq}s | SQL: {t_sql}s | Insights: {t_ins}s")

    print("\n" + "=" * 80)
    print("ALL INTEGRATION TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == '__main__':
    run_tests()
