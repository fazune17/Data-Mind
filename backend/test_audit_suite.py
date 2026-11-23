"""
DataMind Comprehensive Audit & Verification Test Suite
Tests:
1. Authentication & Permissions
2. Dataset Upload & Edge Cases
3. Dataset Listing & Preview
4. Data Insights & Analytics (EDA)
5. AI Q&A with Gemini
6. NL-to-SQL & SQL Security
7. Analysis History Persistence
8. Complete End-to-End Workflow
"""

import os
import sys
import json
import io
import time
import pandas as pd

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from datasets.models import Dataset
from analytics.models import AnalysisHistory

audit_results = {
    "passed": [],
    "failed": [],
    "warnings": []
}

def log_test(name, success, details=""):
    status_str = "PASS" if success else "FAIL"
    print(f"[{status_str}] {name}: {details}")
    if success:
        audit_results["passed"].append(name)
    else:
        audit_results["failed"].append({"name": name, "details": details})


print("\n=======================================================")
print("DATAMIND BACKEND AUDIT SUITE EXECUTION")
print("=======================================================\n")

# Setup Test User
user, _ = User.objects.get_or_create(username='test_auditor')
user.set_password('auditpass123')
user.save()

client = Client()

# ----------------------------------------------------
# 1. AUTHENTICATION & PERMISSIONS
# ----------------------------------------------------
print("--- 1. Testing Authentication & Permissions ---")
# Unauthenticated request to protected endpoint
r_unauth = client.get('/api/datasets/')
# DRF IsAuthenticated returns 401/403 or redirects
log_test("Unauthenticated /api/datasets/ Blocked", r_unauth.status_code in (401, 403), f"Status: {r_unauth.status_code}")

# Authenticate client
client.force_login(user)
r_auth = client.get('/api/datasets/')
log_test("Authenticated /api/datasets/ Permitted", r_auth.status_code == 200, f"Status: {r_auth.status_code}")


# ----------------------------------------------------
# 2. DATASET UPLOAD & VALIDATION (CSV, EXCEL, EDGE CASES)
# ----------------------------------------------------
print("\n--- 2. Testing Dataset Uploads & Validations ---")

# A. Valid CSV Upload
csv_content = b"product,category,quantity,price,region\nLaptop,Electronics,5,50000,Chennai\nChair,Furniture,10,3000,Bangalore\n"
csv_file = SimpleUploadedFile("audit_test_sales.csv", csv_content, content_type="text/csv")
r_upload_csv = client.post('/api/datasets/upload/', {'file': csv_file})
log_test("Valid CSV Upload", r_upload_csv.status_code == 201, f"Status: {r_upload_csv.status_code}")
created_dataset_id = r_upload_csv.json().get('dataset', {}).get('id') if r_upload_csv.status_code == 201 else None

