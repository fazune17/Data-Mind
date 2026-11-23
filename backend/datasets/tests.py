from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Dataset


class DatasetUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test_user', password='password123')
        self.client = Client()
        self.client.force_login(self.user)

    def test_upload_valid_csv(self):
        csv_data = b"product,category,quantity,price\nLaptop,Electronics,5,50000\n"
        file = SimpleUploadedFile("test.csv", csv_data, content_type="text/csv")
        response = self.client.post('/api/datasets/upload/', {'file': file})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Dataset.objects.filter(user=self.user).count(), 1)

    def test_upload_invalid_extension(self):
        file = SimpleUploadedFile("test.pdf", b"pdf content", content_type="application/pdf")
        response = self.client.post('/api/datasets/upload/', {'file': file})
        self.assertEqual(response.status_code, 400)

    def test_upload_empty_file(self):
        file = SimpleUploadedFile("empty.csv", b"", content_type="text/csv")
        response = self.client.post('/api/datasets/upload/', {'file': file})
        self.assertEqual(response.status_code, 400)

    def test_upload_duplicate_columns(self):
        file = SimpleUploadedFile("dup.csv", b"col,col\n1,2\n", content_type="text/csv")
        response = self.client.post('/api/datasets/upload/', {'file': file})
        self.assertEqual(response.status_code, 400)
