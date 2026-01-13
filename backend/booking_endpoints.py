"""
API Endpoints for unified passenger booking, check-in, and revenue tracking.
Import these into app.py and register them with the Flask app.
"""

from flask import request, jsonify
from integration_module import (
    register_passenger_booking,
    check_in_passenger,
    select_seat,
    get_flight_occupancy,
    get_revenue_summary
)


def register_booking_endpoints(app, _require_session):
    """Register all booking-related endpoints with the Flask app."""
    
    @app.route('/api/register', methods=['POST'])
    def api_register_passenger():
        """
        Register/Book a passenger. Updates bookings, passengers, flights, and revenue.
        
        Request body:
        {
            "name": "John Doe",
            "passport": "P1234567",
            "email": "john@example.com",
            "flight": "SMA001",
            "from": "JFK",
            "to": "LHR",
            "seat_class": "Economy",
            "amount": 250.00,
            "currency": "USD",
            "payment_method": "card"
        }
        
        Response: { ok: bool, booking_ref: str, message: str, passenger: {...} }
        """
        try:
            data = request.get_json(silent=True) or {}
            
            name = (data.get('name') or '').strip()
            passport = (data.get('passport') or '').strip()
            email = (data.get('email') or '').strip()
            flight = (data.get('flight') or '').strip()
            from_airport = (data.get('from') or '').strip()
            to_airport = (data.get('to') or '').strip()
            seat_class = (data.get('seat_class') or 'Economy').strip()
            amount = float(data.get('amount') or 0)
            currency = (data.get('currency') or 'USD').strip()
            payment_method = (data.get('payment_method') or 'card').strip()
            
            # Validate required fields
            if not all([name, passport, email, flight, from_airport, to_airport]):
                return jsonify({'error': 'Missing required fields'}), 400
            
            # Register the booking
            success, booking_id, message = register_passenger_booking(
                name, passport, email, flight, from_airport, to_airport,
                seat_class, amount, currency, payment_method
            )
            
            if not success:
                return jsonify({'error': message}), 400
            
            return jsonify({
                'ok': True,
                'booking_ref': booking_id,
                'message': message,
                'passenger': {
                    'name': name,
                    'passport': passport,
                    'email': email,
                    'flight': flight,
                    'booking_ref': booking_id
                }
            }), 201
            
        except Exception as e:
            return jsonify({'error': f'Booking failed: {str(e)}'}), 500
    
    
    @app.route('/api/checkin', methods=['POST'])
    def api_checkin_passenger():
        """
        Check in a passenger and optionally select a seat.
        
        Request body:
        {
            "passport": "P1234567",
            "flight": "SMA001",
            "seat": "12A"  (optional)
        }
        
        Response: { ok: bool, seat: str, boarding_pass: str, message: str }
        """
        try:
            data = request.get_json(silent=True) or {}
            
            passport = (data.get('passport') or '').strip()
            flight = (data.get('flight') or '').strip()
            seat = (data.get('seat') or '').strip() or None
            
            if not passport or not flight:
                return jsonify({'error': 'passport and flight are required'}), 400
            
            success, assigned_seat, boarding_pass_id, message = check_in_passenger(passport, flight, seat)
            
            if not success:
                return jsonify({'error': message}), 400
            
            return jsonify({
                'ok': True,
                'seat': assigned_seat,
                'boarding_pass': boarding_pass_id,
                'message': message
            }), 200
            
        except Exception as e:
            return jsonify({'error': f'Check-in failed: {str(e)}'}), 500
    
    
    @app.route('/api/seat/select', methods=['POST'])
    def api_select_seat():
        """
        Select a specific seat for a passenger.
        
        Request body:
        {
            "passport": "P1234567",
            "flight": "SMA001",
            "seat": "12A"
        }
        
        Response: { ok: bool, message: str }
        """
        try:
            data = request.get_json(silent=True) or {}
            
            passport = (data.get('passport') or '').strip()
            flight = (data.get('flight') or '').strip()
            seat = (data.get('seat') or '').strip()
            
            if not all([passport, flight, seat]):
                return jsonify({'error': 'passport, flight, and seat are required'}), 400
            
            success, message = select_seat(passport, flight, seat)
            
            if not success:
                return jsonify({'error': message}), 400
            
            return jsonify({
                'ok': True,
                'message': message
            }), 200
            
        except Exception as e:
            return jsonify({'error': f'Seat selection failed: {str(e)}'}), 500
    
    
    @app.route('/api/flights/<flight_id>/occupancy', methods=['GET'])
    def api_get_flight_occupancy(flight_id):
        """
        Get real-time occupancy information for a flight.
        
        Response: { flight, total_capacity, booked, checked_in, available, occupancy_percent }
        """
        try:
            occupancy = get_flight_occupancy(flight_id)
            
            if not occupancy:
                return jsonify({'error': 'Flight not found'}), 404
            
            return jsonify(occupancy), 200
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    
    @app.route('/api/revenue/summary', methods=['GET'])
    def api_get_revenue_summary():
        """
        Get revenue summary (admin only).
        
        Response: { total_revenue, transaction_count, by_type: {...}, by_date: {...} }
        """
        try:
            # Check admin authorization
            session = _require_session(request, require_role='admin')
            if not session:
                return jsonify({'error': 'Admin access required'}), 401
            
            summary = get_revenue_summary()
            return jsonify(summary), 200
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
