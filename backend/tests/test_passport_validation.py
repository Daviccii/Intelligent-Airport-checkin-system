import unittest
from security_utils import validate_passport

class TestPassportValidation(unittest.TestCase):
    def test_valid_simple(self):
        ok, reason = validate_passport('A1234567')
        self.assertTrue(ok)
        self.assertEqual(reason, '')

    def test_too_short(self):
        ok, reason = validate_passport('AB')
        self.assertFalse(ok)
        self.assertEqual(reason, 'passport_length_invalid')

    def test_too_long(self):
        ok, reason = validate_passport('A'*30)
        self.assertFalse(ok)
        self.assertEqual(reason, 'passport_length_invalid')

    def test_invalid_chars(self):
        ok, reason = validate_passport('AB@123')
        self.assertFalse(ok)
        self.assertEqual(reason, 'passport_chars_invalid')

    def test_empty(self):
        ok, reason = validate_passport('')
        self.assertFalse(ok)
        self.assertEqual(reason, 'passport_required')

if __name__ == '__main__':
    unittest.main()
