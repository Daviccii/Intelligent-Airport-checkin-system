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
from activity_tracker import log_activity, get_payments_log


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
            
            # Log payment activity for admin dashboard
            log_activity('payment', {
                'booking_ref': booking_id,
                'passenger_name': name,
                'passport': passport,
                'email': email,
                'flight': flight,
                'amount': amount,
                'currency': currency,
                'payment_method': payment_method,
                'status': 'completed',
                'payment_status': 'completed'
            })
            
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
    
    
    @app.route('/api/activities/payments', methods=['GET'])
    def api_get_payments():
        """
        Get all payment activities for admin dashboard.
        
        Response: [{ id, type, timestamp, data: {...} }, ...]
        """
        try:
            payments = get_payments_log()
            return jsonify(payments), 200
        except Exception as e:
            return jsonify({'error': str(e), 'payments': []}), 200
    
    
    @app.route('/api/activities/log', methods=['POST'])
    def api_log_activity():
        """
        Log an activity (booking, payment, checkin, etc.) for admin/staff tracking.
        
        Request body:
        {
            "type": "payment|booking|checkin|flight_status",
            "data": { ... activity-specific data ... }
        }
        
        Response: { ok: bool, activity: {...} }
        """
        try:
            data = request.get_json(silent=True) or {}
            activity_type = data.get('type', 'unknown')
            activity_data = data.get('data', {})
            
            # Log the activity
            activity = log_activity(activity_type, activity_data)
            
            if activity:
                return jsonify({'ok': True, 'activity': activity}), 200
            else:
                return jsonify({'ok': False, 'error': 'Failed to log activity'}), 500
                
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500
    
    
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
    
    
    @app.route('/api/booking/lookup', methods=['GET'])
    def api_lookup_booking():
        """
        Lookup booking details by reference number and email.
        Query params: ref (booking reference), email (passenger email)
        Response: { ok: bool, booking: {...} }
        """
        try:
            import json
            import os
            
            booking_ref = request.args.get('ref', '').strip()
            email = request.args.get('email', '').strip()
            
            if not booking_ref:
                return jsonify({'error': 'Booking reference is required'}), 400
            
            # Load bookings from file
            base_dir = os.path.dirname(os.path.abspath(__file__))
            bookings_file = os.path.join(base_dir, 'bookings.json')
            
            if not os.path.exists(bookings_file):
                return jsonify({'error': 'No bookings found'}), 404
            
            with open(bookings_file, 'r') as f:
                bookings = json.load(f)
            
            # Find matching booking - check both booking_ref and booking_reference
            for booking in bookings:
                ref_value = booking.get('booking_ref') or booking.get('booking_reference')
                if ref_value == booking_ref:
                    # If email provided, verify it matches
                    if email and booking.get('email', '').lower() != email.lower():
                        return jsonify({'error': 'Booking reference and email do not match'}), 403
                    
                    return jsonify({
                        'ok': True,
                        'booking': booking
                    }), 200
            
            return jsonify({'error': 'Booking not found'}), 404
            
        except Exception as e:
            return jsonify({'error': f'Lookup failed: {str(e)}'}), 500
    
    
    @app.route('/api/booking/search-by-passport', methods=['GET'])
    def api_search_booking_by_passport():
        """
        Search for booking by passport number and/or email/name.
        Query params: passport (optional), email (optional)
        Response: { ok: bool, bookings: [...] } - list of matching bookings
        """
        try:
            import json
            import os
            
            passport = request.args.get('passport', '').strip()
            email = request.args.get('email', '').strip().lower()
            name = request.args.get('name', '').strip().lower()
            
            if not passport and not email and not name:
                return jsonify({'error': 'At least one search parameter (passport, email, or name) is required'}), 400
            
            # Load bookings from file
            base_dir = os.path.dirname(os.path.abspath(__file__))
            bookings_file = os.path.join(base_dir, 'bookings.json')
            
            if not os.path.exists(bookings_file):
                return jsonify({'error': 'No bookings found'}), 404
            
            with open(bookings_file, 'r') as f:
                bookings = json.load(f)
            
            # Find all matching bookings
            matching_bookings = []
            for booking in bookings:
                match = False
                
                # Check passport if provided
                if passport:
                    booking_passport = (booking.get('passport') or '').strip()
                    if booking_passport.upper() == passport.upper():
                        match = True
                
                # Check email if provided
                if email:
                    booking_email = (booking.get('email') or '').strip().lower()
                    if booking_email == email:
                        match = True
                    # Reset if we're looking for both and first didn't match
                    elif passport:
                        match = False
                
                # Check name if provided
                if name:
                    booking_name = (booking.get('passenger_name') or '').strip().lower()
                    if name in booking_name or booking_name in name:
                        # If other criteria were provided, ensure they match too
                        if email:
                            booking_email = (booking.get('email') or '').strip().lower()
                            if booking_email == email:
                                match = True
                            else:
                                match = False
                        elif passport:
                            booking_passport = (booking.get('passport') or '').strip()
                            if booking_passport.upper() == passport.upper():
                                match = True
                            else:
                                match = False
                        else:
                            match = True
                
                if match:
                    matching_bookings.append(booking)
            
            if not matching_bookings:
                return jsonify({'error': 'No bookings found matching the provided information'}), 404
            
            return jsonify({
                'ok': True,
                'count': len(matching_bookings),
                'bookings': matching_bookings
            }), 200
            
        except Exception as e:
            return jsonify({'error': f'Search failed: {str(e)}'}), 500
