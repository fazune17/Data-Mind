from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from datasets.models import Dataset
from .models import AnalysisHistory


class AnalyticsSQLTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test_sql_user', password='password123')
        self.client = Client()
        self.client.force_login(self.user)
        csv_data = b"product,category,quantity,price\nLaptop,Electronics,5,50000\nChair,Furniture,10,3000\n"
        f = SimpleUploadedFile("sales.csv", csv_data, content_type="text/csv")
        up = self.client.post('/api/datasets/upload/', {'file': f})
        self.dataset_id = up.json()['dataset']['id']

    def test_sql_select_success(self):
        resp = self.client.post('/api/analytics/sql/', {
            'dataset_id': self.dataset_id,
            'query': 'SELECT product, price * quantity AS total FROM dataset'
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

    def test_sql_drop_blocked(self):
        resp = self.client.post('/api/analytics/sql/', {
            'dataset_id': self.dataset_id,
            'query': 'DROP TABLE dataset'
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_sql_delete_blocked(self):
        resp = self.client.post('/api/analytics/sql/', {
            'dataset_id': self.dataset_id,
            'query': 'DELETE FROM dataset'
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_sql_stacked_injection_blocked(self):
        resp = self.client.post('/api/analytics/sql/', {
            'dataset_id': self.dataset_id,
            'query': 'SELECT * FROM dataset; DROP TABLE dataset;'
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_dataset_insights_calculation(self):
        resp = self.client.get(f'/api/analytics/insights/{self.dataset_id}/')
        self.assertEqual(resp.status_code, 200)
        ins = resp.json()['insights']
        self.assertEqual(ins['total_sales_raw'], 280000.0)
        self.assertEqual(ins['best_category'], 'Electronics')
