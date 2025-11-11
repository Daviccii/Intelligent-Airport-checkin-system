import os
import io
import unittest
from app import app, passengers, save_passengers

class PassengerFlowTests(unittest.TestCase):
    def setUp(self):
        # ensure clean passengers list backup
        self._orig = list(passengers)
        passengers.clear()
        save_passengers()
        os.environ['MASTER_ACCESS'] = 'mastertest'
        self.client = app.test_client()

    def tearDown(self):
        # restore passengers
        passengers.clear()
        passengers.extend(self._orig)
        save_passengers()

    def test_register_login_checkin_and_boardingpass(self):
        # Register a passenger via /api/register
        reg = { 'name': 'Test User', 'passport': 'TP12345', 'flight': 'FL-TST', 'email': 'test@example.com' }
        res = self.client.post('/api/register', json=reg)
        self.assertEqual(res.status_code, 201)
        body = res.get_json()
        self.assertEqual(body.get('passport'), 'TP12345')

        # Login as passenger
        res2 = self.client.post('/api/login', json={'role':'passenger','passport':'TP12345','name':'Test User'})
        self.assertEqual(res2.status_code, 200)
        token = res2.get_json().get('token')
        headers = { 'X-SESSION': token }

        # Checkin (use session) for that passenger
        payload = { 'flight': 'FL-TST', 'passengers': [ { 'name': 'Test User', 'passport': 'TP12345', 'baggage_count': 2 } ] }
        res3 = self.client.post('/api/checkin', headers=headers, json=payload)
        self.assertEqual(res3.status_code, 200)
        results = res3.get_json().get('results', [])
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0].get('status'), 'ok')

        # Request boarding pass (should succeed with session)
        res4 = self.client.get(f"/api/boardingpass?passport=TP12345", headers=headers)
        self.assertEqual(res4.status_code, 200)
        # response should be image/png bytes
        self.assertTrue('image' in res4.content_type)

if __name__ == '__main__':
    unittest.main()