# B. Valid Excel Upload (.xlsx)
df_sample = pd.DataFrame({
    'product': ['Phone', 'Tablet'],
    'category': ['Electronics', 'Electronics'],
    'quantity': [10, 8],
    'price': [20000, 15000],
    'region': ['Mumbai', 'Delhi']
})
excel_buf = io.BytesIO()
df_sample.to_excel(excel_buf, index=False, engine='openpyxl')
excel_buf.seek(0)
excel_file = SimpleUploadedFile("audit_test_sales.xlsx", excel_buf.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
r_upload_xlsx = client.post('/api/datasets/upload/', {'file': excel_file})
log_test("Valid Excel (.xlsx) Upload", r_upload_xlsx.status_code == 201, f"Status: {r_upload_xlsx.status_code}")

# C. Invalid Format Upload (.pdf)
fake_pdf = SimpleUploadedFile("malicious.pdf", b"%PDF-1.4 ...", content_type="application/pdf")
r_upload_invalid = client.post('/api/datasets/upload/', {'file': fake_pdf})
log_test("Invalid File Extension (.pdf) Rejected", r_upload_invalid.status_code == 400, f"Status: {r_upload_invalid.status_code}")

# D. Empty File Upload
empty_file = SimpleUploadedFile("empty.csv", b"", content_type="text/csv")
r_upload_empty = client.post('/api/datasets/upload/', {'file': empty_file})
log_test("Empty Dataset File Rejected", r_upload_empty.status_code == 400, f"Status: {r_upload_empty.status_code}")

# E. Duplicate Column Names Upload
dup_cols_file = SimpleUploadedFile("dup_cols.csv", b"col,col\n1,2\n", content_type="text/csv")
r_upload_dup = client.post('/api/datasets/upload/', {'file': dup_cols_file})
log_test("Duplicate Column Headers Rejected", r_upload_dup.status_code == 400, f"Status: {r_upload_dup.status_code}")


# ----------------------------------------------------
# 3. DATASET LISTING, PREVIEW & PERSISTENCE
# ----------------------------------------------------
print("\n--- 3. Testing Dataset Listing & Preview ---")
r_list = client.get('/api/datasets/')
datasets_list = r_list.json()
log_test("Dataset Listing Returns User Datasets", r_list.status_code == 200 and len(datasets_list) >= 2, f"Count: {len(datasets_list)}")

if created_dataset_id:
    r_prev = client.get(f'/api/datasets/{created_dataset_id}/preview/')
    preview_data = r_prev.json()
    log_test("Dataset Preview Rows & Columns", r_prev.status_code == 200 and len(preview_data.get('rows', [])) == 2, f"Rows: {len(preview_data.get('rows', []))}")


# ----------------------------------------------------
# 4. DATA INSIGHTS & EDA
# ----------------------------------------------------
print("\n--- 4. Testing Analytics & Dynamic Insights ---")
if created_dataset_id:
    # Test EDA View
    r_eda = client.get(f'/api/analytics/{created_dataset_id}/')
    log_test("EDA View Execution", r_eda.status_code == 200, f"Status: {r_eda.status_code}")

    # Test Generated Insights View
    r_insights = client.get(f'/api/analytics/insights/{created_dataset_id}/')
    ins = r_insights.json().get('insights', {})
    total_sales_correct = ins.get('total_sales_raw') == 280000.0  # 5*50000 + 10*3000 = 250000 + 30000 = 280000
    log_test("Dynamic Insights Total Sales Calculation", r_insights.status_code == 200 and total_sales_correct, f"Calculated: {ins.get('total_sales_raw')}, Expected: 280000.0")
    log_test("Dynamic Category Breakdown Present", len(ins.get('category_breakdown', [])) == 2, f"Categories: {len(ins.get('category_breakdown', []))}")
    log_test("Dynamic Top Products Present", len(ins.get('top_products', [])) == 2, f"Products: {len(ins.get('top_products', []))}")


# ----------------------------------------------------
# 5. AI ENGINE & GEMINI Q&A
# ----------------------------------------------------
print("\n--- 5. Testing Google Gemini AI Q&A ---")
if created_dataset_id:
    # A. Dataset-aware Question
    r_ai = client.post('/api/ai/ask/', {'dataset_id': created_dataset_id, 'question': 'What is the total quantity of Laptop sold?'}, content_type='application/json')
    log_test("AI Dataset-Aware Q&A Execution", r_ai.status_code == 200 and r_ai.json().get('success') is True, f"Status: {r_ai.status_code}")

    # B. Empty Question
    r_ai_empty = client.post('/api/ai/ask/', {'dataset_id': created_dataset_id, 'question': ''}, content_type='application/json')
    log_test("AI Empty Question Validation", r_ai_empty.status_code == 400, f"Status: {r_ai_empty.status_code}")

    # C. Non-existent Dataset ID
    r_ai_notfound = client.post('/api/ai/ask/', {'dataset_id': 999999, 'question': 'Show trend'}, content_type='application/json')
    log_test("AI Non-Existent Dataset Rejection", r_ai_notfound.status_code == 404, f"Status: {r_ai_notfound.status_code}")


# ----------------------------------------------------
# 6. SQL QUERY SECURITY & EXECUTION
# ----------------------------------------------------
print("\n--- 6. Testing SQL Security & Execution ---")
if created_dataset_id:
    # A. Valid SELECT Query
    valid_query = "SELECT product, price * quantity AS total_sales FROM dataset ORDER BY total_sales DESC;"
    r_sql_valid = client.post('/api/analytics/sql/', {'dataset_id': created_dataset_id, 'query': valid_query}, content_type='application/json')
    log_test("Valid SELECT SQL Query Execution", r_sql_valid.status_code == 200 and r_sql_valid.json().get('success') is True, f"Count: {r_sql_valid.json().get('results', {}).get('count')}")

    # B. Destructive SQL Prevention (DROP)
    r_sql_drop = client.post('/api/analytics/sql/', {'dataset_id': created_dataset_id, 'query': "DROP TABLE dataset"}, content_type='application/json')
    log_test("Destructive DROP Statement Blocked", r_sql_drop.status_code == 400, f"Status: {r_sql_drop.status_code}")

    # C. Destructive SQL Prevention (DELETE)
    r_sql_del = client.post('/api/analytics/sql/', {'dataset_id': created_dataset_id, 'query': "DELETE FROM dataset"}, content_type='application/json')
    log_test("Destructive DELETE Statement Blocked", r_sql_del.status_code == 400, f"Status: {r_sql_del.status_code}")

    # D. Destructive SQL Prevention (UPDATE)
    r_sql_upd = client.post('/api/analytics/sql/', {'dataset_id': created_dataset_id, 'query': "UPDATE dataset SET price=0"}, content_type='application/json')
    log_test("Destructive UPDATE Statement Blocked", r_sql_upd.status_code == 400, f"Status: {r_sql_upd.status_code}")

    # E. SQL Injection / Semicolon Stacking Blocked
    r_sql_stacked = client.post('/api/analytics/sql/', {'dataset_id': created_dataset_id, 'query': "SELECT * FROM dataset; DROP TABLE dataset;"}, content_type='application/json')
    log_test("Stacked Query SQL Injection Blocked", r_sql_stacked.status_code == 400, f"Status: {r_sql_stacked.status_code}")

    # F. Multi-tenant Dataset Isolation (User B accessing User A dataset)
    other_user, _ = User.objects.get_or_create(username='unauthorized_user')
    other_client = Client()
    other_client.force_login(other_user)
    r_sql_isolation = other_client.post('/api/analytics/sql/', {'dataset_id': created_dataset_id, 'query': "SELECT * FROM dataset"}, content_type='application/json')
    log_test("Multi-Tenant Data Isolation (Cross-User Access Blocked)", r_sql_isolation.status_code == 404, f"Status: {r_sql_isolation.status_code}")


# ----------------------------------------------------
# 7. ANALYSIS HISTORY PERSISTENCE
# ----------------------------------------------------
print("\n--- 7. Testing Analysis History Persistence ---")
r_hist = client.get('/api/analytics/history/')
hist_data = r_hist.json().get('history', [])
log_test("Analysis History Retrieved", r_hist.status_code == 200 and len(hist_data) >= 1, f"Records: {len(hist_data)}")


# ----------------------------------------------------
# 8. COMPLETE END-TO-END WORKFLOW VERIFICATION
# ----------------------------------------------------
print("\n--- 8. Testing Complete End-to-End Workflow ---")
# Workflow: Upload -> Store -> Analyze -> Insights -> Ask AI -> SQL -> History
workflow_success = True
try:
    # 1. Upload
    test_csv = SimpleUploadedFile("workflow_sales.csv", b"product,category,quantity,price\nKeyboard,Electronics,4,2500\nMouse,Electronics,10,800\n", content_type="text/csv")
    w_up = client.post('/api/datasets/upload/', {'file': test_csv})
    assert w_up.status_code == 201
    w_id = w_up.json()['dataset']['id']

    # 2. Store in MySQL verified
    db_obj = Dataset.objects.get(id=w_id, user=user)
    assert db_obj.row_count == 2
    assert os.path.exists(db_obj.file.path)

    # 3. Analyze / EDA
    w_eda = client.get(f'/api/analytics/{w_id}/')
    assert w_eda.status_code == 200

    # 4. Generate Insights
    w_ins = client.get(f'/api/analytics/insights/{w_id}/')
    assert w_ins.status_code == 200
    assert w_ins.json()['insights']['total_sales_raw'] == 18000.0  # 4*2500 + 10*800 = 10000 + 8000 = 18000

    # 5. Ask AI
    w_ai = client.post('/api/ai/ask/', {'dataset_id': w_id, 'question': 'Show revenue by product'}, content_type='application/json')
    assert w_ai.status_code == 200

    # 6. Execute SQL
    w_sql = client.post('/api/analytics/sql/', {'dataset_id': w_id, 'query': 'SELECT * FROM dataset'}, content_type='application/json')
    assert w_sql.status_code == 200

    # 7. Verify History Recorded
    w_hist = client.get('/api/analytics/history/')
    assert w_hist.status_code == 200
    assert any(h['dataset_name'] == 'workflow_sales.csv' for h in w_hist.json()['history'])

except Exception as ex:
    workflow_success = False
    print("Workflow exception:", ex)

log_test("Complete E2E Workflow (Upload -> MySQL -> Insights -> AI -> SQL -> History)", workflow_success)

print("\n=======================================================")
print(f"AUDIT SUITE COMPLETE: {len(audit_results['passed'])} PASSED, {len(audit_results['failed'])} FAILED")
print("=======================================================\n")
