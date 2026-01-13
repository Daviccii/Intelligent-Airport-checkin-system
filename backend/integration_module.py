"""
Integration module for connecting passenger booking, check-in, seat selection, and revenue tracking.
This module provides unified functions to synchronize flight occupancy, passenger records, and revenue data.
"""

import json
import os
from datetime import datetime, timezone
from activity_tracker import log_activity

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
BOOKINGS_FILE = os.path.join(BASE_DIR, 'bookings.json')
PASSENGERS_FILE = os.path.join(BASE_DIR, 'passengers.json')
FLIGHTS_FILE = os.path.join(BASE_DIR, 'flights.json')
REVENUE_FILE = os.path.join(BASE_DIR, 'revenue.json')
EVENTS_FILE = os.path.join(BASE_DIR, 'events.json')


def load_json(path, default=None):
    """Load JSON file with fallback to default."""
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f) or default
    except Exception:
        pass
    return default if default is not None else {}


def save_json(path, data):
    """Save JSON file safely."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving {path}: {e}")
        return False


def register_passenger_booking(name, passport, email, flight, from_airport, to_airport, 
                               seat_class='Economy', amount=0, currency='USD', payment_method='card'):
    """
    Register a new passenger booking and update:
    1. Bookings file
    2. Passengers list
    3. Flight occupancy
    4. Revenue tracking
    
    Returns: (success: bool, booking_id: str, message: str)
    """
    try:
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        booking_id = f"BK{passport}{flight}{int(datetime.now().timestamp())}"[-15:]
        
        # 1. Create booking record
        booking = {
            'booking_ref': booking_id,
            'id': booking_id,
            'name': name,
            'email': email,
            'passport': passport,
            'flight': flight,
            'from': from_airport,
            'to': to_airport,
            'class': seat_class,
            'amount': float(amount),
            'currency': currency,
            'payment_method': payment_method,
            'status': 'completed',
            'created_at': timestamp,
            'updated_at': timestamp
        }
        
        # 2. Add to bookings file
        bookings = load_json(BOOKINGS_FILE, [])
        if not isinstance(bookings, list):
            bookings = []
        bookings.append(booking)
        save_json(BOOKINGS_FILE, bookings)
        
        # 3. Create/Update passenger record
        passenger = {
            'name': name,
            'passport': passport,
            'email': email,
            'flight': flight,
            'from': from_airport,
            'to': to_airport,
            'seat': None,  # Will be assigned during check-in
            'seat_class': seat_class,
            'booking_ref': booking_id,
            'checked_in': False,
            'boarding_pass': None,
            'baggage_count': 0,
            'baggage_paid': False,
            'special_requests': '',
            'admin_notes': '',
            'created_at': timestamp,
            'updated_at': timestamp
        }
        
        passengers = load_json(PASSENGERS_FILE, [])
        if not isinstance(passengers, list):
            passengers = []
        # Avoid duplicates
        passengers = [p for p in passengers if p.get('passport') != passport or p.get('flight') != flight]
        passengers.append(passenger)
        save_json(PASSENGERS_FILE, passengers)
        
        # 4. Update flight occupancy
        flights = load_json(FLIGHTS_FILE, [])
        if not isinstance(flights, list):
            flights = []
        
        for f in flights:
            flight_keys = {f.get('flight'), f.get('flight_number'), f.get('id')}
            if flight in flight_keys:
                # Normalize stored flight key for consistency
                if not f.get('flight'):
                    f['flight'] = f.get('flight_number') or flight
                # Update bookings count
                current_bookings = f.get('bookings', 0)
                f['bookings'] = current_bookings + 1
                f['booked_seats'] = f.get('booked_seats', 0) + 1
                break
        
        save_json(FLIGHTS_FILE, flights)
        
        # 5. Update revenue
        add_revenue_entry(booking_id, name, passport, flight, float(amount), currency, 'booking', timestamp)
        
        # 6. Log activity
        log_activity('booking', {
            'booking_ref': booking_id,
            'passenger_name': name,
            'passport': passport,
            'flight': flight,
            'amount': float(amount),
            'currency': currency
        })
        
        return True, booking_id, f"Booking {booking_id} created successfully"
        
    except Exception as e:
        return False, None, f"Booking failed: {str(e)}"


def check_in_passenger(passport, flight, seat=None):
    """
    Check in a passenger and:
    1. Update passenger check-in status
    2. Assign seat if not already assigned
    3. Generate boarding pass
    4. Log activity
    
    Returns: (success: bool, seat: str, boarding_pass_id: str, message: str)
    """
    try:
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        # Load passengers
        passengers = load_json(PASSENGERS_FILE, [])
        if not isinstance(passengers, list):
            passengers = []
        
        # Find passenger
        passenger = None
        for p in passengers:
            if p.get('passport') == passport and p.get('flight') == flight:
                passenger = p
                break
        
        if not passenger:
            return False, None, None, f"Passenger {passport} not found on flight {flight}"
        
        # Assign seat if not already assigned
        if not passenger.get('seat') and seat:
            passenger['seat'] = seat
        elif not passenger.get('seat'):
            # Auto-assign a seat (simple sequential assignment)
            seat = auto_assign_seat(flight, passenger.get('seat_class', 'Economy'))
            passenger['seat'] = seat
        else:
            seat = passenger.get('seat')
        
        # Generate boarding pass
        boarding_pass_id = f"BP{passport}{flight}{int(datetime.now().timestamp())}"[-15:]
        boarding_pass = {
            'id': boarding_pass_id,
            'flight': flight,
            'seat': seat,
            'passenger': passenger.get('name'),
            'created_at': timestamp
        }
        
        # Update passenger record
        passenger['checked_in'] = True
        passenger['boarding_pass'] = boarding_pass
        passenger['updated_at'] = timestamp
        
        save_json(PASSENGERS_FILE, passengers)
        
        # Update flight check-in count
        flights = load_json(FLIGHTS_FILE, [])
        if not isinstance(flights, list):
            flights = []
        
        for f in flights:
            flight_keys = {f.get('flight'), f.get('flight_number'), f.get('id')}
            if flight in flight_keys:
                if not f.get('flight'):
                    f['flight'] = f.get('flight_number') or flight
                f['checked_in'] = f.get('checked_in', 0) + 1
                break
        
        save_json(FLIGHTS_FILE, flights)
        
        # Log activity
        log_activity('checkin', {
            'passenger': passenger.get('name'),
            'passport': passport,
            'flight': flight,
            'seat': seat,
            'boarding_pass': boarding_pass_id
        })
        
        return True, seat, boarding_pass_id, f"Check-in successful. Seat: {seat}"
        
    except Exception as e:
        return False, None, None, f"Check-in failed: {str(e)}"


def select_seat(passport, flight, seat):
    """
    Assign a seat to a passenger.
    
    Returns: (success: bool, message: str)
    """
    try:
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        passengers = load_json(PASSENGERS_FILE, [])
        if not isinstance(passengers, list):
            passengers = []
        
        # Find and update passenger
        found = False
        for p in passengers:
            if p.get('passport') == passport and p.get('flight') == flight:
                p['seat'] = seat
                p['updated_at'] = timestamp
                found = True
                break
        
        if not found:
            return False, f"Passenger {passport} not found on flight {flight}"
        
        save_json(PASSENGERS_FILE, passengers)
        
        # Log activity
        log_activity('seat_selection', {
            'passport': passport,
            'flight': flight,
            'seat': seat
        })
        
        return True, f"Seat {seat} selected successfully"
        
    except Exception as e:
        return False, f"Seat selection failed: {str(e)}"


def auto_assign_seat(flight, seat_class='Economy'):
    """
    Automatically assign the next available seat for a passenger.
    Uses a simple sequential numbering system.
    
    Returns: seat_number (str like '12A', '12B', etc.)
    """
    try:
        passengers = load_json(PASSENGERS_FILE, [])
        if not isinstance(passengers, list):
            passengers = []
        
        # Count passengers already on this flight
        count = sum(1 for p in passengers if p.get('flight') == flight)
        
        # Simple mapping: row 1-40, columns A-F
        row = (count // 6) + 1
        col_map = {0: 'A', 1: 'B', 2: 'C', 3: 'D', 4: 'E', 5: 'F'}
        col = col_map.get(count % 6, 'A')
        
        return f"{row}{col}"
    except Exception:
        return f"{1 + (int(__import__('random').random() * 40))}{chr(65 + int(__import__('random').random() * 6))}"


def add_revenue_entry(transaction_id, passenger_name, passport, flight, amount, currency, transaction_type, timestamp):
    """
    Add revenue entry and update total revenue.
    
    Transaction types: 'booking', 'checkin', 'baggage', 'seat_upgrade', 'meal', 'other'
    """
    try:
        revenue_data = load_json(REVENUE_FILE, {'total': 0, 'by_date': {}, 'transactions': []})
        if not isinstance(revenue_data, dict):
            revenue_data = {'total': 0, 'by_date': {}, 'transactions': []}
        
        # Ensure required fields
        if 'total' not in revenue_data:
            revenue_data['total'] = 0
        if 'by_date' not in revenue_data:
            revenue_data['by_date'] = {}
        if 'transactions' not in revenue_data:
            revenue_data['transactions'] = []
        
        # Add transaction
        transaction = {
            'id': transaction_id,
            'passenger': passenger_name,
            'passport': passport,
            'flight': flight,
            'amount': float(amount),
            'currency': currency,
            'type': transaction_type,
            'timestamp': timestamp
        }
        
        revenue_data['transactions'].append(transaction)
        
        # Update total
        revenue_data['total'] = float(revenue_data.get('total', 0)) + float(amount)
        
        # Update by-date summary
        date_key = timestamp.split('T')[0]  # YYYY-MM-DD
        if date_key not in revenue_data['by_date']:
            revenue_data['by_date'][date_key] = {'total': 0, 'count': 0}
        
        revenue_data['by_date'][date_key]['total'] = float(revenue_data['by_date'][date_key].get('total', 0)) + float(amount)
        revenue_data['by_date'][date_key]['count'] = int(revenue_data['by_date'][date_key].get('count', 0)) + 1
        
        save_json(REVENUE_FILE, revenue_data)
        
        return True
        
    except Exception as e:
        print(f"Revenue update error: {e}")
        return False


def get_flight_occupancy(flight):
    """
    Get detailed occupancy info for a flight.
    
    Returns: { flight, total_capacity, booked, checked_in, available, occupancy_percent }
    """
    try:
        flights = load_json(FLIGHTS_FILE, [])
        passengers = load_json(PASSENGERS_FILE, [])
        
        flight_data = None
        for f in flights:
            if f.get('flight') == flight:
                flight_data = f
                break
        
        if not flight_data:
            return None
        
        capacity = int(flight_data.get('capacity', 0))
        booked = sum(1 for p in passengers if p.get('flight') == flight)
        checked_in = sum(1 for p in passengers if p.get('flight') == flight and p.get('checked_in'))
        available = max(0, capacity - booked)
        occupancy = round((booked / capacity * 100) if capacity > 0 else 0, 1)
        
        return {
            'flight': flight,
            'total_capacity': capacity,
            'booked': booked,
            'checked_in': checked_in,
            'available': available,
            'occupancy_percent': occupancy
        }
    except Exception:
        return None


def get_revenue_summary():
    """
    Get overall revenue summary.
    
    Returns: { total_revenue, transaction_count, by_type: {}, by_date: {} }
    """
    try:
        revenue_data = load_json(REVENUE_FILE, {'total': 0, 'by_date': {}, 'transactions': []})
        
        transactions = revenue_data.get('transactions', [])
        by_type = {}
        
        for t in transactions:
            ttype = t.get('type', 'other')
            if ttype not in by_type:
                by_type[ttype] = {'count': 0, 'total': 0}
            by_type[ttype]['count'] += 1
            by_type[ttype]['total'] += float(t.get('amount', 0))
        
        return {
            'total_revenue': float(revenue_data.get('total', 0)),
            'transaction_count': len(transactions),
            'by_type': by_type,
            'by_date': revenue_data.get('by_date', {})
        }
    except Exception:
        return {'total_revenue': 0, 'transaction_count': 0, 'by_type': {}, 'by_date': {}}
