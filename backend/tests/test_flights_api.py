import os
import unittest
import json
from app import app

class FlightApiTests(unittest.TestCase):
    def setUp(self):
        # Ensure master password is set so we can create an admin session
        os.environ['MASTER_ACCESS'] = 'testmaster'
        self.client = app.test_client()
        # login as admin using master password
        res = self.client.post('/api/login', json={'role':'admin', 'password':'testmaster'})
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.token = body.get('token')
        self.headers = { 'X-SESSION': self.token, 'Content-Type': 'application/json' }

    def test_create_list_delete_flight(self):
        # create flight
        payload = { 'flight': 'TST123', 'time': '2025-12-01T10:00:00Z', 'aircraft': 'A320', 'gate': 'A1', 'capacity': 10 }
        res = self.client.post('/api/flights', headers=self.headers, json=payload)
        self.assertIn(res.status_code, (200,201))
        body = res.get_json()
        self.assertIn('flight', body.get('flight', {}) if isinstance(body, dict) else {})

        # list flights and ensure our flight exists
        res2 = self.client.get('/api/flights')
        self.assertEqual(res2.status_code, 200)
        jf = res2.get_json()
        flights = jf.get('flights', [])
        found = next((f for f in flights if f.get('flight') == 'TST123'), None)
        self.assertIsNotNone(found)

        # delete flight
        res3 = self.client.delete(f"/api/flights/TST123", headers=self.headers)
        self.assertEqual(res3.status_code, 200)
        # confirm deletion
        res4 = self.client.get('/api/flights')
        flights2 = res4.get_json().get('flights', [])
        found2 = next((f for f in flights2 if f.get('flight') == 'TST123'), None)
        self.assertIsNone(found2)

if __name__ == '__main__':
    unittest.main()
