from datetime import datetime, timedelta
import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import qrcode
import io

@dataclass
class SeatMap:
    rows: int
    columns: int
    layout: str  # e.g., "3-3" for 3 seats on each side
    blocked_seats: List[str]
    emergency_exits: List[int]  # row numbers with emergency exits
    priority_seats: List[str]  # seats reserved for special needs

@dataclass
class Aircraft:
    code: str
    name: str
    seat_map: SeatMap
    capacity: int

class FlightManager:
    def __init__(self):
        self.base_path = os.path.dirname(__file__)
        self.load_aircraft_configs()
        
    def load_aircraft_configs(self):
        config_path = os.path.join(self.base_path, "aircraft_config.json")
        try:
            with open(config_path, 'r') as f:
                configs = json.load(f)
                self.aircraft_configs = {
                    code: Aircraft(
                        code=code,
                        name=config['name'],
                        seat_map=SeatMap(**config['seat_map']),
                        capacity=config['capacity']
                    )
                    for code, config in configs.items()
                }
        except FileNotFoundError:
            self.aircraft_configs = {}

    def get_seat_map(self, flight_id: str) -> Dict:
        """Get detailed seat map with availability."""
        flights = self._load_flights()
        flight = next((f for f in flights if f['flight'] == flight_id), None)
        if not flight:
            return None

        aircraft = self.aircraft_configs.get(flight.get('aircraft'))
        if not aircraft:
            return None

        # Get all occupied seats for this flight
        from app import passengers
        occupied_seats = [
            p.get('seat') for p in passengers 
            if p.get('flight') == flight_id and p.get('seat')
        ]

        seat_map = {
            'aircraft': aircraft.name,
            'layout': aircraft.seat_map.layout,
            'rows': aircraft.seat_map.rows,
            'columns': aircraft.seat_map.columns,
            'emergency_exits': aircraft.seat_map.emergency_exits,
            'seats': {}
        }

        # Generate seat status
        for row in range(1, aircraft.seat_map.rows + 1):
            for col in ['A', 'B', 'C', 'D', 'E', 'F']:
                seat = f"{row}{col}"
                seat_map['seats'][seat] = {
                    'status': 'blocked' if seat in aircraft.seat_map.blocked_seats
                             else 'occupied' if seat in occupied_seats
                             else 'emergency' if row in aircraft.seat_map.emergency_exits
                             else 'priority' if seat in aircraft.seat_map.priority_seats
                             else 'available',
                    'type': 'window' if col in ['A', 'F']
                           else 'middle' if col in ['B', 'E']
                           else 'aisle'
                }

        return seat_map

    def assign_optimal_seat(self, flight_id: str, passenger_type: str = 'regular') -> Optional[str]:
        """Assign best available seat based on passenger type."""
        seat_map = self.get_seat_map(flight_id)
        if not seat_map:
            return None

        # Define seat preferences based on passenger type
        preferences = {
            'family': ['window', 'middle'],  # Families prefer sitting together
            'business': ['aisle', 'window'],  # Business travelers prefer aisle access
            'elderly': ['aisle', 'priority'],  # Elderly prefer easy access
            'regular': ['window', 'aisle', 'middle']  # Regular preference order
        }

        pref_order = preferences.get(passenger_type, preferences['regular'])
        available_seats = {
            seat: info for seat, info in seat_map['seats'].items()
            if info['status'] == 'available'
        }

        # Sort seats by preference
        for seat_type in pref_order:
            seats = [
                seat for seat, info in available_seats.items()
                if info['type'] == seat_type
            ]
            if seats:
                return sorted(seats)[0]  # Return first available preferred seat

        return None

    def generate_boarding_pass(self, passenger_data: Dict) -> bytes:
        """Generate a detailed boarding pass with QR code."""
        # Create QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(json.dumps({
            'passport': passenger_data['passport'],
            'flight': passenger_data['flight'],
            'seat': passenger_data['seat'],
            'timestamp': datetime.utcnow().isoformat()
        }))
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")

        # Convert to bytes
        img_byte_array = io.BytesIO()
        qr_img.save(img_byte_array, format='PNG')
        return img_byte_array.getvalue()

    def check_flight_status(self, flight_id: str) -> Dict:
        """Get detailed flight status including weather and delays."""
        flights = self._load_flights()
        flight = next((f for f in flights if f['flight'] == flight_id), None)
        if not flight:
            return None

        # Calculate load factor
        from app import passengers
        booked_passengers = len([
            p for p in passengers if p.get('flight') == flight_id
        ])
        aircraft = self.aircraft_configs.get(flight.get('aircraft'))
        capacity = aircraft.capacity if aircraft else 0
        load_factor = (booked_passengers / capacity * 100) if capacity > 0 else 0

        return {
            'flight_id': flight_id,
            'status': flight.get('status', 'scheduled'),
            'departure_time': flight.get('time'),
            'gate': flight.get('gate'),
            'load_factor': round(load_factor, 1),
            'check_in_open': self._is_check_in_open(flight),
            'boarding_status': self._get_boarding_status(flight),
            'delay_minutes': self._calculate_delay(flight)
        }

    def _is_check_in_open(self, flight: Dict) -> bool:
        """Check if check-in is currently open for the flight."""
        if not flight.get('time'):
            return False

        departure_time = datetime.fromisoformat(flight['time'].replace('Z', ''))
        now = datetime.utcnow()

        # Load check-in window from config
        config_file = os.path.join(self.base_path, "system_config.json")
        with open(config_file, 'r') as f:
            config = json.load(f)
            start_hours = config['check_in']['start_hours_before']
            end_hours = config['check_in']['end_hours_before']

        check_in_start = departure_time - timedelta(hours=start_hours)
        check_in_end = departure_time - timedelta(hours=end_hours)

        return check_in_start <= now <= check_in_end

    def _get_boarding_status(self, flight: Dict) -> str:
        """Get current boarding status with specific group information."""
        if not flight.get('time'):
            return 'not_boarding'

        departure_time = datetime.fromisoformat(flight['time'].replace('Z', ''))
        now = datetime.utcnow()
        time_to_departure = (departure_time - now).total_seconds() / 3600

        if time_to_departure > 2:
            return 'not_boarding'
        elif time_to_departure > 1.5:
            return 'priority_boarding'
        elif time_to_departure > 1:
            return 'general_boarding'
        elif time_to_departure > 0.5:
            return 'final_call'
        else:
            return 'gate_closed'

    def _calculate_delay(self, flight: Dict) -> int:
        """Calculate current delay in minutes."""
        if not flight.get('time'):
            return 0

        scheduled_time = datetime.fromisoformat(flight['time'].replace('Z', ''))
        estimated_time = flight.get('estimated_time')
        
        if estimated_time:
            estimated_time = datetime.fromisoformat(estimated_time.replace('Z', ''))
            delay = (estimated_time - scheduled_time).total_seconds() / 60
            return max(0, int(delay))
        return 0

    def _load_flights(self):
        flights_file = os.path.join(self.base_path, "flights.json")
        try:
            with open(flights_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return []