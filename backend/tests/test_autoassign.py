import unittest

# import helper from app module
from app import autoassign_seat_from_capacity

class TestAutoassign(unittest.TestCase):
    def test_assign_window_pref(self):
        # capacity 6, none taken
        seat = autoassign_seat_from_capacity(6, existing_seats=[], blocked_seats=[], preference='window')
        # first window seat is 1A
        self.assertEqual(seat, '1A')

    def test_assign_aisle_pref(self):
        seat = autoassign_seat_from_capacity(6, existing_seats=[], blocked_seats=[], preference='aisle')
        # first aisle seat is 1C
        self.assertEqual(seat, '1C')

    def test_assign_middle_pref(self):
        seat = autoassign_seat_from_capacity(6, existing_seats=[], blocked_seats=[], preference='middle')
        # first middle seat is 1B
        self.assertEqual(seat, '1B')

    def test_pref_respects_taken_and_blocked(self):
        # mark 1A taken and 1C blocked, window pref should skip 1A and pick 2A (or next window available)
        seat = autoassign_seat_from_capacity(12, existing_seats=['1A'], blocked_seats=['1C'], preference='window')
        # next window seat after 1A is 2A (since 1F is also window, but order in generation is row-major 1A..1F then 2A..)
        self.assertTrue(seat in ('1F','2A','2F'))

    def test_no_seats_available(self):
        seat = autoassign_seat_from_capacity(2, existing_seats=['1A','1B'], blocked_seats=[], preference='any')
        self.assertIsNone(seat)

if __name__ == '__main__':
    unittest.main()
