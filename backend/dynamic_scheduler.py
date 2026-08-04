"""
Dynamic Flight Scheduler
Generates flight schedules dynamically based on routes, timing patterns, and demand
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import random
import json
from pricing_engine import PricingEngine


class DynamicScheduler:
    """
    Dynamic flight scheduling system that replaces fixed flight data with:
    - Generated flight times based on route patterns
    - Real-time pricing using PricingEngine
    - Dynamic seat maps based on aircraft configuration
    """
    
    # Route patterns with typical frequency and timing
    ROUTE_PATTERNS = {
        # Kenya domestic routes
        ('NBO', 'MBA'): {
            'frequency': 'hourly',
            'first_departure': '06:00',
            'last_departure': '20:00',
            'flight_duration_minutes': 60,
            'typical_aircraft': ['Embraer E190', 'Boeing 737-800', 'Airbus A320']
        },
        ('MBA', 'NBO'): {
            'frequency': 'hourly',
            'first_departure': '06:00',
            'last_departure': '20:00',
            'flight_duration_minutes': 60,
            'typical_aircraft': ['Embraer E190', 'Boeing 737-800', 'Airbus A320']
        },
        ('NBO', 'KIS'): {
            'frequency': 'daily',
            'first_departure': '08:00',
            'last_departure': '16:00',
            'flight_duration_minutes': 45,
            'typical_aircraft': ['Embraer E190', 'ATR 72']
        },
        ('KIS', 'NBO'): {
            'frequency': 'daily',
            'first_departure': '08:00',
            'last_departure': '16:00',
            'flight_duration_minutes': 45,
            'typical_aircraft': ['Embraer E190', 'ATR 72']
        },
        ('NBO', 'EDL'): {
            'frequency': 'daily',
            'first_departure': '09:00',
            'last_departure': '17:00',
            'flight_duration_minutes': 50,
            'typical_aircraft': ['Embraer E190', 'ATR 72']
        },
        ('EDL', 'NBO'): {
            'frequency': 'daily',
            'first_departure': '09:00',
            'last_departure': '17:00',
            'flight_duration_minutes': 50,
            'typical_aircraft': ['Embraer E190', 'ATR 72']
        },
        
        # Regional routes
        ('NBO', 'EBB'): {
            'frequency': 'daily',
            'first_departure': '07:00',
            'last_departure': '18:00',
            'flight_duration_minutes': 75,
            'typical_aircraft': ['Boeing 737-800', 'Airbus A320']
        },
        ('EBB', 'NBO'): {
            'frequency': 'daily',
            'first_departure': '07:00',
            'last_departure': '18:00',
            'flight_duration_minutes': 75,
            'typical_aircraft': ['Boeing 737-800', 'Airbus A320']
        },
        ('NBO', 'DAR'): {
            'frequency': 'daily',
            'first_departure': '08:00',
            'last_departure': '19:00',
            'flight_duration_minutes': 90,
            'typical_aircraft': ['Boeing 737-800', 'Airbus A320']
        },
        ('DAR', 'NBO'): {
            'frequency': 'daily',
            'first_departure': '08:00',
            'last_departure': '19:00',
            'flight_duration_minutes': 90,
            'typical_aircraft': ['Boeing 737-800', 'Airbus A320']
        },
        ('NBO', 'ADD'): {
            'frequency': 'daily',
            'first_departure': '06:00',
            'last_departure': '20:00',
            'flight_duration_minutes': 120,
            'typical_aircraft': ['Boeing 737-800', 'Boeing 787-8']
        },
        ('ADD', 'NBO'): {
            'frequency': 'daily',
            'first_departure': '06:00',
            'last_departure': '20:00',
            'flight_duration_minutes': 120,
            'typical_aircraft': ['Boeing 737-800', 'Boeing 787-8']
        },
        
        # International routes
        ('NBO', 'LHR'): {
            'frequency': 'daily',
            'first_departure': '20:00',
            'last_departure': '22:00',
            'flight_duration_minutes': 540,
            'typical_aircraft': ['Boeing 787-8', 'Boeing 777-300ER']
        },
        ('LHR', 'NBO'): {
            'frequency': 'daily',
            'first_departure': '20:00',
            'last_departure': '22:00',
            'flight_duration_minutes': 540,
            'typical_aircraft': ['Boeing 787-8', 'Boeing 777-300ER']
        },
        ('NBO', 'DXB'): {
            'frequency': 'daily',
            'first_departure': '18:00',
            'last_departure': '21:00',
            'flight_duration_minutes': 300,
            'typical_aircraft': ['Boeing 777-300ER', 'Airbus A380']
        },
        ('DXB', 'NBO'): {
            'frequency': 'daily',
            'first_departure': '18:00',
            'last_departure': '21:00',
            'flight_duration_minutes': 300,
            'typical_aircraft': ['Boeing 777-300ER', 'Airbus A380']
        },
        ('NBO', 'JFK'): {
            'frequency': 'daily',
            'first_departure': '22:00',
            'last_departure': '23:00',
            'flight_duration_minutes': 900,
            'typical_aircraft': ['Boeing 787-8', 'Boeing 777-300ER']
        },
        ('JFK', 'NBO'): {
            'frequency': 'daily',
            'first_departure': '22:00',
            'last_departure': '23:00',
            'flight_duration_minutes': 900,
            'typical_aircraft': ['Boeing 787-8', 'Boeing 777-300ER']
        },
        ('NBO', 'CDG'): {
            'frequency': 'daily',
            'first_departure': '21:00',
            'last_departure': '23:00',
            'flight_duration_minutes': 570,
            'typical_aircraft': ['Boeing 787-8', 'Airbus A350-900']
        },
        ('CDG', 'NBO'): {
            'frequency': 'daily',
            'first_departure': '21:00',
            'last_departure': '23:00',
            'flight_duration_minutes': 570,
            'typical_aircraft': ['Boeing 787-8', 'Airbus A350-900']
        },
    }
    
    # Airlines that operate on different routes
    AIRLINE_ASSIGNMENTS = {
        'Kenya Airways': ['NBO', 'MBA', 'KIS', 'EDL', 'EBB', 'JRO', 'DAR', 'ADD', 'LHR', 'DXB', 'JFK', 'CDG'],
        'SmartFly': ['NBO', 'MBA', 'KIS', 'EDL', 'EBB'],
        'JamboJet': ['NBO', 'MBA', 'KIS', 'EDL', 'WIL'],
        'Ethiopian Airlines': ['NBO', 'ADD', 'EBB', 'DAR', 'LHR', 'DXB'],
        'RwandAir': ['NBO', 'KGL', 'EBB', 'DAR'],
        'Qatar Airways': ['NBO', 'DOH', 'DXB', 'LHR', 'CDG'],
        'Emirates': ['NBO', 'DXB', 'DMM', 'LHR', 'JFK'],
        'British Airways': ['NBO', 'LHR', 'JFK'],
        'Air France': ['NBO', 'CDG', 'LHR'],
        'Lufthansa': ['NBO', 'CDG', 'DXB'],
        'Turkish Airlines': ['NBO', 'IST', 'ADD', 'DXB']
    }
    
    def __init__(self, pricing_engine: PricingEngine):
        self.pricing_engine = pricing_engine
        self.aircraft_config = self._load_aircraft_config()
    
    def is_domestic_flight(self, origin: str, destination: str) -> bool:
        """Determine if a flight is domestic (within Kenya)"""
        return (origin in self.pricing_engine.KENYA_AIRPORTS and 
                destination in self.pricing_engine.KENYA_AIRPORTS)
    
    def is_regional_flight(self, origin: str, destination: str) -> bool:
        """Determine if a flight is regional (East Africa)"""
        all_east_african = {**self.pricing_engine.KENYA_AIRPORTS, 
                          **self.pricing_engine.EAST_AFRICAN_AIRPORTS}
        return (origin in all_east_african and destination in all_east_african)
    
    def _load_aircraft_config(self) -> Dict:
        """Load aircraft configuration from file"""
        try:
            with open('aircraft_config.json', 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def generate_flights_for_route(
        self, 
        origin: str, 
        destination: str, 
        start_date: datetime, 
        end_date: datetime,
        days_ahead: int = 30
    ) -> List[Dict]:
        """
        Generate dynamic flights for a specific route within a date range
        """
        route_key = (origin, destination)
        
        # If route not in patterns, create a default pattern dynamically
        if route_key not in self.ROUTE_PATTERNS:
            pattern = self._create_default_pattern(origin, destination)
        else:
            pattern = self.ROUTE_PATTERNS[route_key]
        
        flights = []
        
        current_date = start_date
        while current_date <= end_date:
            daily_flights = self._generate_daily_flights(
                origin, destination, current_date, pattern
            )
            flights.extend(daily_flights)
            current_date += timedelta(days=1)
        
        return flights
    
    def _create_default_pattern(self, origin: str, destination: str) -> Dict:
        """Create a default pattern for routes not in ROUTE_PATTERNS"""
        # Determine if this is likely a domestic or international route
        is_domestic = self.is_domestic_flight(origin, destination)
        is_regional = self.is_regional_flight(origin, destination)
        
        if is_domestic:
            return {
                'frequency': 'hourly',
                'first_departure': '06:00',
                'last_departure': '20:00',
                'flight_duration_minutes': 60,
                'typical_aircraft': ['Embraer E190', 'Boeing 737-800', 'Airbus A320']
            }
        elif is_regional:
            return {
                'frequency': 'daily',
                'first_departure': '07:00',
                'last_departure': '18:00',
                'flight_duration_minutes': 90,
                'typical_aircraft': ['Boeing 737-800', 'Airbus A320']
            }
        else:
            # International routes
            return {
                'frequency': 'daily',
                'first_departure': '20:00',
                'last_departure': '23:00',
                'flight_duration_minutes': 480,  # 8 hours default
                'typical_aircraft': ['Boeing 787-8', 'Boeing 777-300ER', 'Airbus A350-900']
            }
    
    def _generate_daily_flights(
        self, 
        origin: str, 
        destination: str, 
        date: datetime, 
        pattern: Dict
    ) -> List[Dict]:
        """Generate flights for a single day based on route pattern"""
        flights = []
        
        first_dep = datetime.strptime(pattern['first_departure'], '%H:%M').time()
        last_dep = datetime.strptime(pattern['last_departure'], '%H:%M').time()
        duration = timedelta(minutes=pattern['flight_duration_minutes'])
        
        if pattern['frequency'] == 'hourly':
            current_time = datetime.combine(date.date(), first_dep)
            last_time = datetime.combine(date.date(), last_dep)
            
            while current_time <= last_time:
                flight = self._create_flight(
                    origin, destination, current_time, duration, pattern
                )
                flights.append(flight)
                current_time += timedelta(hours=1)
        
        elif pattern['frequency'] == 'daily':
            # Generate 2-3 flights per day for daily routes
            num_flights = random.randint(2, 3)
            for i in range(num_flights):
                # Distribute flights throughout the day
                hour_offset = (last_dep.hour - first_dep.hour) * (i + 1) / (num_flights + 1)
                dep_time = (datetime.combine(date.date(), first_dep) + 
                           timedelta(hours=hour_offset))
                flight = self._create_flight(
                    origin, destination, dep_time, duration, pattern
                )
                flights.append(flight)
        
        return flights
    
    def _create_flight(
        self, 
        origin: str, 
        destination: str, 
        departure_time: datetime, 
        duration: timedelta,
        pattern: Dict
    ) -> Dict:
        """Create a single flight with dynamic pricing and seat map"""
        arrival_time = departure_time + duration
        
        # Select aircraft and airline
        aircraft = random.choice(pattern['typical_aircraft'])
        airline = self._select_airline_for_route(origin, destination)
        
        # Get aircraft configuration
        aircraft_config = self._get_aircraft_config(aircraft)
        capacity = aircraft_config.get('capacity', 180)
        
        # Calculate dynamic pricing
        price_result = self.pricing_engine.calculate_price(
            origin, destination, airline, aircraft
        )
        # Extract the final price from the result dictionary
        base_price = price_result.get('final_price', price_result.get('base_price', 10000)) if isinstance(price_result, dict) else price_result
        
        # Generate flight ID
        flight_id = f"FLT_{origin}{destination}_{departure_time.strftime('%Y%m%d%H%M')}"
        
        return {
            'id': flight_id,
            'flight_number': self._generate_flight_number(airline),
            'airline': airline,
            'aircraft': aircraft,
            'aircraft_type': self._get_aircraft_type(aircraft),
            'origin': origin,
            'destination': destination,
            'departure_time': departure_time.isoformat(),
            'arrival_time': arrival_time.isoformat(),
            'capacity': capacity,
            'gate': self._assign_gate(),
            'status': 'scheduled',
            'checkin_enabled': False,
            'delay_minutes': 0,
            'blocked_seats': aircraft_config.get('seat_map', {}).get('blocked_seats', []),
            'booked_seats': 0,
            'crew_count': self._calculate_crew_count(capacity),
            'catering_required': random.choice([True, False]),
            'dynamic_pricing': {
                'base_price': base_price,
                'currency': 'KES',
                'price_calculation': 'dynamic',
                'last_updated': datetime.now(timezone.utc).isoformat(),
                'price_breakdown': price_result if isinstance(price_result, dict) else None
            },
            'flight_category': self.pricing_engine.get_flight_category(origin, destination),
            'distance': self.pricing_engine.calculate_distance(origin, destination),
            'duration': duration.total_seconds() / 3600,  # in hours
            'seat_map_config': aircraft_config.get('seat_map', {}),
            'is_dynamic': True
        }
    
    def _select_airline_for_route(self, origin: str, destination: str) -> str:
        """Select an airline that operates this route"""
        eligible_airlines = []
        for airline, routes in self.AIRLINE_ASSIGNMENTS.items():
            if origin in routes and destination in routes:
                eligible_airlines.append(airline)
        
        if eligible_airlines:
            return random.choice(eligible_airlines)
        return 'Kenya Airways'  # Default
    
    def _get_aircraft_config(self, aircraft_name: str) -> Dict:
        """Get aircraft configuration"""
        # Try to find matching aircraft config
        for code, config in self.aircraft_config.items():
            if config['name'] == aircraft_name or aircraft_name in config['name']:
                return config
        
        # Return default config
        return {
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
    
    def _get_aircraft_type(self, aircraft_name: str) -> str:
        """Categorize aircraft type"""
        if 'Boeing 737' in aircraft_name or 'Airbus A320' in aircraft_name:
            return 'Narrow-body'
        elif 'Boeing 787' in aircraft_name or 'Airbus A330' in aircraft_name:
            return 'Wide-body'
        elif 'Embraer' in aircraft_name or 'ATR' in aircraft_name:
            return 'Regional'
        else:
            return 'Narrow-body'
    
    def _generate_flight_number(self, airline: str) -> str:
        """Generate a realistic flight number"""
        airline_codes = {
            'Kenya Airways': 'KQ',
            'SmartFly': 'SF',
            'JamboJet': 'JM',
            'Ethiopian Airlines': 'ET',
            'RwandAir': 'WB',
            'Qatar Airways': 'QR',
            'Emirates': 'EK'
        }
        code = airline_codes.get(airline, 'FL')
        number = random.randint(100, 999)
        return f"{code}{number}"
    
    def _assign_gate(self) -> str:
        """Assign a gate"""
        gates = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2', 'D1', 'D2']
        return random.choice(gates)
    
    def _calculate_crew_count(self, capacity: int) -> int:
        """Calculate required crew based on aircraft capacity"""
        if capacity < 100:
            return 4
        elif capacity < 200:
            return 6
        else:
            return 8
    
    def get_dynamic_price(
        self, 
        flight_id: str, 
        seat_class: str = 'Economy',
        passenger_count: int = 1
    ) -> Dict:
        """
        Get real-time dynamic pricing for a flight
        """
        # This would typically fetch the flight and calculate real-time price
        # based on demand, time until departure, seat availability, etc.
        
        base_price = 10000  # Default base price
        class_multiplier = {
            'Economy': 1.0,
            'Premium Economy': 1.5,
            'Business': 2.5,
            'First': 4.0
        }.get(seat_class, 1.0)
        
        demand_multiplier = 1.0  # Could be based on booking rate
        time_multiplier = 1.0   # Could be based on time until departure
        
        # Handle if base_price is a dictionary
        if isinstance(base_price, dict):
            base_price = base_price.get('final_price', base_price.get('base_price', 10000))
        
        final_price = base_price * class_multiplier * demand_multiplier * time_multiplier
        
        return {
            'flight_id': flight_id,
            'seat_class': seat_class,
            'passenger_count': passenger_count,
            'base_price': base_price,
            'class_multiplier': class_multiplier,
            'demand_multiplier': demand_multiplier,
            'time_multiplier': time_multiplier,
            'final_price': final_price,
            'currency': 'KES',
            'calculated_at': datetime.now(timezone.utc).isoformat()
        }