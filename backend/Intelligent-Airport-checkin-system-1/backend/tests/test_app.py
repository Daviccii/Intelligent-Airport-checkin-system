import json
import os
import unittest
from unittest.mock import patch, MagicMock
from app import passengers, save_passengers, register_passenger, view_passengers

class TestAirportCheckinSystem(unittest.TestCase):

    @patch('builtins.input', side_effect=['John Doe', '123456', 'AA101'])
    def test_register_passenger(self, mock_input):
        initial_count = len(passengers)
        register_passenger()
        self.assertEqual(len(passengers), initial_count + 1)
        self.assertEqual(passengers[-1]['name'], 'John Doe')
        self.assertEqual(passengers[-1]['passport'], '123456')
        self.assertEqual(passengers[-1]['flight'], 'AA101')
        self.assertEqual(passengers[-1]['seat'], initial_count + 1)

    @patch('builtins.input', side_effect=['John Doe', '123456', 'AA101'])
    def test_register_duplicate_passenger(self, mock_input):
        register_passenger()  # Register first time
        initial_count = len(passengers)
        register_passenger()  # Attempt to register again
        self.assertEqual(len(passengers), initial_count)  # Count should not change

    def test_view_passengers(self):
        with patch('builtins.print') as mock_print:
            view_passengers()
            if passengers:
                mock_print.assert_called()  # Ensure print was called if there are passengers
            else:
                mock_print.assert_called_once_with("\nNo passengers registered yet.\n")

if __name__ == '__main__':
    unittest.main()