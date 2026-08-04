"""
Dynamic Booking API Endpoints
API endpoints for dynamic flight scheduling, pricing, and seat maps
"""

from flask import request, jsonify
from datetime import datetime, timedelta, timezone
from dynamic_scheduler import DynamicScheduler
from dynamic_seat_map import DynamicSeatMap
from pricing_engine import PricingEngine
import json


def register_dynamic_booking_endpoints(app):
    """Register all dynamic booking endpoints with the Flask app"""
    
    # Initialize engines
    pricing_engine = PricingEngine()
    scheduler = DynamicScheduler(pricing_engine)
    
    def _load_aircraft_config():
        """Load aircraft configuration"""
        try:
            with open('aircraft_config.json', 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    
    @app.route('/api/dynamic/flights/generate', methods=['POST', 'OPTIONS'])
    def api_generate_dynamic_flights():
        """
        Generate dynamic flights for a route and date range
        
        Request body:
        {
            "origin": "NBO",
            "destination": "MBA",
            "start_date": "2026-07-26",
            "end_date": "2026-08-26",
            "days_ahead": 30
        }
        
        Response: { flights: [...], count: int, generated_at: str }
        """
        # Handle OPTIONS request for CORS
        if request.method == 'OPTIONS':
            return '', 204
        
        try:
            data = request.get_json(silent=True) or {}
            
            origin = (data.get('origin') or '').strip().upper()
            destination = (data.get('destination') or '').strip().upper()
            start_date_str = data.get('start_date')
            end_date_str = data.get('end_date')
            days_ahead = data.get('days_ahead', 30)
            
            if not all([origin, destination, start_date_str]):
                return jsonify({'error': 'Missing required fields: origin, destination, start_date'}), 400
            
            # Parse dates
            try:
                start_date = datetime.fromisoformat(start_date_str)
                if end_date_str:
                    end_date = datetime.fromisoformat(end_date_str)
                else:
                    end_date = start_date + timedelta(days=days_ahead)
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use ISO format (YYYY-MM-DD)'}), 400
            
            # Generate flights
            flights = scheduler.generate_flights_for_route(
                origin, destination, start_date, end_date, days_ahead
            )
            
            return jsonify({
                'flights': flights,
                'count': len(flights),
                'route': f"{origin}-{destination}",
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'generated_at': datetime.now(timezone.utc).isoformat()
            }), 200
            
        except Exception as e:
            return jsonify({'error': f'Flight generation failed: {str(e)}'}), 500
    
    @app.route('/api/dynamic/flights/search', methods=['POST', 'OPTIONS'])
    def api_search_dynamic_flights():
        """
        Search for available flights dynamically
        
        Request body:
        {
            "origin": "NBO",
            "destination": "MBA",
            "departure_date": "2026-07-26",
            "passengers": 1,
            "seat_class": "Economy"
        }
        
        Response: { flights: [...], search_params: {...} }
        """
        # Handle OPTIONS request for CORS
        if request.method == 'OPTIONS':
            return '', 204
        
        try:
            data = request.get_json(silent=True) or {}
            
            origin = (data.get('origin') or '').strip().upper()
            destination = (data.get('destination') or '').strip().upper()
            departure_date_str = data.get('departure_date')
            passengers = data.get('passengers', 1)
            seat_class = data.get('seat_class', 'Economy')
            
            if not all([origin, destination, departure_date_str]):
                return jsonify({'error': 'Missing required fields'}), 400
            
            # Parse departure date
            try:
                departure_date = datetime.fromisoformat(departure_date_str)
            except ValueError:
                return jsonify({'error': 'Invalid date format'}), 400
            
            # Generate flights for the specific date
            end_date = departure_date + timedelta(days=1)
            flights = scheduler.generate_flights_for_route(
                origin, destination, departure_date, end_date, 1
            )
            
            # Add dynamic pricing to each flight
            for flight in flights:
                dynamic_price = scheduler.get_dynamic_price(
                    flight['id'], seat_class, passengers
                )
                flight['dynamic_pricing'] = dynamic_price
                flight['available_seats'] = flight['capacity'] - flight['booked_seats']
            
            # Filter flights with enough availability
            available_flights = [
                f for f in flights if f['available_seats'] >= passengers
            ]
            
            return jsonify({
                'flights': available_flights,
                'count': len(available_flights),
                'search_params': {
                    'origin': origin,
                    'destination': destination,
                    'departure_date': departure_date_str,
                    'passengers': passengers,
                    'seat_class': seat_class
                },
                'searched_at': datetime.now(timezone.utc).isoformat()
            }), 200
            
        except Exception as e:
            return jsonify({'error': f'Flight search failed: {str(e)}'}), 500
    
    @app.route('/api/dynamic/price/calculate', methods=['POST', 'OPTIONS'])
    def api_calculate_dynamic_price():
        """
        Calculate dynamic price for a specific flight
        
        Request body:
        {
            "flight_id": "FLT_NBOMBA_202607261200",
            "seat_class": "Economy",
            "passengers": 1,
            "origin": "NBO",
            "destination": "MBA",
            "airline": "Kenya Airways",
            "aircraft": "Boeing 737-800"
        }
        
        Response: { price_details: {...} }
        """
        # Handle OPTIONS request for CORS
        if request.method == 'OPTIONS':
            return '', 204
        
        try:
            data = request.get_json(silent=True) or {}
            
            flight_id = data.get('flight_id', '')
            seat_class = data.get('seat_class', 'Economy')
            passengers = data.get('passengers', 1)
            origin = data.get('origin', '').strip().upper()
            destination = data.get('destination', '').strip().upper()
            airline = data.get('airline', 'Kenya Airways')
            aircraft = data.get('aircraft', 'Boeing 737-800')
            
            # Calculate base price using pricing engine
            price_result = pricing_engine.calculate_price(
                origin, destination, airline, aircraft
            )
            # Extract the final price from the result dictionary
            base_price = price_result.get('final_price', price_result.get('base_price', 10000)) if isinstance(price_result, dict) else price_result
            
            # Get dynamic pricing
            dynamic_price = scheduler.get_dynamic_price(
                flight_id, seat_class, passengers
            )
            
            # Override base price with calculated one
            dynamic_price['base_price'] = base_price
            # Handle if base_price is still a dictionary (fallback)
            if isinstance(base_price, dict):
                base_price = base_price.get('final_price', base_price.get('base_price', 10000))
            dynamic_price['final_price'] = base_price * dynamic_price['class_multiplier']
            
            return jsonify({
                'price_details': dynamic_price,
                'flight_info': {
                    'flight_id': flight_id,
                    'origin': origin,
                    'destination': destination,
                    'airline': airline,
                    'aircraft': aircraft
                },
                'calculated_at': datetime.now(timezone.utc).isoformat()
            }), 200
            
        except Exception as e:
            return jsonify({'error': f'Price calculation failed: {str(e)}'}), 500
    
    @app.route('/api/dynamic/seatmap/generate', methods=['POST', 'OPTIONS'])
    def api_generate_seat_map():
        """
        Generate dynamic seat map for an aircraft
        
        Request body:
        {
            "aircraft_type": "Boeing 737-800",
            "booked_seats": ["1A", "1B"],
            "seat_class": "Economy"
        }
        
        Response: { seat_map: {...} }
        """
        # Handle OPTIONS request for CORS
        if request.method == 'OPTIONS':
            return '', 204
        
        try:
            data = request.get_json(silent=True) or {}
            
            aircraft_type = data.get('aircraft_type', 'Boeing 737-800')
            booked_seats = data.get('booked_seats', [])
            seat_class = data.get('seat_class', 'Economy')
            
            # Load aircraft config
            aircraft_config = _load_aircraft_config()
            
            # Find matching aircraft config
            matched_config = None
            for code, config in aircraft_config.items():
                if aircraft_type in config.get('name', ''):
                    matched_config = config
                    break
            
            if not matched_config:
                # Use default config
                matched_config = {
                    'name': aircraft_type,
                    'capacity': 180,
                    'seat_map': {
                        'rows': 30,
                        'columns': 6,
                        'layout': '3-3',
                        'blocked_seats': ['1A', '1F'],
                        'emergency_exits': [13, 14],
                        'priority_seats': ['11A', '11B', '11C', '11D', '11E', '11F']
                    }
                }
            
            # Generate seat map
            seat_map_generator = DynamicSeatMap(matched_config)
            seat_map = seat_map_generator.generate_seat_map(
                booked_seats=booked_seats,
                seat_class=seat_class
            )
            
            return jsonify({
                'seat_map': seat_map,
                'generated_at': datetime.now(timezone.utc).isoformat()
            }), 200
            
        except Exception as e:
            return jsonify({'error': f'Seat map generation failed: {str(e)}'}), 500
    
    @app.route('/api/dynamic/seatmap/price', methods=['POST', 'OPTIONS'])
    def api_get_seat_price():
        """
        Get pricing for a specific seat
        
        Request body:
        {
            "aircraft_type": "Boeing 737-800",
            "seat_id": "12A",
            "base_price": 10000,
            "seat_class": "Economy"
        }
        
        Response: { seat_pricing: {...} }
        """
        # Handle OPTIONS request for CORS
        if request.method == 'OPTIONS':
            return '', 204
        
        try:
            data = request.get_json(silent=True) or {}
            
            aircraft_type = data.get('aircraft_type', 'Boeing 737-800')
            seat_id = data.get('seat_id', '')
            base_price = data.get('base_price', 10000)
            seat_class = data.get('seat_class', 'Economy')
            
            # Load aircraft config
            aircraft_config = _load_aircraft_config()
            
            # Find matching aircraft config
            matched_config = None
            for code, config in aircraft_config.items():
                if aircraft_type in config.get('name', ''):
                    matched_config = config
                    break
            
            if not matched_config:
                return jsonify({'error': 'Aircraft configuration not found'}), 404
            
            # Generate seat map and get seat pricing
            seat_map_generator = DynamicSeatMap(matched_config)
            seat_pricing = seat_map_generator.get_seat_pricing(
                seat_id, base_price, seat_class
            )
            
            return jsonify({
                'seat_pricing': seat_pricing,
                'calculated_at': datetime.now(timezone.utc).isoformat()
            }), 200
            
        except Exception as e:
            return jsonify({'error': f'Seat pricing failed: {str(e)}'}), 500
    
    @app.route('/api/dynamic/routes', methods=['GET'])
    def api_get_available_routes():
        """
        Get available routes with their patterns
        
        Response: { routes: {...} }
        """
        try:
            return jsonify({
                'routes': scheduler.ROUTE_PATTERNS,
                'airlines': scheduler.AIRLINE_ASSIGNMENTS,
                'provided_at': datetime.now(timezone.utc).isoformat()
            }), 200
            
        except Exception as e:
            return jsonify({'error': f'Failed to get routes: {str(e)}'}), 500
    
    @app.route('/api/dynamic/aircraft', methods=['GET'])
    def api_get_aircraft_config():
        """
        Get aircraft configurations
        
        Response: { aircraft: {...} }
        """
        try:
            aircraft_config = _load_aircraft_config()
            return jsonify({
                'aircraft': aircraft_config,
                'provided_at': datetime.now(timezone.utc).isoformat()
            }), 200
            
        except Exception as e:
            return jsonify({'error': f'Failed to get aircraft config: {str(e)}'}), 500